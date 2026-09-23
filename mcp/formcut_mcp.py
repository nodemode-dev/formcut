"""Run formcut's MCP server from the repository.

The server is backend/app/agent_mcp.py. The installed app runs it as
`formcut-engine --mcp`; this file runs the same module from a checkout, with the
engine's own virtualenv or mcp/oc_install's.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.agent_mcp import main

if __name__ == "__main__":
    main()
