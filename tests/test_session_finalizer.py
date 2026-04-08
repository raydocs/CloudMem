# Core assertions:
# - SessionFinalizer.run() remains idempotent for the same transcript/session.
# - SessionFinalizer now fails closed for missing/invalid transcript sources.

import json
from pathlib import Path


def _read_manifest(repo_root: Path, session_id: str) -> dict:
    manifest_path = repo_root / "sessions" / f"{session_id}.json"
    return json.loads(manifest_path.read_text())


def test_session_finalizer_run_idempotent(tmp_home, tmp_path, monkeypatch):
    import cloudmem.convo_miner as convo_miner
    from cloudmem.session_finalizer import SessionFinalizer

    calls = {"count": 0}

    def fake_mine_convo_file(*args, **kwargs):
        calls["count"] += 1
        return {"drawers_added": 1, "room": "room-smoke"}

    monkeypatch.setattr(convo_miner, "mine_convo_file", fake_mine_convo_file)

    transcript = tmp_path / "session.md"
    transcript.write_text("> hello\nworld\n")

    repo_root = tmp_path / ".cloudmem"
    finalizer = SessionFinalizer(
        palace_path=str(repo_root / "palace"),
        repo_root=str(repo_root),
    )

    session_id = "sess-idempotent"

    ok1 = finalizer.run(session_id=session_id, transcript_path=str(transcript))
    manifest_path = repo_root / "sessions" / f"{session_id}.json"
    first_manifest = manifest_path.read_text()
    first_mtime = manifest_path.stat().st_mtime_ns

    ok2 = finalizer.run(session_id=session_id, transcript_path=str(transcript))
    second_manifest = manifest_path.read_text()
    second_mtime = manifest_path.stat().st_mtime_ns

    assert ok1 is True
    assert ok2 is True
    assert calls["count"] == 1
    assert first_manifest == second_manifest
    assert first_mtime == second_mtime

    thread = repo_root / "threads" / f"{session_id}.json"
    assert thread.exists()


def test_session_finalizer_fails_when_explicit_transcript_missing(tmp_home, tmp_path, monkeypatch):
    import cloudmem.convo_miner as convo_miner
    from cloudmem.session_finalizer import SessionFinalizer

    calls = {"file": 0, "dir": 0}

    def fake_mine_convo_file(*args, **kwargs):
        calls["file"] += 1
        return {"drawers_added": 1, "room": "room-smoke"}

    def fake_mine_convos(*args, **kwargs):
        calls["dir"] += 1

    monkeypatch.setattr(convo_miner, "mine_convo_file", fake_mine_convo_file)
    monkeypatch.setattr(convo_miner, "mine_convos", fake_mine_convos)

    repo_root = tmp_path / ".cloudmem"
    finalizer = SessionFinalizer(
        palace_path=str(repo_root / "palace"),
        repo_root=str(repo_root),
    )

    missing = tmp_path / "missing-session.md"
    session_id = "sess-missing-explicit"
    ok = finalizer.run(session_id=session_id, transcript_path=str(missing))

    manifest = _read_manifest(repo_root, session_id)

    assert ok is False
    assert calls["file"] == 0
    assert calls["dir"] == 0
    assert manifest["ingest"]["status"] == "failed"
    assert manifest["ingest"]["error"] == "transcript_not_found"
    assert manifest["ingest"]["transcript_path"] == str(missing)


def test_session_finalizer_fails_when_no_fallback_source_available(tmp_home, tmp_path, monkeypatch):
    from cloudmem.session_finalizer import SessionFinalizer

    repo_root = tmp_path / ".cloudmem"
    missing_projects = tmp_path / "does-not-exist"
    monkeypatch.setenv("CLOUDMEM_CLAUDE_PROJECTS", str(missing_projects))

    finalizer = SessionFinalizer(
        palace_path=str(repo_root / "palace"),
        repo_root=str(repo_root),
    )

    session_id = "sess-no-source"
    ok = finalizer.run(session_id=session_id)

    manifest = _read_manifest(repo_root, session_id)

    assert ok is False
    assert manifest["ingest"]["status"] == "failed"
    assert manifest["ingest"]["error"] == "no_transcript_source"
    assert manifest["ingest"]["claude_projects_path"] == str(missing_projects)


def test_session_finalizer_fails_when_fallback_has_no_conversations(tmp_home, tmp_path, monkeypatch):
    import cloudmem.convo_miner as convo_miner
    from cloudmem.session_finalizer import SessionFinalizer

    projects_root = tmp_path / "projects"
    latest = projects_root / "latest"
    latest.mkdir(parents=True)
    monkeypatch.setenv("CLOUDMEM_CLAUDE_PROJECTS", str(projects_root))

    calls = {"mine_convos": 0}

    def fake_scan_convos(*args, **kwargs):
        return []

    def fake_mine_convos(*args, **kwargs):
        calls["mine_convos"] += 1

    monkeypatch.setattr(convo_miner, "scan_convos", fake_scan_convos)
    monkeypatch.setattr(convo_miner, "mine_convos", fake_mine_convos)

    repo_root = tmp_path / ".cloudmem"
    finalizer = SessionFinalizer(
        palace_path=str(repo_root / "palace"),
        repo_root=str(repo_root),
    )

    session_id = "sess-fallback-empty"
    ok = finalizer.run(session_id=session_id)

    manifest = _read_manifest(repo_root, session_id)

    assert ok is False
    assert calls["mine_convos"] == 0
    assert manifest["ingest"]["status"] == "failed"
    assert manifest["ingest"]["error"] == "fallback_no_conversations"
    assert manifest["ingest"]["source_dir"] == str(latest)


def test_session_finalizer_retries_pending_sync_without_reingest(tmp_home, tmp_path, monkeypatch):
    import cloudmem.convo_miner as convo_miner
    import cloudmem.sync as sync_mod
    from cloudmem.session_finalizer import SessionFinalizer

    calls = {"ingest": 0, "push": 0}

    def fake_mine_convo_file(*args, **kwargs):
        calls["ingest"] += 1
        return {"drawers_added": 1, "room": "room-smoke"}

    class FakeResult:
        def __init__(self, ok, **data):
            self.ok = ok
            self.data = data

    class FakeSyncManager:
        def __init__(self, repo_root=None):
            self.repo_root = repo_root

        def is_git_repo(self):
            return True

        def _get_remote_url(self):
            return "git@example.com:cloudmem/palace.git"

        def push(self, message=None):
            calls["push"] += 1
            if calls["push"] == 1:
                return FakeResult(False, error="push_failed")
            return FakeResult(True, commit_sha="abc123")

    monkeypatch.setattr(convo_miner, "mine_convo_file", fake_mine_convo_file)
    monkeypatch.setattr(sync_mod, "SyncManager", FakeSyncManager)

    transcript = tmp_path / "session.md"
    transcript.write_text("> hello\nworld\n")

    repo_root = tmp_path / ".cloudmem"
    finalizer = SessionFinalizer(
        palace_path=str(repo_root / "palace"),
        repo_root=str(repo_root),
    )

    session_id = "sess-retry-sync"

    assert finalizer.run(session_id=session_id, transcript_path=str(transcript)) is True
    first_manifest = _read_manifest(repo_root, session_id)
    assert first_manifest["sync"]["status"] == "pending"

    assert finalizer.run(session_id=session_id, transcript_path=str(transcript)) is True
    second_manifest = _read_manifest(repo_root, session_id)

    assert calls["ingest"] == 1
    assert calls["push"] == 2
    assert second_manifest["sync"]["status"] == "pushed"
    assert second_manifest["sync"]["commit_sha"] == "abc123"
