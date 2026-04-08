# CloudMem Installation Guide

Get AI memory with cloud sync running in under 10 minutes.

---

## Prerequisites

Before you start, make sure you have:

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.9+ (recommend 3.11) | Core engine — memory, compression, MCP server |
| Node.js | 18+ | Hooks installer only (`bin/install.mjs`) |
| Git | Any recent | Clone repo + optional cloud sync |
| pip | Any recent | Python package installer |

Optional:
- A **private GitHub repo** for cloud sync (palace backup across machines)
- A **Cloudflare account** for the remote thread ledger

---

## Step 1: Clone & Install Python Package

```bash
git clone https://github.com/raydocs/cloudmem.git
cd cloudmem
pip install -e .
```

For development / running tests:

```bash
pip install -e ".[dev]"
```

✅ **Verify:** `cloudmem --help` should print the CLI help.

---

## Step 2: Initialize Your First Project

Point CloudMem at a project directory. It will detect rooms from the folder structure and scan for entities (people, projects):

```bash
cloudmem init ~/projects/my-app
```

Then mine the project files into your palace:

```bash
cloudmem mine ~/projects/my-app
```

✅ **Verify:** `cloudmem status` should show drawers filed.

---

## Step 3: Interactive Onboarding

Run the onboarding wizard to set up your identity, entity registry, and AAAK compression entities:

```bash
cloudmem onboard
```

This creates:
- `~/.cloudmem/identity.txt` — who you are
- `~/.cloudmem/entity_registry.json` — people, projects, and shorthand codes
- AAAK dialect configuration for 30× compression

✅ **Verify:** `cloudmem wake-up` should print your L0 + L1 context.

---

## Step 4: Connect MCP Server to Your AI

CloudMem exposes 48 MCP tools (24 `mempalace_*` + 24 `cloudmem_*` aliases).

**For Claude Code:**

```bash
claude mcp add cloudmem -- python -m cloudmem.mcp_server
```

**For Amp:**

```bash
amp mcp add cloudmem -- python -m cloudmem.mcp_server
```

✅ **Verify:** `python -m cloudmem.mcp_server` should start without errors (Ctrl+C to stop).

---

## Step 5: Install Claude Code Hooks

The hooks auto-save memories at key moments during your AI sessions.

```bash
npm install
node bin/install.mjs
```

This registers 3 hooks in `~/.claude/settings.json`:

| Hook | Event | What it does |
|------|-------|--------------|
| `post-session.sh` | **SessionEnd** | Auto-finalize transcript + push to GitHub |
| `mempal_save_hook.sh` | **Stop** | Checkpoint save every 15 exchanges |
| `mempal_precompact_hook.sh` | **PreCompact** | Emergency save before context compression |

✅ **Verify:** Check `~/.claude/settings.json` — you should see entries under `hooks.SessionEnd`, `hooks.Stop`, and `hooks.PreCompact`.

---

## Step 6: Set Up Cloud Sync (Optional)

Sync your palace to a private GitHub repo so it follows you across machines.

**1. Create an empty private repo on GitHub** (e.g., `my-palace`).

**2. Link it:**

```bash
cloudmem sync-init git@github.com:you/my-palace.git
```

**3. Push your palace:**

```bash
cloudmem push
```

**4. On a new machine, restore with:**

```bash
cloudmem clone git@github.com:you/my-palace.git
```

✅ **Verify:** `cloudmem sync-status` should show the remote connected.

---

## Step 7: Cloudflare Thread Remote (Optional)

For an always-online thread ledger with web UI:

```bash
cd cloudflare
./setup.sh
source ~/.cloudmem/thread_remote.env
```

This deploys a Cloudflare Worker + D1 + R2 and configures auth tokens.

See [docs/thread_cloudflare.md](thread_cloudflare.md) for full details.

---

## Final Verification Checklist

Run through these to confirm everything is working:

```bash
# CLI works
cloudmem --help

# Palace has content
cloudmem status

# MCP server starts
python -m cloudmem.mcp_server
# (Ctrl+C to stop)

# Search works
cloudmem search "test query"

# Sync works (if configured)
cloudmem sync-status
```

✅ All commands should exit cleanly without errors.

---

## Troubleshooting

### chromadb install fails

**Symptom:** `pip install -e .` fails on chromadb with build errors.

**Fix:** Make sure you have a C compiler available. On macOS:
```bash
xcode-select --install
```

Or try installing chromadb separately first:
```bash
pip install chromadb>=0.4.0
```

If on an older Python, upgrade to 3.11+:
```bash
python3.11 -m pip install -e .
```

---

### MCP connection issues

**Symptom:** Claude/Amp says the MCP server can't be reached.

**Fix:** Verify the command works standalone:
```bash
python -m cloudmem.mcp_server
```

If it fails with import errors, your `pip install -e .` may not have completed. Re-run it.

Make sure you're using the same Python that has cloudmem installed:
```bash
which python
python -c "import cloudmem; print('OK')"
```

---

### Hooks not firing

**Symptom:** Sessions end without auto-save or sync.

**Fix:**
1. Check that hooks are registered:
   ```bash
   cat ~/.claude/settings.json | python3 -c "import sys,json; h=json.load(sys.stdin).get('hooks',{}); print(json.dumps(h, indent=2))"
   ```
2. Make sure hook scripts are executable:
   ```bash
   ls -la hooks/
   chmod +x hooks/*.sh
   ```
3. Check the hook log:
   ```bash
   cat ~/.cloudmem/hook_state/hook.log
   ```

---

### Sync permission issues

**Symptom:** `cloudmem push` fails with authentication errors.

**Fix:**
- Verify your SSH key is set up for GitHub: `ssh -T git@github.com`
- Make sure the repo is private and you have push access
- If using HTTPS, configure a credential helper:
  ```bash
  git config --global credential.helper osxkeychain  # macOS
  ```

---

### Windows users

CloudMem hooks and shell scripts require a Unix-like environment. Use **WSL** (Windows Subsystem for Linux):
```bash
wsl --install
# Then follow the Linux instructions inside WSL
```

---

## Upgrading

```bash
cd cloudmem
git pull
pip install -e .
```

If hooks have changed, re-run:
```bash
node bin/install.mjs
```

---

## Data Paths

All CloudMem state lives under `~/.cloudmem`:

| Path | Content |
|------|---------|
| `palace/` | Local vector cache (ChromaDB) |
| `identity.txt` | Your identity description |
| `entity_registry.json` | Entity shorthand registry |
| `knowledge_graph.sqlite3` | Temporal entity graph |
| `sessions/` | Session manifests |
| `palace_export.json` | Portable palace snapshot (for sync) |
| `hook_state/` | Hook state + logs |
| `threads/` | Thread ledger data |

---

## Quick Reference

```bash
# Daily usage
cloudmem search "why did we use Postgres"
cloudmem wake-up --wing myapp
cloudmem push

# Mine more content
cloudmem mine ~/projects/another-app
cloudmem mine ~/.claude/projects/ --mode convos

# Thread ledger
cloudmem thread list --limit 20
cloudmem thread show <thread_id>
```

Happy remembering! 🧠
