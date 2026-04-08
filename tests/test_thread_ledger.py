import json


def test_thread_ledger_save_load_and_list(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMEM_HOME", str(tmp_path / ".cloudmem"))

    from cloudmem.thread_ledger import (
        build_thread_record,
        list_threads,
        load_thread,
        load_thread_events,
        save_thread_record,
    )

    manifest = {"ingest": {"status": "completed"}, "sync": {"status": "pending"}}
    hook = {
        "thread_id": "T-abc",
        "mode": "deep",
        "prompt_count": 4,
        "token_input": 1200,
        "token_output": 300,
        "context_used_pct": 67.1,
    }
    rec = build_thread_record(
        session_id="sess-1",
        hook_data=hook,
        manifest=manifest,
        status="completed",
        cwd=str(tmp_path),
    )
    payload = save_thread_record(rec, raw_event={"x": 1})

    assert payload["thread_id"] == "T-abc"
    assert load_thread("T-abc") is not None

    rows = list_threads(limit=10)
    assert rows
    assert rows[0]["thread_id"] == "T-abc"

    events = load_thread_events("T-abc", limit=10)
    assert events
    assert events[-1]["event"]["x"] == 1


def test_upload_thread_record_skips_without_url(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDMEM_HOME", str(tmp_path / ".cloudmem"))

    from cloudmem.thread_ledger import upload_thread_record

    out = upload_thread_record({"thread_id": "x"}, env={})
    assert out["ok"] is False
    assert out["skipped"] is True


def test_cli_thread_show_outputs_json(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("CLOUDMEM_HOME", str(tmp_path / ".cloudmem"))

    from cloudmem.thread_ledger import build_thread_record, save_thread_record
    from cloudmem import cli

    rec = build_thread_record(
        session_id="sess-cli",
        hook_data={"thread_id": "T-cli"},
        manifest={"ingest": {"status": "completed"}, "sync": {"status": "pending"}},
        status="completed",
        cwd=str(tmp_path),
    )
    save_thread_record(rec)

    class Args:
        thread_id = "T-cli"

    cli.cmd_thread_show(Args())
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["thread_id"] == "T-cli"
