<p align="center">
  <img src="frontend/public/favicon.svg" alt="formcut logo" width="160" />
</p>

<h1 align="center">formcut</h1>

<p align="center"><b>Truly open source video editing. Local first, no account, no upload. Cut, grade, caption and export on your own machine.</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.96.2-ffae2b" alt="version v1.96.2" />
  <img src="https://img.shields.io/badge/Node.js-18%2B-339933?logo=nodedotjs&logoColor=white" alt="Node.js 18+" />
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/license-Apache--2.0-555555" alt="license Apache 2.0" />
</p>

A complete video editor that runs entirely on your machine: multi-track timeline, one renderer shared by preview and export so what you see is what you get, a real effect catalogue, captions and speech and subject cutout from local models, a scripting API, and a desktop shell. In addition to ANA connected orchestration for video editing, which makes an edit something another system can drive.

**Stack:** vanilla TypeScript + Vite interface, Python/FastAPI engine, Tauri 2 desktop shell · one CSS token system · no interface framework, no icon dependency, no telemetry

## Highlights

- **One renderer for preview and export.** The same decode, crop, colour, effect, mask, grade, transform and composite path serves the canvas and the file, so a frame you approve is the frame you ship. Pixel-measured parameters follow the resolution actually decoded, so a blur looks the same in a small preview and a full-resolution export. Two exceptions, named here so they are not a surprise: a plain cut and a stack of untouched layers export through ffmpeg filtergraphs with the grade baked into a 33-point cube, and GIF takes a third route through a lossless intermediate; every frame with an effect, mask or transform goes through the renderer. The decoder is in the engine (FFmpeg's libraries through PyAV, each stream on the CPU or the chip by measurement, the pipe as the fallback), every blend happens in linear light on both paths, and a fast-path export is held to the frame path by a frame compared per export. An HLG or PQ project works in that transfer at sixteen bits: HDR sources arrive deep with no tone-map, SDR sources, stills and titles are lifted in at SDR white, the monitor rolls the picture off for an SDR screen, and the export keeps the light the camera recorded with MaxCLL and MaxFALL measured from the frames and written into the HEVC or AV1 stream; SDR pictures entering a deep timeline are moved to BT.2020 primaries in light. On a machine with a real GPU a layer goes up once as bytes and never comes back: its effects (every one of the sixty-one in the catalogue has a device pass), grade, LUT, shader, key, mask, cutout and transform run as WGSL passes, the layers are blended on the device, and the frame is read back once as bytes; the CPU path is kept as the reference, every pass measured within 1/255 of it, and `FORMCUT_COMPOSITE` and `FORMCUT_EFFECTS` force either side. Measured on an Apple M5, 1080p, 48 consecutive frames: 87 fps on the device path against 9 on the CPU path with zero counts of difference; `formcut-engine --bench` prints the reading on any machine, the decode floor beside it.
- **Effect catalogue, browsable and real**: 74 colour grades, 76 visual effects, 48 audio chains, 23 transitions, a library of 180 looks (twenty colour grades, each with nine finishes, named in all sixteen languages), and effect packages you import from the effects browser: a manifest with a stack of formcut's own effects and grades for video, a WGSL kernel of your own with declared parameters (compiled and run on a test frame before it is enabled, and listed with the reason if it is not), or a filter-chain template for audio, each checked before it loads, and a community registry (one JSON index, formcut's own in the repository by default, any fork's by URL) whose packages install from the effects browser after the same checks. Every card's thumbnail is rendered by the engine through that effect. An adjustment layer (Effects tab) is a clip with no footage of its own whose effects and colour apply to everything beneath it for its duration.
- **Voiceover, camera and screen recording** straight onto the timeline, three sections under Studio's Recording tab: the microphone with a device picker and a peak-holding level meter so a muted or wrong input shows before a take is wasted; the camera with its own picker, previewed live before and during a take; the screen or a window with the system sound the browser offers and your microphone mixed in if you want it. Video takes are remuxed on the way in so they seek like any footage, and each section keeps its own take.
- **Background removal that works out of the box**: the default cutout model ships inside the engine, Subject (Auto) picks person or object for you once the person model is fetched, Point to select (SAM 2) clicks what you mean and tracks it through video, and the smart brush turns one stroke into the whole region under it rather than a paint mark. Every model download is pinned to its checksum, and Local models names the processor the sessions run on.
- **Scene detection** from the inspector, which finds a long clip's cuts and splits there, so it can become short ones, **smooth slow motion** that makes the frames between rather than repeating them, and **canvas backgrounds**: a colour, a gradient, an image, or a blurred copy of the clip.
- **Picture repair**: stabilisation from a measured camera path, flicker removal, noise removal that keeps edges, and colour matching between clips.
- **Transitions** that move both clips, not only the one arriving, across wipes, slides, pushes, zoom, iris and dissolve.
- **Projects as one file**: any project exports from the home screen as a `.fc` package (the document, every media file it references, its fonts, LUTs and shaders) that you can keep or send anywhere; a `.fc` dropped on the home screen imports as a new project with its media added to the library, never overwriting anything; projects rename and delete from their cards.
- **Editing surface**: multi-timeline with reorderable, renameable tabs, any timeline placed on another as a single compound clip (the Media tab's Timelines row; it renders and sounds as that timeline, and cannot contain itself), which is also the multicam: a timeline whose tracks are the angles, the compound showing one and sounding one, a chip or a digit key cutting at the playhead and switching the tail, multi-track, multi-select with marquee, drag and drop, trim, blade, split and group split, rejoin, ripple delete, freeze frame, all reachable from the keyboard (clips are focusable with the arrows moving along and across tracks and Enter selecting; every effect, look, template and media card takes Enter), reverse, crop with canvas grips, vertical flip, detach and reattach audio, a magnetic main track, canvas alignment guides, markers on the ruler (M at the playhead, with a colour and a note, snapped to, and left by agents over the automation surface), and per-timeline width, height and frame rate.
- **Color grading**: a Color tab in the inspector with scopes (waveform, RGB parade, vectorscope with the skin tone line, histogram), lift, gamma, gain and offset wheels, primaries (contrast about a pivot, colour boost, hue), custom luma and RGB curves, hue against hue, hue against saturation and luminance against saturation curves, and a thirteen-control basic panel, with copy and paste between clips. The pipeline is colour-managed to a BT.709 working space: PQ and HLG sources are tone-mapped and wide-gamut or SD-tagged sources converted at decode, the media record and its card say what was done, and every export is tagged BT.709 so players read it as rendered. The engine renders the grade, and the layered export bakes it into the same 33-point LUT, so preview and export match.
- **Colour and shape**: imported LUTs as library looks with an intensity mix, fourteen mask shapes plus a pen tool with editable anchors and bezier handles, and In, Out and Combo animation slots that rescale when a clip is trimmed.
- **Keyframes that actually curve**: cubic-bezier easing solved the way CSS solves it, with named presets (ease, easeIn, easeOut, easeInOut, smooth, snap, overshoot, anticipate) as handle positions and a bezier mode with handles of your own, on transform properties and on any effect's parameters and amount (a diamond beside each parameter, the slider writing the key at the playhead, a lane and a graph row per keyed parameter), effect parameters and volume alike.
- **Motion tracking**: pin a title, sticker or overlay to a moving subject by clicking it on the stage; the clip gets keyframes that follow its position and, when asked, its size and angle, relative to the clip's own. Size and angle come from feature points followed by optical flow, each checked forward and back, fitted with RANSAC.
- **Titles**: weight, italic, outline, shadow, background plate, line height, letter spacing, wrap width and opacity, a gallery of ten built-in styles with engine-rendered thumbnails, presets that carry their own font, and double-click typing on the canvas. Sixteen animated titles (pop, rise, drop, spin, stamp, neon, a lower third, kicker and headline, a call to action and more) add a finished, moving design at the playhead on a track above the footage.
- **Media in, as phones make it**: HEIC, HEIF, AVIF and TIFF stills import beside the usual formats; PQ and HLG (HDR) footage is tone-mapped to SDR in the decode pipe, so it looks the same in preview and export instead of washed out; and a recording that keeps the microphone and the desktop sound as separate streams lets each clip pick which one it plays.
- **Captions and speech**: Whisper in the engine's own ONNX Runtime (Core ML, DirectML or CUDA where the machine offers one, the CPU otherwise) in tiny, base, small, medium or large, English-only or multilingual, with word timestamps taken from the model's alignment heads; a browser without the engine's transcriber falls back to Whisper in the page in tiny, base or small; with placement, size and words-per-caption controls, caption styles that colour, pop or box the word being spoken (word timestamps from Whisper where it aligns them), eight one-tap caption looks built on them (Karaoke, Pop word, Boxed, Clean plate, Neon, Bold yellow, Quiet, Lower plate) that style a track and the next transcription, a colour of its own on any word you name, typed captions, a transcript panel that edits the caption track as text with word times refitted to each edit and cuts a sentence together with the footage under it on every track (the same `timeline.cut-range` on the automation surface), SRT and WebVTT files in and out (and the same over the automation surface), and local speech with three engines: Kokoro, Kyutai's Pocket TTS (26 built-in voices, quick on a CPU) and Resemble AI's Chatterbox (expressive and multilingual, its output watermarked), the last two installed into the speech runtime on request, both able to clone a voice from a clip in Media once you confirm the speaker's permission.
- **A library of its own**: 86 stickers (shapes, arrows, callouts, labels, faces, icons, weather, celebration, nature and food), 52 sound effects (whooshes, interface sounds, impacts, cartoon sounds, everyday sounds and ambiences such as rain, wind and waves) and 18 music tracks (calm, upbeat, hip hop, electronic, dramatic and retro), all drawn and composed by formcut's own code, so they are free to use in any video with no credit needed.
- **Studio**: project settings, Pexels stock, Openverse (openly licensed sounds, music and images without a key, each imported with its licence, creator and an attribution line on the record), a media downloader for any site yt-dlp supports, generate image and video through fal.ai with your own key (the model id is an option, so any fal model is one line) or through local models declared as slots (any diffusers-layout ONNX folder in the engine's own runtime, or any program you install as a command runner with the prompt and output path substituted, image or video, weights and licence your choice), sound through ElevenLabs, an agent terminal (a real shell inside the app started with formcut's MCP server in its environment, with one-click connection for Claude Code and Codex so an agent drives the editor through the formcut tools while you watch), timeline templates (twelve of formcut's own, from a cinematic intro, lower third and photo slideshow to a vertical short and an end screen, filled with your footage in one step, beside your own saved, exported and imported ones), local video and image browsers, local speech and local models, in a popout with a collapsible rail and a per-section fullscreen view. The Sounds panel carries twenty CC0 real recordings curated from Openverse beside the synthesised set, fetched on Add. A project may name a sync folder its own Drive, Dropbox or iCloud client carries: its package follows every save there and the other machine imports it from the home screen; formcut uploads nothing.
- **Export**: H.264, HEVC, AV1 and VP9 with hardware encoders preferred and confirmed by encoding, not by listing; 10-bit where the encoder supports it; size and frame-rate presets stored as exact fractions; looping GIF through a two-pass palette; and a live size estimate fitted to real output. On a computer with no H.264 encoder, formcut downloads Cisco's OpenH264 the first time an export needs it (it can be turned off in Settings, Advanced), and otherwise saves MP4 exports as WebM.
- **One renderer for preview and export**, held there by a golden-frame check in CI that also compares the two paths on every push. Editors with separate paths drift: a transition previews as a dissolve and exports as a wipe. The frame path: a decoded layer is uploaded once as bytes, its effects, LUT, shader, key, mask, cutout and transform run as device passes (an effect without a pass runs on the CPU first and the layer still goes up once), it is staged into the frame's compositor on the device, the blend runs there, and the frame is read back once as bytes and reaches the preview as the renderer's own pixels, no JPEG between the engine and the screen; a transition or a push brings back only the frames it touches, and the CPU stays the reference for every pass. `formcut-engine --bench` prints the CPU and device frame rates on your adapter.
- **Proxy editing**: heavy footage gets a small, fast-decoding copy built in the background and used only while editing, so scrubbing 4K stops decoding 4K. Exports always read the originals, proven by identical framemd5 digests with proxies on and off.
- **Speed**: a content-keyed preview frame cache with read-ahead, per-clip audio cached and mixed live so a volume change is heard at once, probed hardware decode, and a bounded worker pool for export.
- **Automation**: JSON-RPC 2.0 over HTTP, websocket, stdin, TCP and gRPC, covering every edit the interface can make, with optimistic concurrency on every edit.
- **MCP server**: built into the app (`formcut-engine --mcp`), so Claude Code, Codex, Cursor or any MCP client can import media, build a project, render it and collect the file without touching the interface; Settings, Connections gives each client the text to add, and the server finds the running app by itself.
- **Interface**: 16 languages covering every string, Arabic, Persian and Hebrew right to left, switched in place without a reload or losing your work, drop-in locale files that may be written right to left, an Easy mode with its own tool tray and clip panel, movable panes that stack as tabs, an appearance that can follow the operating system, and inline `currentColor` icons on a 24-unit grid.
- **Privacy by construction**: the engine binds loopback, mutating calls carry a local header, remote access needs a token you set, model downloads are pinned by SHA-256, and diagnostics report secrets as set or unset rather than by value.

## Quick Start

### Download

Each release carries a zip for macOS (Apple silicon), Windows and Linux that runs with nothing else installed, formcut's ffmpeg included; the release notes say how to open each. On an Intel Mac, build it with `setup/build_macos_app --intel`. The Android and iOS apps in a release are companions, not editors: each is one screen that pairs with the formcut running on your computer and shows its interface over your own network, so the desktop must be running. To run from source instead, read on.

**Tested so far:** the macOS (Apple silicon) and Linux builds have been tested on real machines and work. The Windows build, and the Android and iOS companion apps, are built and published with every release but have not been tested on real devices yet; reports are welcome in the issues.

**Opening the macOS app:** it is signed but not notarized, so the first time macOS says it cannot verify formcut; open System Settings, Privacy & Security, and choose Open Anyway. A download from 1.41.2 or earlier may instead be called damaged, because those builds were not sealed: run `xattr -dr com.apple.quarantine formcut.app` once, then open it.

### Requirements

Node 18 or newer, Python 3.11 or newer, and `ffmpeg` and `ffprobe` on PATH. Everything else is installed by the scripts below.

### macOS and Linux

```shell
chmod +x formcut
./formcut
```

### Windows

```shell
formcut.bat
```

One command covers everything. `formcut` sequences the three scripts in `setup/`: the banner (`formcut_banner`), an idempotent install (`formcut_oc_install`: the engine's virtual environment and requirements, then the interface dependencies) and the boot (`formcut_boot`: both halves, with `.env` exported and the URLs printed). Running it again reinstalls only what is missing. On first run it creates `.env` from `example.env`; add your keys there.

### Ports

| Service | URL | Notes |
|---|---|---|
| Interface | http://localhost:3040 | Vite dev server, proxies `/api/*` to the engine |
| Engine | http://127.0.0.1:8040 | FastAPI, REST + streamed frames + JSON-RPC |
| Preview build | http://localhost:3041 | `npm run preview` of the built interface |

### Local speech runtime

`./formcut` and `formcut.bat` install the Kokoro speech runtime after the main install on every boot (idempotent, never gates the boot). To re-run it alone:

```shell
setup/setup_local_ai   # macOS and Linux; setup\setup_local_ai.bat on Windows
```

## Configuration

Everything lives in `.env` beside the launcher, never committed. The template is `example.env`:

| Variable | Purpose |
|---|---|
| `PEXELS_API_KEY` | Stock media search; a key set in Settings, AI providers overrides it and needs no restart |
| `ELEVENLABS_API_KEY` | Hosted speech; local speech needs no key. Also settable in Settings, AI providers |
| `FORMCUT_DATA_DIR` | Where media, projects, templates and renders live; defaults to the platform data directory |
| `FORMCUT_MODELS_DIR` | Where AI models live; defaults to `models/` at the repository root, or the data directory's `models` folder in the packaged app |
| `FORMCUT_MODELS_AUTO` | `1` (default) fetches only the default cutout model at engine start, a few megabytes; every other model downloads when first used. `all` fetches every permissively licensed model and the Whisper files, for a machine that will be offline. `0` fetches nothing |
| `FORMCUT_DEMO_DIR` | Demo media folder, if not `examples/demo` |
| `FORMCUT_FONT_PATH` | Fallback font for rendered text |
| `FORMCUT_PORT` | Engine port; `0` picks a free one, which the desktop and portable builds use |
| `FORMCUT_DIST` | Serve a prebuilt interface instead of the dev server |
| `FORMCUT_NO_BROWSER` | `1` stops the portable launcher opening a window |
| `FORMCUT_AI_PYTHON` | Interpreter carrying the local speech runtime |
| `PEXELS_BASE` / `ELEVENLABS_BASE` | Provider endpoints, for a proxy, a mirror or a local stub |
| `PEXELS_HOSTS` | Hosts the stock importer is allowed to fetch from |
| `FORMCUT_ENGINE` | Engine address the MCP server talks to; by default it finds the running app, then tries `http://127.0.0.1:8040` |
| `FORMCUT_MCP_SESSION` | Session name the MCP server registers under, shown in Settings, Connections |

## Demo media

The demo project loads the four files in `examples/demo/`: two 10-second clips and an image from Pexels, and a spoken line generated with Kokoro. They are in the repository, under their own licences rather than formcut's; [`examples/demo/README.md`](examples/demo/README.md) lists each one's source. They are not bundled into release builds, so in an installed app the demo button says what is missing and the effect thumbnails use a generated image.

## Architecture

```
frontend/  vanilla TypeScript + Vite, no framework
├── src/main.ts            entry, boot, window.formcut bindings
├── src/engine/            project engine (state, commands, history), media bin, timing,
│                          keyframes, captions, api client
├── src/ui/                panes (media, preview, inspector, timeline), titlebar, studio
│                          dialog, creator panel, icon modules
├── src/workers/           transcription worker (Whisper in the browser, the fallback when the engine has no ONNX Runtime)
├── src/i18n/              en, es, de key tables + the generated pack for nine more locales
└── src/styles/            tokens.css, app.css, creator.css on one token system

backend/   Python FastAPI engine
├── app/main.py            composition root, version source, loopback binding
├── app/features.py        mounts the route modules
├── app/renderer.py        the shared renderer: decode, effects, masks, grade, composite
├── app/render_stream.py   paced JPEG playback stream
├── app/video_source.py    bounded decode and the preview decoder pool
├── app/export.py          export graph and encoder ladders
├── app/catalogue.py       effects, grades, transitions, audio chains, masks, cutouts
├── app/automation.py      JSON-RPC surface (HTTP, websocket, stdin, TCP, gRPC)
├── app/orchestration.py   sessions, operation log and the server-sent event stream
├── app/providers.py       provider keys held by the engine, and a real connection test
├── app/clip_visuals.py    audio peaks and filmstrips for the timeline
├── app/storage.py         data directory usage, split into rebuildable and precious
├── app/local_speech.py    local speech: Kokoro, Pocket TTS and Chatterbox workers
├── app/model_manager.py   model installs: background on first start, cancellable, adopts old installs
├── app/templates.py       template save, fill, export, import
├── app/template_library.py formcut's own twelve templates, built in code
└── app/store.py           atomic project writes with revision checks

src-tauri/ Tauri 2 desktop shell (spawns the engine, native menu, window lifecycle)
setup/     install and build scripts (macOS, Windows, Linux app and portable)
examples/  LUT and shader examples, plus the ignored demo media folder
.docs/     licence inventory, mobile notes, and the wiki source
.claude/   contributor pointer and skills/ for AI-assisted development
.github/   publish-wiki.yml (mirrors .docs/wiki to the GitHub wiki)
```

Subsystem docs live on the [project wiki](https://github.com/nodemode-ai/formcut/wiki); the editable source sits in [`.docs/wiki/`](.docs/wiki/Home.md) and is published by a GitHub Action on every push to `main`. Licences for assets and dependencies are in [`.docs/wiki/Licences.md`](.docs/wiki/Licences.md); the mobile surface is described in [`.docs/wiki/Mobile-notes.md`](.docs/wiki/Mobile-notes.md), and how every string reaches all 16 languages in [`.docs/wiki/Translation.md`](.docs/wiki/Translation.md).

## MCP server

formcut carries an MCP server, so Claude Code, Codex, Cursor, Claude Desktop, VS Code or any MCP client can drive the editor: 21 workflow tools over stdio, built on the official Python SDK, which answers both the 2025-11-25 protocol and the stateless 2026-07-28 revision.

The installed app includes it. Open **Settings, Connections, AI agents**: it shows, for each client, the exact command or config to add, with this copy of formcut's path already filled in, and a Copy button. The client runs the app's own engine as `formcut-engine --mcp`; nothing else is installed. While formcut is running, the server finds it by itself: the engine publishes its address in `engine.json` in formcut's data folder, and every call reads it afresh, so quitting and reopening formcut breaks no connection. If formcut is not running, a call says so and asks for it to be opened.

From a checkout, the same server runs as `mcp/formcut_mcp.py` with the engine's virtualenv, or with its own from `cd mcp && ./oc_install`.

The tools are workflow shaped rather than one per endpoint: `formcut_status`,
`formcut_import_media`, `formcut_create_project`, `formcut_add_clip`,
`formcut_set_frame`, `formcut_render`, `formcut_render_status`,
`formcut_cancel_render`, `formcut_list_media`, `formcut_list_projects`,
`formcut_get_project`, `formcut_media_proxy`, `formcut_find_scenes`,
`formcut_catalogue`, `formcut_edit`, `formcut_capabilities`, and for effect packages
`formcut_package_guide`, `formcut_add_package`, `formcut_preview_package`,
`formcut_list_packages` and `formcut_remove_package`. Every call returns the handles the next one needs, and a
failure comes back as text naming the recovery action. The server identifies
itself to the engine, so Settings, Connections shows the agent that is driving.

## Project skills

`.claude/skills/formcut-skillset/` is a skill pack describing this codebase for
local development with Claude Code: a director, five specialists (engine,
interface, timeline and render, orchestration and MCP, build discipline) and
reference maps whose inventories are generated from the tree by
`setup/skill_maps.py`. It carries the invariants that explain most defects here,
so a change starts from what is true rather than from a guess.

`.claude/skills/formcut-mcp/` is a skill pack for the MCP server: setting it up
with a host, driving formcut through its tools (assembling and rendering a cut,
raw edits, a rough cut from detected scenes, and recovering from stale revisions
or an interrupted job), and changing the server safely. Its tool reference is
generated from the server by `setup/mcp_tool_reference.py`.

## Releasing

A release is a version, and only the maintainer makes one: bump it, push to `main` (which runs the checks), then run the release workflow on `main` from the Actions tab, or `gh workflow run release.yml --ref main`. `.github/workflows/release.yml` then builds macOS (Apple silicon), Windows and Linux and publishes one zip for each on the release `v<version>`. Run `python setup/preflight.py` before pushing: it refuses a version that disagrees anywhere, a build that refers to a missing file, or an ffmpeg licence that has not been decided. See [RELEASING.md](RELEASING.md).

## Development

- Conventions: surgical edits over rewrites, one state engine that owns the document, stable mounted DOM with no rebuilds, every colour and z value from a token, inline `currentColor` icons with no icon dependency, no emoji anywhere, and no claim in the notes that was not run. Full set: [CLAUDE.md](CLAUDE.md).
- Skills: project skills for AI-assisted development live in `.claude/skills/`, one folder per skill: `formcut-skillset` and `formcut-mcp`, described under Project skills.
- Wiki edits: change the files in `.docs/wiki/` and push; the Action publishes them. The wiki must exist first (create any page once in the GitHub UI) for the first publish to land.

## Contributing

Bug reports, fixes, features and translations are all welcome: [CONTRIBUTING.md](CONTRIBUTING.md) says how to set up, which checks to run and how releases happen. Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md), and security problems are reported privately, as [SECURITY.md](SECURITY.md) describes.

## Licence

Apache 2.0, in [`LICENSE`](LICENSE). Timeline glyphs derive from the Lucide set (ISC). Every third-party asset and dependency obligation is listed in [`.docs/wiki/Licences.md`](.docs/wiki/Licences.md).

## Maintenance

formcut is maintained for as long as it is really used and contributed to. Its aim is to go past CapCut in what it can do, and that takes both: people editing with it and reporting what they find, and contributions that expand what it can do. While there are both, it will keep being maintained; without them, maintenance will stop.

## Star history

<a href="https://www.star-history.com/#nodemode-ai/formcut&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=nodemode-ai/formcut&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=nodemode-ai/formcut&type=Date" />
    <img alt="Star history for nodemode-ai/formcut" src="https://api.star-history.com/svg?repos=nodemode-ai/formcut&type=Date&theme=dark" />
  </picture>
</a>
