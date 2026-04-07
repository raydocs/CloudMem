#!/bin/bash
# CloudMem post-session hook — thin wrapper
# Reads Claude Code hook JSON from stdin, delegates all work to Python SessionFinalizer.
# Always exits 0 to avoid interrupting Claude Code's session end.

set -euo pipefail

PYTHON_BIN="${CLOUDMEM_PYTHON:-python3}"
LOG_FILE="${CLOUDMEM_LOG:-${HOME}/.cloudmem/logs/post-session.log}"

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true

# Read stdin (may contain Claude Code hook JSON)
HOOK_INPUT=$(cat)

{
  echo "--- $(date '+%Y-%m-%d %H:%M:%S') post-session ---"
  echo "$HOOK_INPUT" | "$PYTHON_BIN" -m cloudmem session-finalize --hook-json-stdin 2>&1
} >> "$LOG_FILE" 2>&1 || true

exit 0
