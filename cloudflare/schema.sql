-- D1 schema for CloudMem thread ledger

CREATE TABLE IF NOT EXISTS thread_ledger (
  thread_id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  repo TEXT,
  branch TEXT,
  mode TEXT,
  status TEXT,
  created_at TEXT,
  ended_at TEXT,
  duration_sec INTEGER DEFAULT 0,
  prompt_count INTEGER DEFAULT 0,
  token_input INTEGER DEFAULT 0,
  token_output INTEGER DEFAULT 0,
  context_used_pct REAL DEFAULT 0,
  cost_usd REAL DEFAULT 0,
  cost_is_estimated INTEGER DEFAULT 1,
  lines_added INTEGER DEFAULT 0,
  lines_deleted INTEGER DEFAULT 0,
  lines_modified INTEGER DEFAULT 0,
  files_changed INTEGER DEFAULT 0,
  oracle_used INTEGER DEFAULT 0,
  tool_calls_count INTEGER DEFAULT 0,
  transcript_path TEXT,
  commit_sha TEXT,
  sync_status TEXT,
  ingest_status TEXT,
  error_code TEXT,
  error_detail TEXT,
  remote_status TEXT,
  remote_detail TEXT,
  updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_thread_ended_at ON thread_ledger(ended_at DESC);
CREATE INDEX IF NOT EXISTS idx_thread_repo_branch ON thread_ledger(repo, branch);
