"""The MCP server's tools, and everything that names them, agree.

The README once listed 14 tools while the server had 16, and formcut_find_scenes
told agents to use formcut_split_clip, which was never written. Agents learn tool
names from these places and fail at call time when they are wrong.
"""

import importlib.util
import re

from conftest import ROOT

SERVER = (ROOT / "mcp" / "formcut_mcp.py").read_text(encoding="utf-8")


def _reference():
    spec = importlib.util.spec_from_file_location("mcp_tool_reference", ROOT / "setup" / "mcp_tool_reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_readme_lists_every_tool_and_the_count():
    names = [tool["name"] for tool in _reference().tools()]
    section = (ROOT / "README.md").read_text(encoding="utf-8").split("## MCP server", 1)[1].split("\n## ", 1)[0]
    assert f"{len(names)}\nworkflow tools" in section or f"{len(names)} workflow tools" in section
    for name in names:
        assert f"`{name}`" in section, f"the README's MCP section does not list {name}"


def test_the_server_names_only_tools_that_exist():
    names = {tool["name"] for tool in _reference().tools()}
    mentioned = set(re.findall(r"\bformcut_[a-z_]+\b", SERVER)) - {"formcut_mcp"}
    assert mentioned <= names, f"named but not declared: {sorted(mentioned - names)}"


def test_the_skill_packs_tool_reference_matches_the_server():
    module = _reference()
    assert module.REFERENCE.read_text(encoding="utf-8") == module.reference(), "run python setup/mcp_tool_reference.py"
