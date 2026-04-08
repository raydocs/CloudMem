# Core coverage: cloudmem_* MCP aliases exist and mirror mempalace_* tool-call behavior.

import pytest


try:
    from cloudmem import mcp_server as _mcp_server

    HAS_CLOUDMEM_ALIASES = any(name.startswith("cloudmem_") for name in _mcp_server.TOOLS)
except Exception:
    _mcp_server = None
    HAS_CLOUDMEM_ALIASES = False


@pytest.mark.skipif(not HAS_CLOUDMEM_ALIASES, reason="P1-A aliases not available yet")
def test_mcp_and_cloudmem_search_tools_both_exist():
    assert "mempalace_search" in _mcp_server.TOOLS
    assert "cloudmem_search" in _mcp_server.TOOLS


@pytest.mark.skipif(not HAS_CLOUDMEM_ALIASES, reason="P1-A aliases not available yet")
def test_every_mempalace_tool_has_cloudmem_alias():
    mempalace_names = {name for name in _mcp_server.TOOLS if name.startswith("mempalace_")}
    cloudmem_names = {name for name in _mcp_server.TOOLS if name.startswith("cloudmem_")}

    expected_aliases = {name.replace("mempalace_", "cloudmem_", 1) for name in mempalace_names}
    assert expected_aliases.issubset(cloudmem_names)


def _call_tool(name: str, arguments: dict | None = None):
    return _mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
    )


@pytest.mark.skipif(not HAS_CLOUDMEM_ALIASES, reason="P1-A aliases not available yet")
def test_cloudmem_alias_call_matches_mempalace_response_shape():
    for mem_name in sorted(n for n in _mcp_server.TOOLS if n.startswith("mempalace_")):
        alias_name = mem_name.replace("mempalace_", "cloudmem_", 1)

        primary = _call_tool(mem_name)
        alias = _call_tool(alias_name)

        assert alias is not None
        if "error" in alias:
            assert alias["error"]["code"] != -32601  # unknown tool

        assert ("result" in alias) == ("result" in primary)
        assert ("error" in alias) == ("error" in primary)
