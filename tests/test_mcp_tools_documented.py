"""The MCP server's tools, and everything that names them, agree.

The README once listed 14 tools while the server had 16, and formcut_find_scenes
told agents to use formcut_split_clip, which was never written. Agents learn tool
names from these places and fail at call time when they are wrong.
"""

import importlib.util
import re

from conftest import ROOT

SERVER = (ROOT / "backend" / "app" / "agent_mcp.py").read_text(encoding="utf-8")


def _reference():
    spec = importlib.util.spec_from_file_location("mcp_tool_reference", ROOT / "setup" / "mcp_tool_reference.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_readme_states_the_tool_count_and_names_only_real_tools():
    names = {tool["name"] for tool in _reference().tools()}
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    stated = [int(n) for n in re.findall(r"\b(\d+)\s+workflow tools", readme)]
    assert stated and all(n == len(names) for n in stated), f"the README states {stated} workflow tools, the server has {len(names)}"
    mentioned = set(re.findall(r"\bformcut_[a-z_]+\b", readme)) - {"formcut_mcp"}
    assert mentioned <= names, f"the README names tools that do not exist: {sorted(mentioned - names)}"


def test_the_server_names_only_tools_that_exist():
    names = {tool["name"] for tool in _reference().tools()}
    mentioned = set(re.findall(r"\bformcut_[a-z_]+\b", SERVER)) - {"formcut_mcp"}
    assert mentioned <= names, f"named but not declared: {sorted(mentioned - names)}"


def test_the_skill_packs_tool_reference_matches_the_server():
    module = _reference()
    assert module.REFERENCE.read_text(encoding="utf-8") == module.reference(), "run python setup/mcp_tool_reference.py"
