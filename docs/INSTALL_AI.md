# CloudMem Installation Guide (For AI Agents)

This document is intended for AI assistants helping users install and configure CloudMem.
Follow these steps exactly. Do not skip steps or assume defaults.

---

## Environment Detection

Run these checks before proceeding. Stop and report if any required check fails.

```bash
# REQUIRED: Python 3.9+
python3 --version
# Expected output: Python 3.x.x where x >= 9
# If missing or < 3.9 → tell user to install Python 3.11+

# REQUIRED for hooks only: Node.js 18+
node --version
# Expected output: v18.x.x or higher
# If missing → hooks installation (Phase 4) will be skipped

# REQUIRED: Git
git --version
# Expected output: git version 2.x.x

# REQUIRED: pip
python3 -m pip --version
# Expected output: pip XX.X.X from ...
```

### OS Compatibility

| OS | Status | Notes |
|----|--------|-------|
| macOS | ✅ Supported | No extra setup |
| Linux | ✅ Supported | May need `build-essential` for chromadb |
| Windows | ⚠️ WSL only | Run `wsl --install` first, then follow Linux steps inside WSL |

---

## Installation Sequence

### Phase 1: Python Package

**Goal:** Install CloudMem as an editable Python package so the `cloudmem` CLI is available.

```bash
# Step 1a: Clone the repository
git clone https://github.com/raydocs/cloudmem.git
cd cloudmem

# Step 1b: Install in editable mode
pip install -e .

# Step 1c (optional): Install dev dependencies
pip install -e ".[dev]"
```

**Dependencies installed:** `chromadb>=0.4.0,<1.0`, `pyyaml>=6.0`

**Verify Phase 1:**

```bash
cloudmem --help
```

Expected: CLI help text starting with `CloudMem — AI memory with cloud sync`.
If this fails: `pip install -e .` did not complete successfully. Check for chromadb build errors.

**Common failure — chromadb build error:**

```bash
# On macOS, ensure Xcode CLI tools:
xcode-select --install

# On Linux (Debian/Ubuntu):
sudo apt-get install build-essential python3-dev

# Then retry:
pip install -e .
```

---

### Phase 2: Palace Initialization

**Goal:** Create the palace structure from a user's project directory.

**Prerequisite:** Ask the user which project directory to initialize. Do not assume a path.

```bash
# Step 2a: Initialize — detects entities and creates project config
cloudmem init <PROJECT_DIR>
# Replace <PROJECT_DIR> with the user's actual project path
# Example: cloudmem init ~/projects/my-app
#
# This command:
#   - Scans files for entity detection (people, projects)
#   - Creates a mempalace.yaml config
#   - Initializes global config at ~/.cloudmem/config.json
#
# Interactive: may prompt user to confirm detected entities.
# For non-interactive: add --yes flag

# Step 2b: Mine project files into the palace
cloudmem mine <PROJECT_DIR>
# This command:
#   - Reads files from the project directory
#   - Creates structured memory entries (drawers) in ChromaDB
#   - Organizes by wing (project) / room (subdirectory) / closet / drawer
```

**Verify Phase 2:**

```bash
cloudmem status
```

Expected: Output showing filed drawers with wing/room counts. If it says "No palace found", Phase 2 failed.

---

### Phase 3: MCP Server Registration

**Goal:** Register the CloudMem MCP server so the AI client can access memory tools.

CloudMem exposes 48 MCP tools (24 `mempalace_*` + 24 `cloudmem_*` aliases).

**Detect the user's AI client and run the appropriate command:**

```bash
# IF user uses Claude Code:
claude mcp add cloudmem -- python -m cloudmem.mcp_server

# IF user uses Amp:
amp mcp add cloudmem -- python -m cloudmem.mcp_server

# IF user uses another MCP-compatible client:
# The MCP server command is: python -m cloudmem.mcp_server
# It communicates via stdio using JSON-RPC.
# Register this command according to the client's MCP configuration docs.
```

**Verify Phase 3:**

```bash
python -m cloudmem.mcp_server
```

Expected: Process starts and waits for JSON-RPC input on stdin. No errors printed to stderr.
Send a test initialize request to confirm:

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | python -m cloudmem.mcp_server 2>/dev/null | head -1
```

Expected: A JSON response containing `"result"` with server capabilities.

---

### Phase 4: Hooks Installation

**Goal:** Register 3 Claude Code hooks for automatic memory saves.

**Prerequisite:** Node.js 18+ must be installed. If not available, skip this phase and inform the user.

```bash
# Step 4a: Install Node dependencies (from the cloudmem repo root)
npm install

# Step 4b: Run the hooks installer
node bin/install.mjs
```

Expected output:

```
CloudMem hooks installation complete:
- [installed] SessionEnd -> /path/to/cloudmem/hooks/post-session.sh
- [installed] Stop -> /path/to/cloudmem/hooks/mempal_save_hook.sh
- [installed] PreCompact -> /path/to/cloudmem/hooks/mempal_precompact_hook.sh
```

If output shows `[skipped]` instead of `[installed]`, the hooks were already registered.
If output shows `[updated]`, existing hooks were updated to the new path.

**What each hook does:**

| Event | Script | Behavior |
|-------|--------|----------|
| `SessionEnd` | `post-session.sh` | Runs session finalizer: ingest transcript into palace + push to GitHub |
| `Stop` | `mempal_save_hook.sh` | Every 15 human messages, blocks AI to save memories before stopping |
| `PreCompact` | `mempal_precompact_hook.sh` | Always blocks before context compression to save everything |

**Verify Phase 4:**

```bash
python3 -c "
import json
from pathlib import Path
settings = json.loads(Path.home().joinpath('.claude/settings.json').read_text())
hooks = settings.get('hooks', {})
for event in ['SessionEnd', 'Stop', 'PreCompact']:
    entries = hooks.get(event, [])
    print(f'{event}: {len(entries)} hook(s) registered')
"
```

Expected: Each event shows at least 1 hook registered.

---

### Phase 5: Cloud Sync Setup (Optional)

**Goal:** Link the local palace to a private GitHub repo for cross-machine sync.

**Prerequisites:**
- User must have a private GitHub repo (empty or existing)
- SSH key configured for GitHub: test with `ssh -T git@github.com`

**Ask the user for their GitHub repo URL before proceeding.**

```bash
# Step 5a: Initialize sync
cloudmem sync-init git@github.com:<USER>/<REPO>.git
# Replace <USER>/<REPO> with the actual repo

# Step 5b: Push the palace
cloudmem push
```

**Verify Phase 5:**

```bash
cloudmem sync-status
```

Expected: Output showing the remote URL and sync status. Should print `✓` with operation details.

**On a new machine, restore with:**

```bash
cloudmem clone git@github.com:<USER>/<REPO>.git
```

---

### Phase 6: Cloudflare Thread Remote (Optional)

**Goal:** Deploy a remote thread ledger to Cloudflare for always-online access.

**When to set up:** Only if the user wants remote thread storage or a web UI for thread history. Skip if user doesn't mention Cloudflare or remote threads.

**Prerequisites:**
- Cloudflare account
- `npx wrangler` available (included via npm)

```bash
# Step 6a: Deploy Worker + D1 + R2
cd cloudflare
./setup.sh
# Interactive: will prompt for Cloudflare login via wrangler

# Step 6b: Load the generated env vars
source ~/.cloudmem/thread_remote.env

# Step 6c (optional): Deploy web UI
cd cloudflare/pages
npx wrangler pages project create cloudmem-threads-web
npx wrangler pages deploy . --project-name cloudmem-threads-web
```

**Verify Phase 6:**

The env file should contain:

```bash
cat ~/.cloudmem/thread_remote.env
# Expected: CLOUDMEM_THREAD_REMOTE_URL, CLOUDMEM_THREAD_REMOTE_TOKEN, CLOUDMEM_THREAD_REMOTE_HMAC_SECRET
```

---

## Verification Checklist

Run each command. All must pass for a complete installation.

```bash
# 1. CLI is functional
cloudmem --help
# Exit code must be 0

# 2. Palace has content
cloudmem status
# Must show at least one wing with drawers

# 3. MCP server starts
python -m cloudmem.mcp_server &
MCP_PID=$!
sleep 2
kill $MCP_PID 2>/dev/null
# Must start without import errors or crashes

# 4. Hooks are registered (if Node.js was available)
python3 -c "import json; from pathlib import Path; s=json.loads(Path.home().joinpath('.claude/settings.json').read_text()); h=s.get('hooks',{}); assert 'SessionEnd' in h, 'SessionEnd hook missing'; assert 'Stop' in h, 'Stop hook missing'; assert 'PreCompact' in h, 'PreCompact hook missing'; print('All hooks registered')"

# 5. Cloud sync (if configured)
cloudmem sync-status
# Must show connected remote

# 6. Search works
cloudmem search "test"
# Must return without errors (may return 0 results if palace is small)
```

---

## Common Failure Modes

### chromadb build failure

**Symptom:** `pip install -e .` fails with compilation errors mentioning `hnswlib`, `chroma-hnswlib`, or C++ build errors.

**Cause:** Missing C/C++ compiler or build tools.

**Fix:**
```bash
# macOS
xcode-select --install

# Linux (Debian/Ubuntu)
sudo apt-get install build-essential python3-dev

# Then retry
pip install -e .
```

---

### `cloudmem` command not found

**Symptom:** `cloudmem: command not found` after `pip install -e .`

**Cause:** pip scripts directory is not in PATH.

**Fix:**
```bash
# Find where pip installs scripts
python3 -m site --user-base
# Add the bin subdirectory to PATH, e.g.:
export PATH="$(python3 -m site --user-base)/bin:$PATH"

# Or run via module:
python3 -m cloudmem.cli --help
```

---

### MCP server import error

**Symptom:** `python -m cloudmem.mcp_server` fails with `ModuleNotFoundError`.

**Cause:** CloudMem not installed in the active Python environment.

**Fix:**
```bash
# Check which python
which python3

# Verify cloudmem is importable
python3 -c "import cloudmem; print('OK')"

# If not OK, re-install from the repo directory
cd /path/to/cloudmem
pip install -e .
```

---

### Hooks not firing during sessions

**Symptom:** Sessions end without auto-save. No entries in hook log.

**Cause:** Hook scripts not executable, or paths in settings.json are stale.

**Fix:**
```bash
# Check hook scripts are executable
ls -la hooks/*.sh
# All should show -rwxr-xr-x

# If not:
chmod +x hooks/*.sh

# Check hook log for activity
cat ~/.cloudmem/hook_state/hook.log

# Re-run installer to fix paths
node bin/install.mjs
```

---

### Sync push fails with auth error

**Symptom:** `cloudmem push` outputs `✗ failed` with git authentication errors.

**Cause:** SSH key not configured for GitHub, or repo doesn't exist.

**Fix:**
```bash
# Test SSH access
ssh -T git@github.com
# Expected: "Hi <username>! You've successfully authenticated"

# If not configured, generate and add a key:
ssh-keygen -t ed25519 -C "your@email.com"
cat ~/.ssh/id_ed25519.pub
# Add the public key to GitHub → Settings → SSH keys
```

---

### Palace path mismatch (legacy migration)

**Symptom:** Commands work but can't find data from a previous MemPalace installation.

**Cause:** CloudMem uses `~/.cloudmem` while legacy MemPalace used `~/.mempalace`. Migration is automatic for most paths, but some data may remain in the old location.

**Fix:**
```bash
# Check if legacy data exists
ls ~/.mempalace/ 2>/dev/null

# CloudMem will auto-fallback to legacy paths for:
#   - hook_state
#   - identity.txt
#   - entity_registry.json
# But the palace (ChromaDB) should be at ~/.cloudmem/palace
```

---

## Post-Install: First Session Workflow

After installation is complete, the AI agent should:

1. **Run `cloudmem wake-up`** to load L0 (identity) + L1 (essential context).
   If output is empty, onboarding has not been run yet.

2. **If onboarding is needed**, run:
   ```bash
   cloudmem onboard
   ```
   This is interactive — the user will need to provide identity information.

3. **Confirm MCP tools are available.** In the AI session, try calling any `cloudmem_*` or `mempalace_*` tool (e.g., `mempalace_status`). If MCP tools are not available, the server registration (Phase 3) needs to be re-done.

4. **Test memory write → read cycle:**
   - Mine the current project: `cloudmem mine <project-dir>`
   - Search for something just mined: `cloudmem search "<term from the project>"`
   - Confirm results are returned.

5. **If cloud sync is configured**, do a push/pull test:
   ```bash
   cloudmem push
   cloudmem pull
   ```

6. **Report installation status** to the user with:
   - Python version used
   - Number of hooks registered
   - Cloud sync status (connected / not configured)
   - Number of drawers in palace

---

## Data Layout Reference

All persistent state is under `~/.cloudmem` (override with `CLOUDMEM_HOME` env var):

```
~/.cloudmem/
├── config.json              # Global configuration
├── identity.txt             # User identity description
├── entity_registry.json     # Entity shorthand codes
├── known_names.json         # Known name mappings
├── people_map.json          # People relationship map
├── knowledge_graph.sqlite3  # Temporal entity graph
├── palace/                  # ChromaDB vector store (local cache)
├── palace_export.json       # Portable snapshot for sync
├── sessions/                # Session manifests
├── hook_state/              # Hook state files + hook.log
└── threads/                 # Thread ledger
    ├── <thread_id>.json     # Latest snapshot per thread
    └── YYYY/MM/DD/
        ├── index.jsonl       # Append-only daily index
        └── events.jsonl      # Append-only raw events
```

---

## CLI Command Reference

| Command | Description |
|---------|-------------|
| `cloudmem init <dir>` | Detect rooms from folder structure, scan for entities |
| `cloudmem mine <dir>` | Mine project files into palace |
| `cloudmem mine <dir> --mode convos` | Mine conversation exports |
| `cloudmem search "query"` | Semantic search across all memories |
| `cloudmem wake-up` | Show L0 + L1 wake-up context |
| `cloudmem status` | Show filed drawer counts |
| `cloudmem onboard` | Interactive identity + entity + AAAK setup |
| `cloudmem compress` | Compress drawers with AAAK dialect (\~30× reduction) |
| `cloudmem sync-init <url>` | Link to a private GitHub repo |
| `cloudmem sync-status` | Show sync connection status |
| `cloudmem push` | Push palace to GitHub |
| `cloudmem pull` | Pull palace from GitHub |
| `cloudmem clone <url>` | Restore palace on a new machine |
| `cloudmem export` | Export palace to portable JSON |
| `cloudmem import <file>` | Import an AAAK JSON snapshot |
| `cloudmem thread list` | List recent thread logs |
| `cloudmem thread show <id>` | Show a specific thread |
| `cloudmem thread serve` | Local web UI for threads (port 8788) |
