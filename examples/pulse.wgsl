@group(0) @binding(0) var<storage, read> source: array<vec4<f32>>;
@group(0) @binding(1) var<storage, read> options: array<f32>;
@group(0) @binding(2) var<storage, read_write> output: array<vec4<f32>>;
@compute @workgroup_size(64)
fn main(@builtin(global_invocation_id) id: vec3<u32>) {
    if (id.x >= arrayLength(&output)) { return; }
    let pixel = source[id.x];
    let gain = 0.85 + 0.15 * cos(options[2] * 6.2831853);
    output[id.x] = vec4<f32>(pixel.rgb * gain, pixel.a);
}
