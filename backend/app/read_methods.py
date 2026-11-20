"""The JSON-RPC methods that change nothing: served at POST /api/rpc/read without the window key, and sent there by the MCP server."""

READ_METHODS = frozenset(
    (
        "capabilities",
        "catalogue",
        "devices.list",
        "extensions.list",
        "job.result",
        "media.cutdowns",
        "media.list",
        "media.music",
        "media.qc",
        "media.scenes",
        "project.get",
        "project.list",
        "speech.range",
        "timeline.cuts",
    )
)
