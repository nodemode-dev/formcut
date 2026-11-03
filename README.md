<p align="center">
  <img src="assets/app-icon/formcut-256.png" width="128" height="128" alt="FormCut icon: rounded tiles in orange, pink and violet on a dark square">
</p>

<h1 align="center">FormCut</h1>

<p align="center">
  <b>Video editing; a local-first multi-track editor with no account and no upload.</b><br>
  Timeline, colour grading, captions, effects and export,<br>
  on your own machine. One renderer for preview and file, and open to agents.
</p>

<p align="center">
  <img alt="version v2.11.5" src="https://img.shields.io/badge/version-v2.11.5-eef0f4?style=flat-square">
  <img alt="TypeScript and Vite" src="https://img.shields.io/badge/TypeScript-Vite-3178c6?style=flat-square&logo=typescript&logoColor=white">
  <img alt="Python FastAPI" src="https://img.shields.io/badge/Python-FastAPI-3776ab?style=flat-square">
  <img alt="macOS, Windows, Linux" src="https://img.shields.io/badge/macOS%20%C2%B7%20Windows%20%C2%B7%20Linux-native-2f7bf5?style=flat-square">
  <img alt="License: Apache 2.0" src="https://img.shields.io/badge/license-Apache--2.0-3a3a3a?style=flat-square">
  <img alt="Status: active" src="https://img.shields.io/badge/status-active-d69e2e?style=flat-square">
</p>

<p align="center">
  <a href="https://formcut.formai.studio/"><b>Download FormCut on formai.studio</b></a> ·
  <a href="#run-it-from-source">Run it from source</a> ·
  <a href="#the-form-family">All Form apps</a>
</p>

<br>

<p align="center">
  <img src="docs/images/formcut-hero.png" alt="FormCut with four panoramic clips and a music track on the multi-track timeline, the media library on the left and the preview showing a Venice sunset frame" width="100%">
  <br>
  <sub>Four clips and a music track on the timeline, the library on the left, the transform inspector on the right.</sub>
</p>

<p align="center">
  <a href="#features">Features</a> · <a href="#everything-in-the-box">In the box</a> · <a href="#built-for-agents">Agents</a> · <a href="#under-the-hood">Under the hood</a> ·
  <a href="#download">Download</a> · <a href="#run-it-from-source">Run from source</a> · <a href="#the-form-family">Form family</a>
</p>

<br>

<table>
  <tr>
    <td width="25%" valign="top"><h3>What you see is what you get</h3>One renderer draws the preview and the export, so the frame you approve is the frame you ship.</td>
    <td width="25%" valign="top"><h3>Local first</h3>No account, no upload and no telemetry. The engine binds loopback and model downloads are pinned by checksum.</td>
    <td width="25%" valign="top"><h3>A real effect catalogue</h3>Grades, effects, audio chains and transitions, each previewed by the engine, plus packages you can import.</td>
    <td width="25%" valign="top"><h3>Agent-ready</h3>The same editor from the interface, a JSON-RPC surface and an MCP server, so an agent can cut a video.</td>
  </tr>
</table>

<br>

## Features

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/images/formcut-color.webp" alt="The Color tab of the inspector with a waveform scope and lift and gamma wheels beside the preview" width="100%">
      <br><sub>The Color tab with a waveform scope and grading wheels.</sub>
      <h3>Colour grading with scopes</h3>
      Waveform, parade, vectorscope and histogram, lift, gamma and gain wheels, curves and LUTs. The export bakes the same grade.
    </td>
    <td width="50%" valign="top">
      <img src="docs/images/formcut-effects.webp" alt="The effects browser with engine-rendered thumbnails for Sharpen and Edge Detect while a clip is selected" width="100%">
      <br><sub>The effects browser, every thumbnail rendered by the engine.</sub>
      <h3>Browsable effects</h3>
      Pick a category and see each effect applied to a real frame before you add it. Adjustment layers apply a stack to everything beneath.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/images/formcut-export.png" alt="The Export video dialog with format, quality, codec, size and colour options and an estimated file size" width="100%">
      <br><sub>The export dialog with codec, size and colour choices.</sub>
      <h3>Export you can trust</h3>
      H.264, HEVC, AV1, VP9 and GIF, with hardware encoders preferred and a live size estimate. HDR output tags travel with the file.
    </td>
    <td width="50%" valign="top">
      <h3>Captions, tracking and cutout</h3>
      Whisper captions from a local model, motion and planar tracking, and background removal that works out of the box.
    </td>
  </tr>
</table>

## Everything in the box

<table>
  <tr>
    <td width="33%" valign="top"><h4>76 video effects</h4>Blur · Stylize · Distort · Texture · Looks · Masks · Cutout · 74 colour grades · 23 transitions</td>
    <td width="33%" valign="top"><h4>48 audio chains</h4>Voice · Tone · Space · Clean · loudness target and true-peak ceiling on export</td>
    <td width="33%" valign="top"><h4>Formats</h4>Opens: video, audio, HEIC, HEIF, AVIF, TIFF, SRT, WebVTT · Saves: MP4, WebM, GIF · Native: <code>.fc</code></td>
  </tr>
</table>

## Built for agents

FormCut ships an MCP server with 32 workflow tools; the interface, the JSON-RPC surface and the MCP server edit the same project.

```sh
./formcut mcp            # MCP server on stdio, starts the engine if nothing answers
./formcut claude         # Claude Code here, already connected to the formcut tools
./formcut agents status  # show how Claude Code, Codex and Cursor are set up
```

`.mcp.json`, `.codex/config.toml` and `.cursor/mcp.json` are already wired in this repo. See [`AGENTS.md`](AGENTS.md).

## Under the hood

- **One renderer:** decode, effects, masks, grade and composite share one path for the canvas and the file, held together by a golden-frame check in CI.
- **Engine:** Python and FastAPI over FFmpeg's libraries, with WGSL device passes for effects and the CPU path kept as the reference.
- **Interface:** vanilla TypeScript and Vite on one CSS token system, no UI framework and no icon dependency, in 16 languages.
- **Automation:** JSON-RPC 2.0 over HTTP, websocket, stdin, TCP and gRPC, with optimistic concurrency on every edit.
- **Tested:** 868 Python test functions under `tests/` plus a window test in `frontend/tests/`, run in CI on every push.

## Download

**Get the app:** download FormCut from [formai.studio](https://formcut.formai.studio/). That is the easiest way to install it.

**Latest builds:** see the [FormCompiler releases](https://github.com/nodemode-dev/formcompiler/releases?q=formcut-v&expanded=true). **Keep it updated:** [FormPortal](https://github.com/nodemode-dev/formportal) installs, updates and rolls back every Form app from the same signed catalogue.

Builds exist for macOS (Apple silicon), Windows (x64) and Linux (x64). All FormCut builds are compiled and released from [`nodemode-dev/formcompiler`](https://github.com/nodemode-dev/formcompiler/releases), not from this repo. This repo holds the source.

## Run it from source

Prefer it in your browser, or want to contribute? Run the web UI straight from this repo.

**Requires:** Node 18+, Python 3.11+, and `ffmpeg` and `ffprobe` on PATH.

```sh
git clone git@github.com:nodemode-dev/formcut.git
cd formcut
chmod +x formcut
./formcut           # installs the engine and the interface on first run, then boots both
```

The interface opens at http://localhost:3040. On first run `.env` is created from `example.env`; every key in it is optional.

On Windows run `formcut.bat`. The engine listens on http://127.0.0.1:8040; `FORMCUT_DATA_DIR`, `FORMCUT_MODELS_DIR` and `FORMCUT_PORT` in `.env` move its data, models and port.

> [!IMPORTANT]
> **Status:** active development. The Android and iOS apps are companions that pair with FormCut running on a computer, and have not been tested on real devices yet.

**Contributing:** branch from `main`, keep changes to source here, and leave packaging and releases to formcompiler. See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`AGENTS.md`](AGENTS.md).

## Repository

| Path | What it is |
|---|---|
| `frontend/` | Vanilla TypeScript and Vite interface |
| `backend/` | Python FastAPI engine, renderer and MCP server |
| `src-tauri/` | Tauri 2 desktop shell |
| `setup/` | Install, boot and build scripts |

Docs: [`.docs/wiki`](.docs/wiki/Home.md) · Agents: [`CLAUDE.md`](CLAUDE.md), [`AGENTS.md`](AGENTS.md) · Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md)

## The Form family

FormCut is one of the **Form apps**: native creative tools that install, update and roll back through FormPortal and can all be driven by agents.

| | App | What it's for | Download | Code |
|:-:|---|---|---|---|
| <img src=".github/assets/family/form.md.png" alt="" width="32" height="32"> | **form.md** | Documents, databases and realtime editing together | [formai.studio](https://formmd.formai.studio/) | [GitHub](https://github.com/nodemode-dev/form.md) |
| <img src=".github/assets/family/format.png" alt="" width="32" height="32"> | **FormAT** | Chat and agent workspace on your key | [formai.studio](https://format.formai.studio/) | [GitHub](https://github.com/nodemode-dev/format) |
| <img src=".github/assets/family/formCAD.png" alt="" width="32" height="32"> | **FormCAD** | Drafting, parametric parts and NURBS surfaces | | [GitHub](https://github.com/nodemode-dev/formCAD) |
| <img src=".github/assets/family/formcel.png" alt="" width="32" height="32"> | **FormCel** | Spreadsheets agents can read and edit | [formai.studio](https://formcel.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formcel) |
| <img src=".github/assets/family/formcraft.png" alt="" width="32" height="32"> | **FormCraft** | Generate images, video, audio, 3D and worlds | | [GitHub](https://github.com/nodemode-dev/formcraft) |
| <img src=".github/assets/family/formcut.png" alt="" width="32" height="32"> | **FormCut** | Multi-track video editing with no upload | [formai.studio](https://formcut.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formcut) |
| <img src=".github/assets/family/formDAM.png" alt="" width="32" height="32"> | **FormDAM** | Photo library and asset manager | [formai.studio](https://formdam.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formDAM) |
| <img src=".github/assets/family/formdeck.png" alt="" width="32" height="32"> | **FormDeck** | Presentations and pitch decks | [formai.studio](https://formdeck.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formdeck) |
| <img src=".github/assets/family/formdesign.png" alt="" width="32" height="32"> | **FormDesign** | Page layout for print and the web | [formai.studio](https://formdesign.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formdesign) |
| <img src=".github/assets/family/formencoder.png" alt="" width="32" height="32"> | **FormEncoder** | Media encoding queue with presets | [formai.studio](https://formencoder.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formencoder) |
| <img src=".github/assets/family/formfabric.png" alt="" width="32" height="32"> | **FormFabric** | Sewing patterns draped with cloth simulation | | [GitHub](https://github.com/nodemode-dev/formfabric) |
| <img src=".github/assets/family/formlit.png" alt="" width="32" height="32"> | **FormLit** | Photo library and raw development | [formai.studio](https://formlit.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formlit) |
| <img src=".github/assets/family/formmorpheus.png" alt="" width="32" height="32"> | **FormMorpheus** | Frame-by-frame and performed animation | | [GitHub](https://github.com/nodemode-dev/formmorpheus) |
| <img src=".github/assets/family/formNET.png" alt="" width="32" height="32"> | **FormNET** | See what your computer sends online | | [GitHub](https://github.com/nodemode-dev/formNET) |
| <img src=".github/assets/family/formpath.png" alt="" width="32" height="32"> | **FormPath** | Vector illustration with artboards and type | [formai.studio](https://formpath.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formpath) |
| <img src=".github/assets/family/formpdf.png" alt="" width="32" height="32"> | **FormPDF** | Edit, redact, sign and fill PDFs | [formai.studio](https://formpdf.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formpdf) |
| <img src=".github/assets/family/formpromo.png" alt="" width="32" height="32"> | **FormPromo** | Promo films from your own media | [formai.studio](https://formpromo.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formpromo) |
| <img src=".github/assets/family/formref.png" alt="" width="32" height="32"> | **FormRef** | Reference boards for creative work | [formai.studio](https://formref.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formref) |
| <img src=".github/assets/family/formrig.png" alt="" width="32" height="32"> | **FormRig** | Rig, skin and retarget any mesh | | [GitHub](https://github.com/nodemode-dev/formrig) |
| <img src=".github/assets/family/formsculpt.png" alt="" width="32" height="32"> | **FormSculpt** | 3D sculpting, remeshing and painting | [formai.studio](https://formsculpt.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formsculpt) |
| <img src=".github/assets/family/formsurface.png" alt="" width="32" height="32"> | **FormSurface** | Texture painting with PBR export | [formai.studio](https://formsurface.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formsurface) |
| <img src=".github/assets/family/formtools.png" alt="" width="32" height="32"> | **FormTools** | Viewers, batch tools and file utilities | | [GitHub](https://github.com/nodemode-dev/formtools) |
| <img src=".github/assets/family/formtxt.png" alt="" width="32" height="32"> | **FormTxt** | Word processing with .docx round trips | [formai.studio](https://formtxt.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formtxt) |
| <img src=".github/assets/family/formvfx.png" alt="" width="32" height="32"> | **FormVFX** | Motion graphics and VFX compositing | [formai.studio](https://formvfx.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formvfx) |
| <img src=".github/assets/family/formvis.png" alt="" width="32" height="32"> | **FormVis** | Layered image editing with local AI | [formai.studio](https://formvis.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formvis) |
| <img src=".github/assets/family/formwav.png" alt="" width="32" height="32"> | **FormWav** | Multitrack audio editing and mixing | [formai.studio](https://formwav.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formwav) |
| <img src=".github/assets/family/formweb.png" alt="" width="32" height="32"> | **FormWeb** | Visual website building with a CMS | [formai.studio](https://formweb.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formweb) |
| <img src=".github/assets/family/formportal.png" alt="" width="32" height="32"> | **FormPortal** | Install, update and roll back Form apps | [formai.studio](https://formportal.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formportal) |
| <img src=".github/assets/family/formtray.png" alt="" width="32" height="32"> | **FormTray** | One dock icon for every app | [formai.studio](https://formtray.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formtray) |
| <img src=".github/assets/family/formMCP.png" alt="" width="32" height="32"> | **FormMCP** | One MCP connection to the family | [formai.studio](https://formmcp.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formMCP) |
| <img src=".github/assets/family/formskills.png" alt="" width="32" height="32"> | **FormSkills** | Every app's agent skills in one place | [formai.studio](https://formskill.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formskills) |
| <img src=".github/assets/family/formbench.png" alt="" width="32" height="32"> | **FormBench** | Parity, testing and rankings for the family | [formai.studio](https://formranker.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formbench) |
| <img src=".github/assets/family/formslot.png" alt="" width="32" height="32"> | **FormSlot** | Codebase memory for coding agents | | [GitHub](https://github.com/nodemode-dev/formslot) |
| <img src=".github/assets/family/subform.png" alt="" width="32" height="32"> | **SubForm** | Workbench for parallel Claude Code agents | | [GitHub](https://github.com/nodemode-dev/subform) |
| <img src=".github/assets/family/formcompiler.png" alt="" width="32" height="32"> | **FormCompiler** | Builds, signs and releases every app | [formai.studio](https://formcompiler.formai.studio/) | [GitHub](https://github.com/nodemode-dev/formcompiler) |
| <img src=".github/assets/family/formpipe.png" alt="" width="32" height="32"> | **FormPipe** | Release pipeline and update feeds | | [GitHub](https://github.com/nodemode-dev/formpipe) |

<br>

---

## Maintainers

| Maintainer | Role |
|---|---|
| [@nodemode-ai](https://github.com/nodemode-ai) | Owner |
| [@gbarnai](https://github.com/gbarnai) | Co-owner |

Code owners are set in [`.github/CODEOWNERS`](.github/CODEOWNERS).

## License

FormCut is licensed under the Apache License 2.0 ([`LICENSE`](LICENSE), SPDX `Apache-2.0`). Copyright 2026 NodeAgentc, Inc. Third-party notices: [`NOTICE`](NOTICE). How FormCut may be used is set out in [`USE_POLICY.md`](USE_POLICY.md).

<sub>Screenshot content: CC0 panoramic video clips made from Poly Haven photos, and music made for the Form family.</sub>

