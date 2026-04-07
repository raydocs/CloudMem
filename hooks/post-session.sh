#!/bin/bash
# CloudMem post-session hook
# Runs after every Claude Code session stop.
# 1. MemPalace save (from MemPalace hooks)
# 2. Ingest latest Claude session into palace
# 3. Push palace to GitHub

set -euo pipefail

PALACE_DIR="${CLOUDMEM_PALACE:-$HOME/.cloudmem}"
CLAUDE_PROJECTS="${CLAUDE_PROJECTS_DIR:-$HOME/.claude/projects}"

# ── Step 1: MemPalace structured save ───────────────────────────────────────
if command -v cloudmem &>/dev/null; then
  cloudmem save --quiet 2>/dev/null || true
fi

# ── Step 2: Ingest most recent Claude session ────────────────────────────────
if command -v cloudmem &>/dev/null && [ -d "$CLAUDE_PROJECTS" ]; then
  LAST_SESSION=$(ls -t "$CLAUDE_PROJECTS" 2>/dev/null | head -1)
  if [ -n "$LAST_SESSION" ]; then
    cloudmem mine "$CLAUDE_PROJECTS/$LAST_SESSION" --mode convos --quiet 2>/dev/null || true
  fi
fi

# ── Step 3: Push palace to GitHub ───────────────────────────────────────────
if [ -d "$PALACE_DIR/.git" ]; then
  cd "$PALACE_DIR"
  git add -A
  if ! git diff --cached --quiet; then
    git commit -m "palace: $(date '+%Y-%m-%d %H:%M')" --quiet 2>/dev/null || true
    git push --quiet 2>/dev/null || true
  fi
fi
