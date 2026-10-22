# formcut wiki

formcut is a local video editor: a TypeScript interface, a Python engine that renders every frame, and a Tauri shell. One renderer serves both the preview and the export.

## Pages

- [Architecture](Architecture): how the pieces fit, and where a frame comes from
- [Creator workflow](Creator-workflow): what you can do to a clip, in the order you would do it
- [Automation](Automation): driving the editor from outside, over RPC or MCP
- [Translation](Translation): the sixteen languages, and adding or correcting one
- [Packaging](Packaging): desktop and portable builds
- [Models](Models): every open-weight model, its link, licence and loader
- [Licences](Licences): model and asset licences, and the gate that keeps them honest
- [Mobile notes](Mobile-notes): the phone layout
- [Phones](Phones): the desktop is the editor, the phones reach it, and why.

## Where things live

| Path | What it holds |
| --- | --- |
| `frontend/src/engine` | the document, its commands, history, persistence, timing and easing |
| `frontend/src/ui` | panes, popouts and overlays |
| `backend/app` | the renderer, the effect catalogue, media, jobs, automation and the model manager |
| `mcp/` | the MCP server |
| `src-tauri/` | the desktop shell |
| `.docs/wiki` | these pages |

Every release is on the [Releases page](https://github.com/nodemode-ai/formcompiler/releases), with its downloads, checksums and the changes it carries.
