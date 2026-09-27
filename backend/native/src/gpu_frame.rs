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

use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;
use std::collections::HashMap;
use std::sync::Arc;
use wgpu::util::DeviceExt;

enum Step {
    Upload { picture: usize, width: u32, height: u32, deep: bool, bytes: Vec<u8> },
    Pass { code: usize, src: usize, dst: usize, held: usize, width: u32, height: u32, params: Vec<f32>, aux: Option<Vec<u8>> },
    Copy { from: usize, to: usize, width: u32, height: u32 },
    Download { picture: usize, code: usize, width: u32, height: u32, out_bytes: u64 },
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
}

#[pymethods]
impl GpuFrame {
    /// Open the adapter once; `picture_bytes` is the largest picture the batch will hold (w * h * 16).
    #[new]
    fn new(picture_bytes: u64, pictures: usize) -> PyResult<Self> {
        let instance = wgpu::Instance::new(wgpu::InstanceDescriptor { backends: wgpu::Backends::PRIMARY, ..Default::default() });
        let adapter = pollster::block_on(instance.request_adapter(&wgpu::RequestAdapterOptions {
            power_preference: wgpu::PowerPreference::HighPerformance,
            compatible_surface: None,
            force_fallback_adapter: false,
        }))
        .ok_or_else(|| PyRuntimeError::new_err("no WebGPU adapter"))?;
        let adapter_name = adapter.get_info().name;
        let big = picture_bytes.max(1 << 28);
        let limits = wgpu::Limits { max_storage_buffer_binding_size: big as u32, max_buffer_size: big, ..wgpu::Limits::default() };
        let (device, queue) = pollster::block_on(adapter.request_device(
            &wgpu::DeviceDescriptor {
                label: Some("formcut frame"),
                required_features: wgpu::Features::empty(),
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
        Ok(Self { device, queue, layout, pipelines: HashMap::new(), sources: Vec::new(), pictures, steps: Vec::new(), adapter_name })
    }

    fn adapter(&self) -> String {
        self.adapter_name.clone()
    }

    /// Register a kernel's WGSL (with the engine's HEADER where the kernel needs it); returns its id.
    fn kernel(&mut self, source: String) -> usize {
        if let Some(i) = self.sources.iter().position(|s| *s == source) {
            return i;
        }
        self.sources.push(source);
        self.sources.len() - 1
    }

    fn upload(&mut self, picture: usize, width: u32, height: u32, deep: bool, bytes: Vec<u8>) {
        self.steps.push(Step::Upload { picture, width, height, deep, bytes });
    }

    #[pyo3(signature = (code, src, dst, held, width, height, params, aux=None))]
    #[allow(clippy::too_many_arguments)]
    fn pass(&mut self, code: usize, src: usize, dst: usize, held: usize, width: u32, height: u32, params: Vec<f32>, aux: Option<Vec<u8>>) {
        self.steps.push(Step::Pass { code, src, dst, held, width, height, params, aux });
    }

    fn copy(&mut self, from: usize, to: usize, width: u32, height: u32) {
        self.steps.push(Step::Copy { from, to, width, height });
    }

    fn download(&mut self, picture: usize, code: usize, width: u32, height: u32, out_bytes: u64) {
        self.steps.push(Step::Download { picture, code, width, height, out_bytes });
    }

    /// Record every step into one command buffer, submit once, read the frame back once.
    fn run(&mut self, unpack_code: usize, unpack16_code: usize) -> PyResult<Vec<u8>> {
        let steps = std::mem::take(&mut self.steps);
        let mut encoder = self.device.create_command_encoder(&wgpu::CommandEncoderDescriptor { label: Some("formcut frame") });
        let mut readback: Option<(wgpu::Buffer, u64)> = None;
        // every pass gets its own parameter and aux buffers for this frame, so nothing is overwritten before the device reads it
        let mut scratch: Vec<wgpu::Buffer> = Vec::new();
        for step in steps {
            match step {
                Step::Upload { picture, width, height, deep, bytes } => {
                    let staging = self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: Some("upload"), contents: &bytes, usage: wgpu::BufferUsages::STORAGE });
                    let params = self.params_buffer(&[width as f32, height as f32]);
                    let other = (picture + 1) % self.pictures.len();
                    let pipeline = self.pipeline(if deep { unpack16_code } else { unpack_code })?;
                    let group = self.group(other, picture, &params, &staging, other);
                    self.dispatch(&mut encoder, &pipeline, &group, width, height);
                    scratch.push(staging);
                    scratch.push(params);
                }
                Step::Pass { code, src, dst, held, width, height, params, aux } => {
                    let mut p = vec![width as f32, height as f32];
                    p.extend(params);
                    let params = self.params_buffer(&p);
                    let filler = [0u8; 16];
                    let aux = self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: Some("aux"), contents: aux.as_deref().unwrap_or(&filler), usage: wgpu::BufferUsages::STORAGE });
                    let pipeline = self.pipeline(code)?;
                    let group = self.group(src, dst, &params, &aux, held);
                    self.dispatch(&mut encoder, &pipeline, &group, width, height);
                    scratch.push(params);
                    scratch.push(aux);
                }
                Step::Copy { from, to, width, height } => {
                    encoder.copy_buffer_to_buffer(&self.pictures[from], 0, &self.pictures[to], 0, (width as u64) * (height as u64) * 16);
                }
                Step::Download { picture, code, width, height, out_bytes } => {
                    let size = out_bytes.max(16);
                    let packed = self.device.create_buffer(&wgpu::BufferDescriptor { label: Some("packed"), size, usage: wgpu::BufferUsages::STORAGE | wgpu::BufferUsages::COPY_SRC, mapped_at_creation: false });
                    let params = self.params_buffer(&[width as f32, height as f32]);
                    let pipeline = self.pipeline(code)?;
                    let group = self.device.create_bind_group(&wgpu::BindGroupDescriptor {
                        label: None,
                        layout: &self.layout,
                        entries: &[
                            wgpu::BindGroupEntry { binding: 0, resource: self.pictures[picture].as_entire_binding() },
                            wgpu::BindGroupEntry { binding: 1, resource: packed.as_entire_binding() },
                            wgpu::BindGroupEntry { binding: 2, resource: params.as_entire_binding() },
                            wgpu::BindGroupEntry { binding: 3, resource: params.as_entire_binding() },
                            wgpu::BindGroupEntry { binding: 4, resource: self.pictures[picture].as_entire_binding() },
                        ],
                    });
                    self.dispatch(&mut encoder, &pipeline, &group, width, height);
                    let read = self.device.create_buffer(&wgpu::BufferDescriptor { label: Some("read"), size, usage: wgpu::BufferUsages::MAP_READ | wgpu::BufferUsages::COPY_DST, mapped_at_creation: false });
                    encoder.copy_buffer_to_buffer(&packed, 0, &read, 0, size);
                    readback = Some((read, out_bytes));
                    scratch.push(packed);
                    scratch.push(params);
                }
            }
        }
        self.queue.submit(Some(encoder.finish()));
        let Some((read, out_bytes)) = readback else { return Ok(Vec::new()) };
        let slice = read.slice(..);
        let (tx, rx) = std::sync::mpsc::channel();
        slice.map_async(wgpu::MapMode::Read, move |r| {
            let _ = tx.send(r);
        });
        self.device.poll(wgpu::Maintain::Wait);
        rx.recv().map_err(|_| PyRuntimeError::new_err("readback lost"))?.map_err(|e| PyRuntimeError::new_err(format!("readback: {e:?}")))?;
        let out = slice.get_mapped_range()[..out_bytes as usize].to_vec();
        read.unmap();
        drop(scratch);
        Ok(out)
    }
}

impl GpuFrame {
    fn params_buffer(&self, values: &[f32]) -> wgpu::Buffer {
        let mut padded = values.to_vec();
        while padded.len() < 32 {
            padded.push(0.0);
        }
        self.device.create_buffer_init(&wgpu::util::BufferInitDescriptor { label: Some("params"), contents: bytemuck::cast_slice(&padded), usage: wgpu::BufferUsages::STORAGE })
    }

    fn pipeline(&mut self, code: usize) -> PyResult<Arc<wgpu::ComputePipeline>> {
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

    fn dispatch(&self, encoder: &mut wgpu::CommandEncoder, pipeline: &wgpu::ComputePipeline, group: &wgpu::BindGroup, width: u32, height: u32) {
        let mut pass = encoder.begin_compute_pass(&wgpu::ComputePassDescriptor { label: None, timestamp_writes: None });
        pass.set_pipeline(pipeline);
        pass.set_bind_group(0, group, &[]);
        pass.dispatch_workgroups(width.div_ceil(16), height.div_ceil(16), 1);
    }
}

pub fn register(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<GpuFrame>()
}
