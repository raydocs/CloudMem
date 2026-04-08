# Core assertion: MCP tool registry shape is valid and tools/list returns non-empty tools.

import pytest


def test_registered_tools_have_valid_shape(monkeypatch, tmp_path):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("CLOUDMEM_HOME", str(tmp_path / ".cloudmem"))

    from cloudmem import mcp_server

    assert mcp_server.TOOLS
    for name, spec in mcp_server.TOOLS.items():
        assert isinstance(name, str) and name.strip()
        schema = spec.get("input_schema", {})
        required = schema.get("required", [])
        assert isinstance(required, list)


def test_tools_list_request_returns_tools(monkeypatch, tmp_path):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("CLOUDMEM_HOME", str(tmp_path / ".cloudmem"))

    from cloudmem import mcp_server

    response = mcp_server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    )

    assert response is not None
    tools = response["result"]["tools"]
    assert tools

    for tool in tools:
        assert tool["name"].strip()
        required = tool.get("inputSchema", {}).get("required", [])
        assert isinstance(required, list)


def test_thread_tools_return_expected_shapes(monkeypatch, tmp_path):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("CLOUDMEM_HOME", str(tmp_path / ".cloudmem"))

    from cloudmem import mcp_server

    list_resp = mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "cloudmem_thread_list", "arguments": {"limit": 5}},
        }
    )
    assert "result" in list_resp

    show_resp = mcp_server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "cloudmem_thread_show", "arguments": {"thread_id": "nope"}},
        }
    )
    assert "result" in show_resp
