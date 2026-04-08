import pytest


class _BrokenMetaCollection:
    def __init__(self, message="metadata read failed"):
        self._message = message

    def count(self):
        return 7

    def get(self, **kwargs):
        raise RuntimeError(self._message)


class _BrokenCountCollection:
    def count(self):
        raise RuntimeError("count failed")


@pytest.mark.parametrize(
    ("fn_name", "kwargs"),
    [
        ("tool_list_wings", {}),
        ("tool_list_rooms", {"wing": "wing_code"}),
        ("tool_get_taxonomy", {}),
    ],
)
def test_read_tools_return_structured_error_on_metadata_failure(
    monkeypatch, tmp_path, fn_name, kwargs
):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("CLOUDMEM_HOME", str(tmp_path / ".cloudmem"))

    from cloudmem import mcp_server

    monkeypatch.setattr(mcp_server, "_get_collection", lambda create=False: _BrokenMetaCollection())

    result = getattr(mcp_server, fn_name)(**kwargs)

    assert isinstance(result.get("error"), dict)
    assert result["error"]["code"] == "metadata_read_failed"
    assert "metadata read failed" in result["error"]["detail"]
    assert result["palace_path"]


def test_status_returns_structured_error_on_count_failure(monkeypatch, tmp_path):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("CLOUDMEM_HOME", str(tmp_path / ".cloudmem"))

    from cloudmem import mcp_server

    monkeypatch.setattr(mcp_server, "_get_collection", lambda create=False: _BrokenCountCollection())

    result = mcp_server.tool_status()

    assert isinstance(result.get("error"), dict)
    assert result["error"]["code"] == "collection_count_failed"
    assert "count failed" in result["error"]["detail"]
    assert result["palace_path"]


def test_status_returns_structured_error_on_metadata_failure(monkeypatch, tmp_path):
    pytest.importorskip("chromadb")
    monkeypatch.setenv("CLOUDMEM_HOME", str(tmp_path / ".cloudmem"))

    from cloudmem import mcp_server

    monkeypatch.setattr(mcp_server, "_get_collection", lambda create=False: _BrokenMetaCollection())

    result = mcp_server.tool_status()

    assert isinstance(result.get("error"), dict)
    assert result["error"]["code"] == "metadata_read_failed"
    assert "metadata read failed" in result["error"]["detail"]
    assert result["total_drawers"] == 7
    assert result["palace_path"]
