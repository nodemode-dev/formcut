//! formcut's native render kernels, called from the Python engine.
//!
//! Each kernel reproduces the Python code it stands in for to the bit, so the
//! engine uses it wherever it is built and falls back to Python where it is
//! not, with the same pictures either way.

// PyO3's #[pyfunction] wrapper, generated beside each function, converts PyErr
// into itself, which newer clippy flags; the wrapper is not ours to change.
#![allow(clippy::useless_conversion)]

use numpy::{PyReadonlyArray3, PyReadwriteArray3, PyUntypedArrayMethods};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use rayon::prelude::*;

// OpenCV's warpAffine: the inverse map is stepped in 1/1024 of a pixel and
// sampled in 1/32 of a pixel, with 15-bit fixed-point bilinear weights.
const INTER_BITS: i32 = 5;
const INTER_TAB_SIZE: i32 = 1 << INTER_BITS;
const AB_BITS: i32 = 10;
const AB_SCALE: f64 = (1 << AB_BITS) as f64;
const ROUND_DELTA: i32 = (1 << AB_BITS) / INTER_TAB_SIZE / 2;
const COEF_BITS: i32 = 15;

/// OpenCV's saturate_cast<int>(double): round half to even, then clamp.
fn round_int(value: f64) -> i32 {
    value.round_ties_even().clamp(i32::MIN as f64, i32::MAX as f64) as i32
}

/// The inverse of the forward matrix, computed as warpAffine computes it.
fn invert(forward: [f64; 6]) -> [f64; 6] {
    let mut m = forward;
    let det = m[0] * m[4] - m[1] * m[3];
    let det = if det != 0.0 { 1.0 / det } else { 0.0 };
    let (a11, a22) = (m[4] * det, m[0] * det);
    m[0] = a11;
    m[1] *= -det;
    m[3] *= -det;
    m[4] = a22;
    let (b1, b2) = (-m[0] * m[2] - m[1] * m[5], -m[3] * m[2] - m[4] * m[5]);
    m[2] = b1;
    m[5] = b2;
    m
}

/// The canvas pixels the source rectangle can reach, with a margin for the taps.
fn reach(forward: &[f64; 6], source_w: usize, source_h: usize, canvas_w: usize, canvas_h: usize) -> (usize, usize, usize, usize) {
    let corners = [(-1.0, -1.0), (source_w as f64, -1.0), (-1.0, source_h as f64), (source_w as f64, source_h as f64)];
    let (mut left, mut top, mut right, mut bottom) = (f64::MAX, f64::MAX, f64::MIN, f64::MIN);
    for (u, v) in corners {
        let x = forward[0] * u + forward[1] * v + forward[2];
        let y = forward[3] * u + forward[4] * v + forward[5];
        left = left.min(x);
        right = right.max(x);
        top = top.min(y);
        bottom = bottom.max(y);
    }
    let clamp = |value: f64, limit: usize| value.clamp(0.0, limit as f64) as usize;
    (
        clamp(left.floor() - 2.0, canvas_w),
        clamp(top.floor() - 2.0, canvas_h),
        clamp(right.ceil() + 3.0, canvas_w),
        clamp(bottom.ceil() + 3.0, canvas_h),
    )
}

#[allow(clippy::too_many_arguments)]
fn draw(
    canvas: &mut [u8],
    canvas_w: usize,
    canvas_h: usize,
    source: &[u8],
    source_w: usize,
    source_h: usize,
    forward: [f64; 6],
    alpha: f64,
) {
    let m = invert(forward);
    let adelta: Vec<i32> = (0..canvas_w).map(|x| round_int(m[0] * x as f64 * AB_SCALE)).collect();
    let bdelta: Vec<i32> = (0..canvas_w).map(|x| round_int(m[3] * x as f64 * AB_SCALE)).collect();
    // The Python path multiplies the source's alpha by the layer's opacity and
    // fade before warping it, rounding half to even.
    let mut opacity = [0u8; 256];
    for (level, slot) in opacity.iter_mut().enumerate() {
        *slot = (level as f64 * alpha).round_ties_even().clamp(0.0, 255.0) as u8;
    }
    let (left, top, right, bottom) = reach(&forward, source_w, source_h, canvas_w, canvas_h);
    // An integer translation, the identity included, samples every source pixel
    // at its own position: the fractional weights are 0, so the bilinear sum is
    // the pixel times 32768 and shifts back to the pixel itself. Fetching it
    // directly is the same number without the arithmetic.
    let shift = (forward[0] == 1.0
        && forward[1] == 0.0
        && forward[3] == 0.0
        && forward[4] == 1.0
        && forward[2].fract() == 0.0
        && forward[5].fract() == 0.0)
        .then_some((forward[2] as i64, forward[5] as i64));
    canvas.par_chunks_mut(canvas_w * 4).enumerate().for_each(|(y, row)| {
        for x in 0..canvas_w {
            row[x * 4 + 3] = 255;
        }
        if y < top || y >= bottom {
            return;
        }
        if let Some((tx, ty)) = shift {
            let sy = y as i64 - ty;
            if sy < 0 || sy >= source_h as i64 {
                return;
            }
            for x in left..right {
                let sx = x as i64 - tx;
                if sx < 0 || sx >= source_w as i64 {
                    continue;
                }
                let at = (sy as usize * source_w + sx as usize) * 4;
                let layer = [source[at] as i32, source[at + 1] as i32, source[at + 2] as i32, opacity[source[at + 3] as usize] as i32];
                if layer[3] != 0 {
                    blend(row, x, layer);
                }
            }
            return;
        }
        let x0 = round_int((m[1] * y as f64 + m[2]) * AB_SCALE) + ROUND_DELTA;
        let y0 = round_int((m[4] * y as f64 + m[5]) * AB_SCALE) + ROUND_DELTA;
        for x in left..right {
            let xx = x0.wrapping_add(adelta[x]) >> (AB_BITS - INTER_BITS);
            let yy = y0.wrapping_add(bdelta[x]) >> (AB_BITS - INTER_BITS);
            let sx = (xx >> INTER_BITS).clamp(i16::MIN as i32, i16::MAX as i32);
            let sy = (yy >> INTER_BITS).clamp(i16::MIN as i32, i16::MAX as i32);
            if sx >= source_w as i32 || sx + 1 < 0 || sy >= source_h as i32 || sy + 1 < 0 {
                continue;
            }
            let (fx, fy) = (xx & (INTER_TAB_SIZE - 1), yy & (INTER_TAB_SIZE - 1));
            let weights = [(32 - fx) * (32 - fy) * 32, fx * (32 - fy) * 32, (32 - fx) * fy * 32, fx * fy * 32];
            let taps = [(sx, sy), (sx + 1, sy), (sx, sy + 1), (sx + 1, sy + 1)];
            let mut sum = [0i32; 4];
            for (weight, (tx, ty)) in weights.iter().zip(taps) {
                if tx >= 0 && ty >= 0 && (tx as usize) < source_w && (ty as usize) < source_h {
                    let at = (ty as usize * source_w + tx as usize) * 4;
                    sum[0] += source[at] as i32 * weight;
                    sum[1] += source[at + 1] as i32 * weight;
                    sum[2] += source[at + 2] as i32 * weight;
                    sum[3] += opacity[source[at + 3] as usize] as i32 * weight;
                }
            }
            let layer = sum.map(|value| ((value + (1 << (COEF_BITS - 1))) >> COEF_BITS).clamp(0, 255));
            if layer[3] != 0 {
                blend(row, x, layer);
            }
        }
    });
}

/// The Normal blend of one warped pixel onto the canvas row, in float32 in the
/// Python code's order of operations. The result is 0 to 255, where adding and
/// removing 2^23 rounds half to even as round_ties_even does, without the
/// library call per value that the baseline x86-64 build makes of it.
#[inline]
fn blend(row: &mut [u8], x: usize, layer: [i32; 4]) {
    const HALF_EVEN: f32 = 8_388_608.0;
    let a = layer[3] as f32 / 255.0;
    let keep = 1.0f32 - a;
    for channel in 0..3 {
        let base = row[x * 4 + channel] as f32 / 255.0;
        let front = layer[channel] as f32 / 255.0;
        let mixed = (base * keep + front * a).clamp(0.0, 1.0);
        row[x * 4 + channel] = ((mixed * 255.0 + HALF_EVEN) - HALF_EVEN) as u8;
    }
}

/// Warp an RGBA source onto an RGBA canvas through a forward affine matrix, at
/// an opacity, with the Normal blend, in place: cv2.warpAffine with a
/// transparent border followed by gpu.composite, in one pass and to the bit.
#[pyfunction]
fn composite_affine(
    py: Python<'_>,
    mut canvas: PyReadwriteArray3<u8>,
    source: PyReadonlyArray3<u8>,
    matrix: [f64; 6],
    alpha: f64,
) -> PyResult<()> {
    let (canvas_shape, source_shape) = (canvas.shape().to_vec(), source.shape().to_vec());
    if canvas_shape[2] != 4 || source_shape[2] != 4 {
        return Err(PyValueError::new_err("the canvas and the source must both be RGBA"));
    }
    let target = canvas.as_slice_mut().map_err(|_| PyValueError::new_err("the canvas must be contiguous"))?;
    let pixels = source.as_slice().map_err(|_| PyValueError::new_err("the source must be contiguous"))?;
    py.allow_threads(|| draw(target, canvas_shape[1], canvas_shape[0], pixels, source_shape[1], source_shape[0], matrix, alpha));
    Ok(())
}

// NumPy's float32 luma weights: each decimal rounded to float64, then to float32.
const LUMA: [f32; 3] = [0.2126_f64 as f32, 0.7152_f64 as f32, 0.0722_f64 as f32];

/// The colour panel's settings, derived exactly as pixel_effects.colour_panel
/// derives them: scalars in float64, then narrowed to float32 where NumPy
/// narrows them against a float32 frame. None is a control at its neutral
/// value, which the Python code skips, so the kernel skips it too.
struct Grade {
    gain: Option<[f32; 3]>,
    tint: Option<[f32; 3]>,
    exposure: Option<f32>,
    brightness: Option<f32>,
    contrast: Option<f32>,
    highlights: Option<f32>,
    shadows: Option<f32>,
    whites: Option<f32>,
    blacks: Option<f32>,
    luminance: bool,
    saturation: Option<f32>,
    fade: Option<(f32, f32)>,
    vignette: Option<f64>,
}

impl Grade {
    fn new(values: [f64; 12]) -> Self {
        let [temperature, tint, exposure, brightness, contrast, highlights, shadows, whites, blacks, saturation, fade, vignette] = values;
        let gain = ((temperature - 6500.0).abs() > 1e-6).then(|| {
            let shift = (6500.0 - temperature.clamp(2000.0, 11000.0)) / 4500.0;
            [(1.0 + 0.22 * shift) as f32, (1.0 + 0.02 * shift.abs() * 0.0) as f32, (1.0 - 0.22 * shift) as f32]
        });
        let tint = tint / 100.0;
        let (highlights, shadows, whites, blacks) = (highlights / 100.0, shadows / 100.0, whites / 100.0, blacks / 100.0);
        let luminance = highlights != 0.0 || shadows != 0.0 || whites != 0.0 || blacks != 0.0 || saturation != 0.0;
        let (brightness, contrast, factor) = (brightness / 100.0, 1.0 + contrast / 100.0, 1.0 + saturation / 100.0);
        let (fade, vignette) = (fade / 100.0, vignette / 100.0);
        let some = |value: f64| (value != 0.0).then_some(value as f32);
        Grade {
            gain,
            tint: (tint != 0.0).then_some([(1.0 - 0.10 * tint) as f32, (1.0 + 0.25 * tint) as f32, (1.0 - 0.10 * tint) as f32]),
            exposure: (exposure != 0.0).then(|| 2f64.powf(exposure) as f32),
            brightness: some(brightness),
            contrast: (contrast != 1.0).then_some(contrast as f32),
            highlights: some(highlights),
            shadows: some(shadows),
            whites: some(whites),
            blacks: some(blacks),
            luminance,
            saturation: (factor != 1.0 && luminance).then_some(factor as f32),
            fade: (fade != 0.0).then_some(((1.0 - 0.35 * fade) as f32, (0.12 * fade) as f32)),
            vignette: (vignette != 0.0).then_some(vignette),
        }
    }

    fn row(&self, line: &mut [u8], row: usize, width: usize, height: usize) {
        let (half_w, half_h) = (width as f64 / 2.0, height as f64 / 2.0);
        for (column, pixel) in line.as_chunks_mut::<4>().0.iter_mut().enumerate() {
            let mut c = [pixel[0] as f32 / 255.0, pixel[1] as f32 / 255.0, pixel[2] as f32 / 255.0];
            if let Some(gain) = self.gain {
                c.iter_mut().zip(gain).for_each(|(v, g)| *v *= g);
            }
            if let Some(tint) = self.tint {
                c.iter_mut().zip(tint).for_each(|(v, t)| *v *= t);
            }
            if let Some(exposure) = self.exposure {
                c.iter_mut().for_each(|v| *v *= exposure);
            }
            if let Some(brightness) = self.brightness {
                c.iter_mut().for_each(|v| *v += brightness);
            }
            if let Some(contrast) = self.contrast {
                c.iter_mut().for_each(|v| *v = (*v - 0.5) * contrast + 0.5);
            }
            // np.einsum sums in this order: (r·wr + g·wg) + b·wb.
            let lum = if self.luminance {
                (c[0].clamp(0.0, 4.0) * LUMA[0] + c[1].clamp(0.0, 4.0) * LUMA[1]) + c[2].clamp(0.0, 4.0) * LUMA[2]
            } else {
                0.0
            };
            if self.highlights.is_some() || self.shadows.is_some() {
                let high = (lum - 0.5).max(0.0) * 2.0;
                if let Some(highlights) = self.highlights {
                    let add = high * highlights;
                    c.iter_mut().for_each(|v| *v += add);
                }
                if let Some(shadows) = self.shadows {
                    let add = (0.5 - lum).max(0.0) * 2.0 * shadows;
                    c.iter_mut().for_each(|v| *v += add);
                }
            }
            if let Some(whites) = self.whites {
                let add = (lum * lum * lum) * whites;
                c.iter_mut().for_each(|v| *v += add);
            }
            if let Some(blacks) = self.blacks {
                let dark = 1.0 - lum;
                let add = (dark * dark * dark) * blacks;
                c.iter_mut().for_each(|v| *v += add);
            }
            if let Some(saturation) = self.saturation {
                c.iter_mut().for_each(|v| *v = (*v - lum) * saturation + lum);
            }
            if let Some((scale, lift)) = self.fade {
                c.iter_mut().for_each(|v| *v = *v * scale + lift);
            }
            match self.vignette {
                None => pixel.iter_mut().zip(c).for_each(|(out, v)| *out = (v * 255.0).clamp(0.0, 255.0) as u8),
                // A float32 frame times a float64 falloff is float64 in NumPy, to the end.
                Some(amount) => {
                    let (dx, dy) = ((column as f64 - half_w) / half_w, (row as f64 - half_h) / half_h);
                    let radius = (dx * dx + dy * dy).sqrt();
                    let falloff = (1.0 - radius * radius * amount).clamp(0.0, 1.0);
                    let factor = if amount > 0.0 { falloff } else { 2.0 - falloff };
                    pixel.iter_mut().zip(c).for_each(|(out, v)| *out = (v as f64 * factor * 255.0).clamp(0.0, 255.0) as u8);
                }
            }
        }
    }
}

/// The colour panel on an RGBA frame, in place, alpha untouched: the float32
/// grade of pixel_effects.colour_panel and apply_colour_panel's truncation to
/// bytes, to the bit. `values` are the panel's temperature, tint, exposure,
/// brightness, contrast, highlights, shadows, whites, blacks, saturation, fade
/// and vignette; sharpen is not here, and the engine keeps Python when it is on.
#[pyfunction]
fn colour_panel(py: Python<'_>, mut image: PyReadwriteArray3<u8>, values: [f64; 12]) -> PyResult<()> {
    let shape = image.shape().to_vec();
    if shape[2] != 4 {
        return Err(PyValueError::new_err("the image must be RGBA"));
    }
    let (height, width) = (shape[0], shape[1]);
    let pixels = image.as_slice_mut().map_err(|_| PyValueError::new_err("the image must be contiguous"))?;
    let grade = Grade::new(values);
    py.allow_threads(|| {
        pixels.par_chunks_mut(width * 4).enumerate().for_each(|(row, line)| grade.row(line, row, width, height));
    });
    Ok(())
}

const CHUNK: usize = 1 << 16;

/// Bytes to 0..1 floats into `out`, as `image.astype(np.float32) / 255` makes them.
#[pyfunction]
fn unit_float(py: Python<'_>, image: PyReadonlyArray3<u8>, mut out: PyReadwriteArray3<f32>) -> PyResult<()> {
    if image.shape() != out.shape() {
        return Err(PyValueError::new_err("the image and the output differ in shape"));
    }
    let source = image.as_slice().map_err(|_| PyValueError::new_err("the image must be contiguous"))?;
    let target = out.as_slice_mut().map_err(|_| PyValueError::new_err("the output must be contiguous"))?;
    py.allow_threads(|| {
        target.par_chunks_mut(CHUNK).zip(source.par_chunks(CHUNK)).for_each(|(to, from)| {
            to.iter_mut().zip(from).for_each(|(value, byte)| *value = *byte as f32 / 255.0);
        });
    });
    Ok(())
}

/// 0..1 floats to bytes into `out`, as `np.round(values * 255).astype(np.uint8)`
/// makes them: the product in float32, rounded half to even. round_ties_even is a
/// library call per value on baseline x86-64; adding and removing 2^23 rounds the
/// same way in plain float32 arithmetic (the values are 0 to 255) and vectorises.
#[pyfunction]
fn to_bytes(py: Python<'_>, values: PyReadonlyArray3<f32>, mut out: PyReadwriteArray3<u8>) -> PyResult<()> {
    const ROUND: f32 = 8_388_608.0;
    if values.shape() != out.shape() {
        return Err(PyValueError::new_err("the values and the output differ in shape"));
    }
    let source = values.as_slice().map_err(|_| PyValueError::new_err("the values must be contiguous"))?;
    let target = out.as_slice_mut().map_err(|_| PyValueError::new_err("the output must be contiguous"))?;
    py.allow_threads(|| {
        target.par_chunks_mut(CHUNK).zip(source.par_chunks(CHUNK)).for_each(|(to, from)| {
            to.iter_mut().zip(from).for_each(|(byte, value)| *byte = ((value * 255.0 + ROUND) - ROUND) as u8);
        });
    });
    Ok(())
}

#[pymodule]
fn formcut_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(composite_affine, module)?)?;
    module.add_function(wrap_pyfunction!(colour_panel, module)?)?;
    module.add_function(wrap_pyfunction!(unit_float, module)?)?;
    module.add_function(wrap_pyfunction!(to_bytes, module)?)?;
    Ok(())
}
