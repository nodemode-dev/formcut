# Phones: the desktop is the editor, and why

formcut's Android and iOS apps are a remote control for the desktop: they open a project, scrub it, move the playhead, add and trim clips, switch multicam angles and start exports, all against the engine running on the computer that holds the media. They are not an editor with an engine of their own, and the download page says so beside each phone card.

## Why there is no phone-hosted engine

The engine is Python over FFmpeg's libraries, ONNX Runtime, wgpu and OpenCV, with sixty-one effects as WGSL passes, Whisper, a cutout model and an optional local image model. Hosting that on a phone means either shipping a Python runtime and every native library into an app store package, at a size and a review burden that no one has volunteered for, or rewriting the engine in Kotlin and Swift twice, which would leave the desktop and the phones disagreeing about what a frame looks like, the one thing formcut has spent eighty versions refusing to allow.

So the decision, recorded here rather than implied: the desktop is the product; the phones reach it. A phone that is on the same network as the desktop gets the full editor's engine at the desktop's speed through a screen it can hold, which for cutting on the sofa is most of what a phone editor is for.

## What the phone can do today

Open, scrub, cut, trim, move, switch angles, start and watch exports, pair with a one-time code, and reconnect when the desktop's address changes. The Remote page in Studio pairs the two.

## What would change the decision

A single engine that runs on both, which is a Rust engine. That is a project of its own, not a version, and if it is ever started it starts as a compositor that produces the same frame as this one, measured the way every pass here is measured.
