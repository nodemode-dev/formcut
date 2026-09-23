<p align="center">
  <img src="frontend/public/favicon.svg" alt="formcut logo" width="160" />
</p>

<h1 align="center">formcut</h1>

<p align="center"><b>Truly open source video editing. Local first, no account, no upload. Cut, grade, caption and export on your own machine.</b></p>

<p align="center">
  <img src="https://img.shields.io/badge/version-v1.40.0-ffae2b" alt="version v1.40.0" />
  <img src="https://img.shields.io/badge/Node.js-18%2B-339933?logo=nodedotjs&logoColor=white" alt="Node.js 18+" />
  <img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" alt="Python 3.11+" />
  <img src="https://img.shields.io/badge/license-Apache--2.0-555555" alt="license Apache 2.0" />
</p>

A complete video editor that runs entirely on your machine: multi-track timeline, one renderer shared by preview and export so what you see is what you get, a real effect catalogue, captions and speech and subject cutout from local models, a scripting API, and a desktop shell. In addition to ANA connected orchestration for video editing, which makes an edit something another system can drive.

**Stack:** vanilla TypeScript + Vite interface, Python/FastAPI engine, Tauri 2 desktop shell · **Scale:** 5,367 lines of TypeScript across 49 modules, 972 lines of CSS on one token system, 4,148 lines of Python across 44 modules, 194 lines of Rust, 162 tracked files · no interface framework, no icon dependency, no telemetry

## Highlights

- **One renderer for preview and export.** The same decode, crop, colour, effect, mask, grade, transform and composite path serves the canvas and the file, so a frame you approve is the frame you ship. Pixel-measured parameters follow the resolution actually decoded, so a blur looks the same in a small preview and a full-resolution export.
- **Effect catalogue, browsable and real**: 74 colour grades, 76 visual effects, 48 audio chains, 23 transitions, a library of 180 looks (twenty colour grades, each with nine finishes, named in all twelve languages), and effect packages you import from the effects browser: a manifest with a stack of formcut's own effects and grades for video, or a filter-chain template for audio, each checked before it loads. Every card's thumbnail is rendered by the engine through that effect.
- **Voiceover recording** straight onto the timeline, with a peak-holding level meter so a muted or wrong input shows before a take is wasted.
- **Scene detection** from the inspector, which finds a long clip's cuts and splits there, so it can become short ones, **smooth slow motion** that makes the frames between rather than repeating them, and **canvas backgrounds**: a colour, a gradient, an image, or a blurred copy of the clip.
- **Picture repair**: stabilisation from a measured camera path, flicker removal, noise removal that keeps edges, and colour matching between clips.
- **Transitions** that move both clips, not only the one arriving, across wipes, slides, pushes, zoom, iris and dissolve.
- **Editing surface**: multi-timeline with reorderable, renameable tabs, multi-track, multi-select with marquee, drag and drop, trim, blade, split and group split, rejoin, ripple delete, freeze frame, reverse, crop with canvas grips, vertical flip, detach and reattach audio, a magnetic main track, canvas alignment guides, and per-timeline width, height and frame rate.
- **Color grading**: a Color tab in the inspector with scopes (waveform, RGB parade, vectorscope with the skin tone line, histogram), lift, gamma, gain and offset wheels, primaries (contrast about a pivot, colour boost, hue), custom luma and RGB curves, hue against hue, hue against saturation and luminance against saturation curves, and a thirteen-control basic panel, with copy and paste between clips. The engine renders the grade, and the layered export bakes it into the same 33-point LUT, so preview and export match.
- **Colour and shape**: imported LUTs as library looks with an intensity mix, fourteen mask shapes plus a pen tool with editable anchors and bezier handles, and In, Out and Combo animation slots that rescale when a clip is trimmed.
- **Keyframes that actually curve**: cubic-bezier easing solved the way CSS solves it, with named presets (ease, easeIn, easeOut, easeInOut, smooth, snap, overshoot, anticipate) as handle positions and a bezier mode with handles of your own, on transform properties, effect parameters and volume alike.
- **Titles**: weight, italic, outline, shadow, background plate, line height, letter spacing, wrap width and opacity, a gallery of ten built-in styles with engine-rendered thumbnails, presets that carry their own font, and double-click typing on the canvas.
- **Captions and speech**: Whisper in the browser in tiny, base or small, English-only or multilingual, on WebGPU where the browser offers it, with placement, size and words-per-caption controls, typed captions, and local speech with three engines: Kokoro, Kyutai's Pocket TTS (26 built-in voices, quick on a CPU) and Resemble AI's Chatterbox (expressive and multilingual, its output watermarked), the last two installed into the speech runtime on request, both able to clone a voice from a clip in Media once you confirm the speaker's permission.
- **Studio**: project settings, Pexels stock, a media downloader for any site yt-dlp supports, generate image, video and audio through your own provider keys, timeline templates, local video and image browsers, local speech and local models, in a popout with a collapsible rail and a per-section fullscreen view.
- **Export**: H.264, HEVC, AV1 and VP9 with hardware encoders preferred and confirmed by encoding, not by listing; 10-bit where the encoder supports it; size and frame-rate presets stored as exact fractions; and a live size estimate fitted to real output.
- **One renderer for preview and export**, held there by a golden-frame check in CI that also compares the two paths on every push. Editors with separate paths drift: a transition previews as a dissolve and exports as a wipe.
- **Proxy editing**: heavy footage gets a small, fast-decoding copy built in the background and used only while editing, so scrubbing 4K stops decoding 4K. Exports always read the originals, proven by identical framemd5 digests with proxies on and off.
- **Speed**: a content-keyed preview frame cache with read-ahead, per-clip audio cached and mixed live so a volume change is heard at once, probed hardware decode, and a bounded worker pool for export.
- **Automation**: JSON-RPC 2.0 over HTTP, websocket, stdin, TCP and gRPC, covering every edit the interface can make, with optimistic concurrency on every edit.
- **MCP server**: workflow tools over stdio in `mcp/`, so an agent can import media, build a project, render it and collect the file without touching the interface.
- **Interface**: 12 languages covering every string, switched in place without a reload or losing your work, drop-in locale files that may be written right to left, an Easy mode with its own tool tray and clip panel, movable panes that stack as tabs, an appearance that can follow the operating system, and inline `currentColor` icons on a 24-unit grid.
- **Privacy by construction**: the engine binds loopback, mutating calls carry a local header, remote access needs a token you set, model downloads are pinned by SHA-256, and diagnostics report secrets as set or unset rather than by value.

## Quick Start

### Download

Each release carries a zip for macOS (Apple silicon), Windows and Linux that runs with nothing else installed, formcut's ffmpeg included; the release notes say how to open each. On an Intel Mac, build it with `setup/build_macos_app --intel`. To run from source instead, read on.

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
| `FORMCUT_ENGINE` | Engine address the MCP server talks to, default `http://127.0.0.1:8040` |
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
├── src/workers/           transcription worker (Whisper in the browser)
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
└── app/store.py           atomic project writes with revision checks

src-tauri/ Tauri 2 desktop shell (spawns the engine, native menu, window lifecycle)
setup/     install and build scripts (macOS, Windows, Linux app and portable)
examples/  LUT and shader examples, plus the ignored demo media folder
.docs/     licence inventory, mobile notes, and the wiki source
.claude/   contributor pointer and skills/ for AI-assisted development
.github/   publish-wiki.yml (mirrors .docs/wiki to the GitHub wiki)
```

Subsystem docs live on the [project wiki](https://github.com/nodemode-ai/formcut/wiki); the editable source sits in [`.docs/wiki/`](.docs/wiki/Home.md) and is published by a GitHub Action on every push to `main`. Licences for assets and dependencies are in [`.docs/wiki/Licences.md`](.docs/wiki/Licences.md); the mobile surface is described in [`.docs/wiki/Mobile-notes.md`](.docs/wiki/Mobile-notes.md), and how every string reaches all 12 languages in [`.docs/wiki/Translation.md`](.docs/wiki/Translation.md).

## MCP server

`mcp/` carries an MCP server that puts the editor in front of an agent: 16
workflow tools over stdio, built on the official Python SDK. It runs as its own
process with its own virtualenv, because the SDK pins a newer starlette than the
engine's FastAPI accepts.

```bash
cd mcp && ./oc_install          # prints the command and args to register
```

Register the printed interpreter and script path with any MCP host. The tools
are workflow shaped rather than one per endpoint: `formcut_status`,
`formcut_import_media`, `formcut_create_project`, `formcut_add_clip`,
`formcut_set_frame`, `formcut_render`, `formcut_render_status`,
`formcut_cancel_render`, `formcut_list_media`, `formcut_list_projects`,
`formcut_get_project`, `formcut_media_proxy`, `formcut_find_scenes`,
`formcut_catalogue`, `formcut_edit` and `formcut_capabilities`. Every call returns the handles the next one needs, and a
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

A release is a version: bump it and push to `main`, and `.github/workflows/release.yml` builds macOS (Apple silicon), Windows and Linux and publishes one zip for each on the release `v<version>`. Run `python setup/preflight.py` before pushing: it refuses a version that disagrees anywhere, a build that refers to a missing file, or an ffmpeg licence that has not been decided. See [RELEASING.md](RELEASING.md).

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
