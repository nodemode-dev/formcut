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
    canvas.par_chunks_mut(canvas_w * 4).enumerate().for_each(|(y, row)| {
        for x in 0..canvas_w {
            row[x * 4 + 3] = 255;
        }
        if y < top || y >= bottom {
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
            if layer[3] == 0 {
                continue;
            }
            // The Normal blend in float32, in the Python code's order of operations.
            let a = layer[3] as f32 / 255.0;
            let keep = 1.0f32 - a;
            for channel in 0..3 {
                let base = row[x * 4 + channel] as f32 / 255.0;
                let front = layer[channel] as f32 / 255.0;
                let mixed = (base * keep + front * a).clamp(0.0, 1.0);
                row[x * 4 + channel] = (mixed * 255.0).round_ties_even() as u8;
            }
        }
    });
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

#[pymodule]
fn formcut_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(composite_affine, module)?)?;
    Ok(())
}
