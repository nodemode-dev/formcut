//! The frame path in Rust (R26): a batch executor for the engine's WGSL passes.
//!
//! The Python engine still decides what a frame is: which layers, which passes, in which order, with which
//! parameters and fields. What it stops doing is driving the device one call at a time. It hands this
//! executor the whole frame as a list of steps; the executor records every pass into one command buffer,
//! submits once, and reads the packed frame back once. The M5 profile put fourteen of every twenty-three
//! milliseconds in the Python binding between passes; here there is no Python between passes.
//!
//! The kernels are the engine's own WGSL strings, passed in and compiled once per source (the code the
//! Python path runs, so a frame from here is measured against the CPU reference exactly as before).
//! Buffers follow the engine's layout: pictures as vec4<f32>, one a pixel; parameters as f32 words
//! (w, h, then the pass's own); aux as raw bytes the kernel declares as it likes; `held` a third picture.
//!
//! Not yet compiled where it was written: the sandbox that wrote it could not fetch wgpu's crate tree
//! through its proxy and reset when cargo ran. The first build is the first verification, on a machine
//! with a GPU (`maturin develop --release --features gpu` in backend/native), and the parity check that
//! follows it is the one every pass has passed: the device against the CPU, within a count.

use numpy::PyReadonlyArray1;
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use std::collections::HashMap;
use std::sync::{Arc, Mutex};

// The executor's API as the engine checks it: 2 takes bytes and returns bytes, and stages uploads and aux on
// the device as they are recorded (1, the first build, moved every byte through a Python list).
// 3: buffers come from pools that live across frames (the M5 showed per-frame allocation costing more than
// the passes), pictures can be cleared on the device, input is read from the caller's memory (numpy or
// bytes) without a copy on the Python side, and each run's time is split for the bench.
// 4: a download may bind a second picture as held and carry parameters, so the frame's last blend and its
// pack run as one kernel.
// 5: a validation error is kept and returned by the run that met it (it had aborted the process), and with
// FORMCUT_GPU_TIMINGS=1 each pass is timed on the device (pass_times), so the bench can say which kernel
// the frame's device time goes to.
const API: u32 = 5;
const TIMED_PASSES: u32 = 128;

/// Storage buffers by size class, reused frame after frame: taken for a run, given back when it ends.
struct Pool {
    free: HashMap<u64, Vec<wgpu::Buffer>>,
}

impl Pool {
    fn take(&mut self, device: &wgpu::Device, size: u64) -> wgpu::Buffer {
        let class = size.max(256).next_power_of_two();
        if let Some(buffer) = self.free.get_mut(&class).and_then(|list| list.pop()) {
            return buffer;
        }
        device.create_buffer(&wgpu::BufferDescriptor { label: Some("pooled"), size: class, usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_DST, mapped_at_creation: false })
    }

    fn give(&mut self, buffer: wgpu::Buffer) {
        self.free.entry(buffer.size()).or_default().push(buffer);
    }
}

/// The caller's memory as bytes, read in place: a contiguous one-dimensional uint8 numpy array (the engine
/// passes its pictures as uint8 views). The buffer protocol is not in the abi3 API this module is built for.
fn bytes_of<'a>(array: &'a PyReadonlyArray1<'_, u8>) -> PyResult<&'a [u8]> {
    array.as_slice().map_err(|_| PyRuntimeError::new_err("the array must be contiguous"))
}

enum Step {
    Upload { picture: usize, width: u32, height: u32, deep: bool, staging: wgpu::Buffer },
    Pass { code: usize, src: usize, dst: usize, held: usize, width: u32, height: u32, params: Vec<f32>, aux: Option<wgpu::Buffer> },
    Copy { from: usize, to: usize, width: u32, height: u32 },
    Clear { picture: usize, bytes: u64 },
    Download { picture: usize, code: usize, width: u32, height: u32, out_bytes: u64, held: usize, params: Vec<f32> },
}

/// A frame recorded step by step and run as one command buffer.
#[pyclass]
pub struct GpuFrame {
    device: wgpu::Device,
    queue: wgpu::Queue,
    layout: wgpu::BindGroupLayout,
    // wgpu 22's ComputePipeline is not Clone (the first build on the M5 said so): shared through Arc
    pipelines: HashMap<usize, Arc<wgpu::ComputePipeline>>,
    sources: Vec<String>,
    pictures: Vec<wgpu::Buffer>,
    steps: Vec<Step>,
    adapter_name: String,
    pool: Pool,
    // the readback pair, kept and grown rather than made every frame
    packed: Option<wgpu::Buffer>,
    read: Option<wgpu::Buffer>,
    // milliseconds summed over runs: recording and submitting, waiting for the device, copying the frame out
    spent: [f64; 3],
    runs: u32,
    // device errors kept for the run that met them, instead of wgpu's default handler aborting the process
    errors: Arc<Mutex<Option<String>>>,
    // timestamps a pass, when the adapter has them and FORMCUT_GPU_TIMINGS=1: the query set, where it is
    // resolved and read, the code each timed pass ran this run, and the milliseconds summed per code
    timing: Option<(wgpu::QuerySet, wgpu::Buffer, wgpu::Buffer, f32)>,
    timed: Vec<usize>,
    per_code: HashMap<usize, (f64, u32)>,
    current_code: usize,
}

#[pymethods]
impl GpuFrame {
    /// Open the adapter once; `picture_bytes` is the largest picture the batch will hold (w * h * 16).
    #[new]
    fn new(picture_bytes: u64, pictures: usize) -> PyResult<Self> {
        // Metal, Vulkan or DX12 first; a machine with none of them (a Linux box with only OpenGL) takes GL
        let options = wgpu::RequestAdapterOptions { power_preference: wgpu::PowerPreference::HighPerformance, compatible_surface: None, force_fallback_adapter: false };
        let adapter = [wgpu::Backends::PRIMARY, wgpu::Backends::all()]
            .into_iter()
            .find_map(|backends| pollster::block_on(wgpu::Instance::new(wgpu::InstanceDescriptor { backends, ..Default::default() }).request_adapter(&options)))
            .ok_or_else(|| PyRuntimeError::new_err("no WebGPU adapter"))?;
        let info = adapter.get_info();
        // the backend in the name, so the engine can tell Metal, Vulkan or DX12 from OpenGL
        let adapter_name = format!("{} ({:?})", info.name, info.backend);
        // ask for what the adapter has: a fixed request (256 MB bindings) refused the 128 MB of an OpenGL adapter
        let limits = adapter.limits();
        if picture_bytes > limits.max_storage_buffer_binding_size as u64 {
            return Err(PyRuntimeError::new_err(format!("a {picture_bytes}-byte picture is over this adapter's {} bytes", limits.max_storage_buffer_binding_size)));
        }
        let (device, queue) = pollster::block_on(adapter.request_device(
            &wgpu::DeviceDescriptor {
                label: Some("formcut frame"),
                required_features: adapter.features() & wgpu::Features::TIMESTAMP_QUERY,
                required_limits: limits,
                memory_hints: Default::default(),
            },
            None,
        ))
        .map_err(|e| PyRuntimeError::new_err(format!("no device: {e}")))?;
        let entry = |binding: u32, read_only: bool| wgpu::BindGroupLayoutEntry {
            binding,
            visibility: wgpu::ShaderStages::COMPUTE,
            ty: wgpu::BindingType::Buffer { ty: wgpu::BufferBindingType::Storage { read_only }, has_dynamic_offset: false, min_binding_size: None },
            count: None,
        };
        let layout = device.create_bind_group_layout(&wgpu::BindGroupLayoutDescriptor {
            label: Some("formcut pass"),
            entries: &[entry(0, true), entry(1, false), entry(2, true), entry(3, true), entry(4, true)],
        });
        let usage = wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC | wgpu::BufferUsages::COPY_DST;
        let pictures = (0..pictures)
            .map(|i| device.create_buffer(&wgpu::BufferDescriptor { label: Some(&format!("picture {i}")), size: picture_bytes, usage, mapped_at_creation: false }))
            .collect();
        Ok(Self {
            device,
            queue,
            layout,
            pipelines: HashMap::new(),
            sources: Vec::new(),
            pictures,
            steps: Vec::new(),
            adapter_name,
            pool: Pool { free: HashMap::new() },
            packed: None,
            read: None,
            spent: [0.0; 3],
            runs: 0,
            errors: Arc::new(Mutex::new(None)),
            timing: None,
            timed: Vec::new(),
            per_code: HashMap::new(),
            current_code: 0,
        })
        .map(|mut frame| {
            let kept = Arc::clone(&frame.errors);
            frame.device.on_uncaptured_error(Box::new(move |error| {
                if let Ok(mut slot) = kept.lock() {
                    slot.get_or_insert_with(|| error.to_string());
                }
            }));
            let wanted = std::env::var("FORMCUT_GPU_TIMINGS").map(|v| v == "1").unwrap_or(false);
            if wanted && frame.device.features().contains(wgpu::Features::TIMESTAMP_QUERY) {
                let count = TIMED_PASSES * 2;
                let set = frame.device.create_query_set(&wgpu::QuerySetDescriptor { label: Some("pass times"), ty: wgpu::QueryType::Timestamp, count });
                let resolve = frame.device.create_buffer(&wgpu::BufferDescriptor { label: Some("pass times"), size: count as u64 * 8, usage: wgpu::BufferUsages::QUERY_RESOLVE | wgpu::BufferUsages::COPY_SRC, mapped_at_creation: false });
                let read = frame.device.create_buffer(&wgpu::BufferDescriptor { label: Some("pass times read"), size: count as u64 * 8, usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST, mapped_at_creation: false });
                let period = frame.queue.get_timestamp_period();
                frame.timing = Some((set, resolve, read, period));
            }
            frame
        })
    }

    fn adapter(&self) -> String {
        self.adapter_name.clone()
    }

    fn api(&self) -> u32 {
        API
    }

    /// Register a kernel's WGSL (with the engine's HEADER where the kernel needs it); returns its id.
    fn kernel(&mut self, source: String) -> usize {
        if let Some(i) = self.sources.iter().position(|s| *s == source) {
            return i;
        }
        self.sources.push(source);
        self.sources.len() - 1
    }

    /// Averages since the last call, in milliseconds: (recording and submitting, waiting for the device, the copy out).
    /// Device milliseconds a pass, summed per kernel since the last call, as (kernel id, milliseconds, passes);
    /// empty when the adapter has no timestamps or FORMCUT_GPU_TIMINGS is not 1.
    fn pass_times(&mut self) -> Vec<(usize, f64, u32)> {
        let mut out: Vec<(usize, f64, u32)> = self.per_code.drain().map(|(code, (ms, n))| (code, ms, n)).collect();
        out.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
        out
    }

    fn timings(&mut self) -> (f64, f64, f64) {
        let n = self.runs.max(1) as f64;
        let out = (self.spent[0] / n, self.spent[1] / n, self.spent[2] / n);
        self.spent = [0.0; 3];
        self.runs = 0;
        out
    }

    /// Stage a picture's bytes (RGBA8, or RGBA16 when `deep`) on the device now; the unpack runs with the frame.
    fn upload(&mut self, picture: usize, width: u32, height: u32, deep: bool, data: PyReadonlyArray1<'_, u8>) -> PyResult<()> {
        let bytes = bytes_of(&data)?;
        let staging = self.pool.take(&self.device, bytes.len() as u64);
        self.queue.write_buffer(&staging, 0, &bytes[..bytes.len() / 4 * 4]);
        self.steps.push(Step::Upload { picture, width, height, deep, staging });
        Ok(())
    }

    /// Fill a picture with zeros on the device (a blank canvas), instead of uploading zeros.
    fn clear(&mut self, picture: usize, bytes: u64) {
        self.steps.push(Step::Clear { picture, bytes });
    }

    /// One pass: `pass` is a Python keyword, so the method is `step` on the Python side.
    #[pyo3(name = "step", signature = (code, src, dst, held, width, height, params, aux=None))]
    #[allow(clippy::too_many_arguments)]
    fn pass(&mut self, code: usize, src: usize, dst: usize, held: usize, width: u32, height: u32, params: Vec<f32>, aux: Option<PyReadonlyArray1<'_, u8>>) -> PyResult<()> {
        let aux = match aux {
            Some(data) => {
                let bytes = bytes_of(&data)?;
                let buffer = self.pool.take(&self.device, bytes.len().max(16) as u64);
                self.queue.write_buffer(&buffer, 0, &bytes[..bytes.len() / 4 * 4]);
                Some(buffer)
            }
            None => None,
        };
        self.steps.push(Step::Pass { code, src, dst, held, width, height, params, aux });
        Ok(())
    }

    fn copy(&mut self, from: usize, to: usize, width: u32, height: u32) {
        self.steps.push(Step::Copy { from, to, width, height });
    }

    #[pyo3(signature = (picture, code, width, height, out_bytes, held=None, params=None))]
    #[allow(clippy::too_many_arguments)]
    fn download(&mut self, picture: usize, code: usize, width: u32, height: u32, out_bytes: u64, held: Option<usize>, params: Option<Vec<f32>>) {
        self.steps.push(Step::Download { picture, code, width, height, out_bytes, held: held.unwrap_or(picture), params: params.unwrap_or_default() });
    }

    /// Record every step into one command buffer, submit once, read the frame back once.
    fn run(&mut self, py: Python<'_>, unpack_code: usize, unpack16_code: usize) -> PyResult<Py<PyBytes>> {
        let started = std::time::Instant::now();
        let steps = std::mem::take(&mut self.steps);
        self.timed.clear();
        let mut encoder = self.device.create_command_encoder(&wgpu::CommandEncoderDescriptor { label: Some("formcut frame") });
        let mut readback: Option<u64> = None;
        // pooled buffers this frame used, given back once the device is done with them
        let mut used: Vec<wgpu::Buffer> = Vec::new();
        for step in steps {
            match step {
                Step::Upload { picture, width, height, deep, staging } => {
                    let params = self.params_buffer(&[width as f32, height as f32]);
                    let other = if picture == 0 { 1 } else { 0 };
                    let pipeline = self.pipeline(if deep { unpack16_code } else { unpack_code })?;
                    let group = self.group(other, picture, &params, &staging, other);
                    self.dispatch(&mut encoder, &pipeline, &group, width, height);
                    used.push(staging);
                    used.push(params);
                }
                Step::Pass { code, src, dst, held, width, height, params, aux } => {
                    let mut p = vec![width as f32, height as f32];
                    p.extend(params);
                    let params = self.params_buffer(&p);
                    // no aux given: any pooled buffer serves, as the Python context's aux holds whatever it last held
                    let aux = aux.unwrap_or_else(|| self.pool.take(&self.device, 256));
                    let pipeline = self.pipeline(code)?;
                    let group = self.group(src, dst, &params, &aux, held);
                    self.dispatch(&mut encoder, &pipeline, &group, width, height);
                    used.push(params);
                    used.push(aux);
                }
                Step::Copy { from, to, width, height } => {
                    encoder.copy_buffer_to_buffer(&self.pictures[from], 0, &self.pictures[to], 0, (width as u64) * (height as u64) * 16);
                }
                Step::Clear { picture, bytes } => {
                    encoder.clear_buffer(&self.pictures[picture], 0, Some(bytes.div_ceil(4) * 4));
                }
                Step::Download { picture, code, width, height, out_bytes, held, params } => {
                    let size = out_bytes.max(16).div_ceil(4) * 4;
                    if self.packed.as_ref().map_or(true, |b| b.size() < size) {
                        let grown = size.next_power_of_two();
                        self.packed = Some(self.device.create_buffer(&wgpu::BufferDescriptor { label: Some("packed"), size: grown, usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC, mapped_at_creation: false }));
                        self.read = Some(self.device.create_buffer(&wgpu::BufferDescriptor { label: Some("read"), size: grown, usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST, mapped_at_creation: false }));
                    }
                    let mut p = vec![width as f32, height as f32];
                    p.extend(params);
                    let params = self.params_buffer(&p);
                    let pipeline = self.pipeline(code)?;
                    let group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
                        label: None,
                        layout: &self.layout,
                        entries: &[
                            wgpu::BindGroupEntry { binding: 0, resource: self.pictures[picture].as_entire_binding() },
                            wgpu::BindGroupEntry { binding: 1, resource: self.packed.as_ref().expect("packed").as_entire_binding() },
                            wgpu::BindGroupEntry { binding: 2, resource: params.as_entire_binding() },
                            wgpu::BindGroupEntry { binding: 3, resource: params.as_entire_binding() },
                            wgpu::BindGroupEntry { binding: 4, resource: self.pictures[held].as_entire_binding() },
                        ],
                    });
                    self.dispatch(&mut encoder, &pipeline, &group, width, height);
                    let packed = self.packed.as_ref().expect("packed");
                    encoder.copy_buffer_to_buffer(packed, 0, self.read.as_ref().expect("read"), 0, size);
                    readback = Some(out_bytes);
                    used.push(params);
                }
            }
        }
        let timed = self.timed.len() as u32;
        if let Some((set, resolve, read, _)) = &self.timing {
            if timed > 0 {
                encoder.resolve_query_set(set, 0..timed * 2, resolve, 0);
                encoder.copy_buffer_to_buffer(resolve, 0, read, 0, timed as u64 * 16);
            }
        }
        self.queue.submit(Some(encoder.finish()));
        let submitted = std::time::Instant::now();
        // the wait for the device lets other Python threads run (the export's pipe writer, the decoder's read-ahead)
        let device = &self.device;
        let out = match readback {
            None => {
                py.allow_threads(|| {
                    device.poll(wgpu::Maintain::Wait);
                });
                PyBytes::new_bound(py, &[]).unbind()
            }
            Some(out_bytes) => {
                let read = self.read.as_ref().expect("read");
                let slice = read.slice(..);
                let (tx, rx) = std::sync::mpsc::channel();
                slice.map_async(wgpu::MapMode::Read, move |r| {
                    let _ = tx.send(r);
                });
                py.allow_threads(|| {
                    device.poll(wgpu::Maintain::Wait);
                });
                rx.recv().map_err(|_| PyRuntimeError::new_err("readback lost"))?.map_err(|e| PyRuntimeError::new_err(format!("readback: {e:?}")))?;
                let bytes = {
                    let mapped = slice.get_mapped_range();
                    PyBytes::new_bound(py, &mapped[..out_bytes as usize]).unbind()
                };
                read.unmap();
                bytes
            }
        };
        let waited = std::time::Instant::now();
        if let Some(message) = self.errors.lock().ok().and_then(|mut slot| slot.take()) {
            for buffer in used {
                self.pool.give(buffer);
            }
            return Err(PyRuntimeError::new_err(format!("device: {message}")));
        }
        if timed > 0 {
            if let Some((_, _, read, period)) = &self.timing {
                let slice = read.slice(0..timed as u64 * 16);
                let (tx, rx) = std::sync::mpsc::channel();
                slice.map_async(wgpu::MapMode::Read, move |r| {
                    let _ = tx.send(r);
                });
                self.device.poll(wgpu::Maintain::Wait);
                if let Ok(Ok(())) = rx.recv() {
                    let ticks: Vec<u64> = {
                        let mapped = slice.get_mapped_range();
                        bytemuck::cast_slice::<u8, u64>(&mapped).to_vec()
                    };
                    read.unmap();
                    let period = *period as f64;
                    for (k, code) in self.timed.iter().enumerate() {
                        let (begin, end) = (ticks[k * 2], ticks[k * 2 + 1]);
                        let ms = end.saturating_sub(begin) as f64 * period / 1.0e6;
                        let entry = self.per_code.entry(*code).or_insert((0.0, 0));
                        entry.0 += ms;
                        entry.1 += 1;
                    }
                }
            }
        }
        for buffer in used {
            self.pool.give(buffer);
        }
        let done = std::time::Instant::now();
        self.spent[0] += (submitted - started).as_secs_f64() * 1000.0;
        self.spent[1] += (waited - submitted).as_secs_f64() * 1000.0;
        self.spent[2] += (done - waited).as_secs_f64() * 1000.0;
        self.runs += 1;
        Ok(out)
    }
}

impl GpuFrame {
    fn params_buffer(&mut self, values: &[f32]) -> wgpu::Buffer {
        let mut padded = values.to_vec();
        while padded.len() < 32 {
            padded.push(0.0);
        }
        let buffer = self.pool.take(&self.device, (padded.len() * 4) as u64);
        self.queue.write_buffer(&buffer, 0, bytemuck::cast_slice(&padded));
        buffer
    }

    fn pipeline(&mut self, code: usize) -> PyResult<Arc<wgpu::ComputePipeline>> {
        self.current_code = code;
        if let Some(p) = self.pipelines.get(&code) {
            return Ok(Arc::clone(p));
        }
        let source = self.sources.get(code).ok_or_else(|| PyRuntimeError::new_err("unknown kernel"))?.clone();
        let module = self.device.create_shader_module(wgpu::ShaderModuleDescriptor { label: None, source: wgpu::ShaderSource::Wgsl(source.into()) });
        let layout = self.device.create_pipeline_layout(&wgpu::PipelineLayoutDescriptor { label: None, bind_group_layouts: &[&self.layout], push_constant_ranges: &[] });
        let pipeline = self.device.create_compute_pipeline(&wgpu::ComputePipelineDescriptor {
            label: None,
            layout: Some(&layout),
            module: &module,
            entry_point: "main",
            compilation_options: Default::default(),
            cache: None,
        });
        let pipeline = Arc::new(pipeline);
        self.pipelines.insert(code, Arc::clone(&pipeline));
        Ok(pipeline)
    }

    fn group(&self, src: usize, dst: usize, params: &wgpu::Buffer, aux: &wgpu::Buffer, held: usize) -> wgpu::BindGroup {
        self.device.create_bind_group(&wgpu::BindGroupDescriptor {
            label: None,
            layout: &self.layout,
            entries: &[
                wgpu::BindGroupEntry { binding: 0, resource: self.pictures[src].as_entire_binding() },
                wgpu::BindGroupEntry { binding: 1, resource: self.pictures[dst].as_entire_binding() },
                wgpu::BindGroupEntry { binding: 2, resource: params.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 3, resource: aux.as_entire_binding() },
                wgpu::BindGroupEntry { binding: 4, resource: self.pictures[held].as_entire_binding() },
            ],
        })
    }

    fn dispatch(&mut self, encoder: &mut wgpu::CommandEncoder, pipeline: &wgpu::ComputePipeline, group: &wgpu::BindGroup, width: u32, height: u32) {
        let slot = self.timed.len() as u32;
        let writes = match &self.timing {
            Some((set, _, _, _)) if slot < TIMED_PASSES => Some(wgpu::ComputePassTimestampWrites { query_set: set, beginning_of_pass_write_index: Some(slot * 2), end_of_pass_write_index: Some(slot * 2 + 1) }),
            _ => None,
        };
        if writes.is_some() {
            self.timed.push(self.current_code);
        }
        let mut pass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor { label: None, timestamp_writes: writes });
        pass.set_pipeline(pipeline);
        pass.set_bind_group(0, group, &[]);
        pass.dispatch_workgroups(width.div_ceil(16), height.div_ceil(16), 1);
    }
}

pub fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<GpuFrame>()
}
