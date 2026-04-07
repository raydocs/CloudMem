# CloudMem

**AI memory with cloud sync.**

Combines the AAAK compression and palace structure from [MemPalace](https://github.com/milla-jovovich/mempalace) with the automatic GitHub session backup from [claude-session-tracker](https://github.com/ej31/claude-session-tracker) — plus a new cloud sync layer so your palace lives on GitHub and follows you to any machine.

---

## What it does

| Feature | Source |
|---------|--------|
| Auto-save sessions → GitHub Issues (verbatim backup, human-readable) | claude-session-tracker |
| AAAK compression — 30x, lossless, any LLM reads it | MemPalace |
| Palace structure — Wing / Room / Closet / Drawer, +34% retrieval | MemPalace |
| MCP server — 19 tools, Claude loads context automatically | MemPalace |
| Push palace → GitHub after every session | **CloudMem** |
| Pull / clone palace on a new machine in one command | **CloudMem** |

---

## Quick Start

### 1. Install

```bash
# Python core (memory + compression + MCP)
pip install -e .

# Node installer (GitHub hooks + session backup)
npm install
```

### 2. Set up palace and cloud sync

```bash
# Initialize palace for your project
cloudmem init ~/projects/myapp

# Link to a private GitHub repo (create an empty one first)
cloudmem sync-init git@github.com:you/my-palace.git

# Connect MCP to Claude Code
claude mcp add cloudmem -- python -m cloudmem.mcp_server
```

### 3. Install Claude Code hooks (session backup + auto-push)

```bash
npx cloudmem-install
```

This installs:
- **session-tracker hooks** → every session saved as a GitHub Issue
- **post-session hook** → palace ingested and pushed to GitHub after each session
- **PreCompact hook** → emergency palace save before context compression

---

## Cloud Sync

```bash
# Push palace to GitHub (also runs automatically after each session)
cloudmem push

# Pull latest palace (same machine, different day)
cloudmem pull

# Restore on a new machine
cloudmem clone git@github.com:you/my-palace.git
```

---

## Memory Commands

```bash
# Mine a project
cloudmem mine ~/projects/myapp

# Mine Claude session exports
cloudmem mine ~/.claude/projects/ --mode convos

# Search
cloudmem search "why did we use Postgres"
cloudmem search "auth decision" --wing myapp

# Wake up (AI loads L0+L1, ~170 tokens)
cloudmem wake-up
cloudmem wake-up --wing myapp

# Status
cloudmem status
```

---

## How it works

```
Session ends
    │
    ├─► GitHub Issues (session-tracker)
    │     verbatim backup, human-searchable
    │
    ├─► Palace ingest (MemPalace)
    │     AAAK-compressed, Wing/Room structure
    │
    └─► git push palace → GitHub
          cloud backup, machine-portable

Next session starts
    │
    └─► MCP wake-up (~170 tokens)
          AI knows your history
```

### Memory stack

| Layer | Content | Size | When |
|-------|---------|------|------|
| L0 | Identity | ~50 tokens | Always |
| L1 | Critical facts (AAAK) | ~120 tokens | Always |
| L2 | Room recall | On demand | Topic comes up |
| L3 | Deep semantic search | On demand | Explicit query |

---

## Architecture

```
cloudmem/
├── cloudmem/
│   ├── dialect.py          AAAK compression (from MemPalace)
│   ├── mcp_server.py       19 MCP tools (from MemPalace)
│   ├── convo_miner.py      conversation ingestion (from MemPalace)
│   ├── layers.py           4-layer memory stack (from MemPalace)
│   ├── searcher.py         ChromaDB semantic search (from MemPalace)
│   ├── knowledge_graph.py  temporal entity graph / SQLite (from MemPalace)
│   ├── sync.py             GitHub push/pull/clone (CloudMem)
│   └── cli.py              unified CLI (CloudMem)
├── bin/
│   └── install.mjs         hooks installer (from claude-session-tracker)
├── hooks/
│   ├── post-session.sh     ingest + push after session (CloudMem)
│   └── mempal_*.sh         palace save hooks (from MemPalace)
├── pyproject.toml
└── package.json
```

---

## Credits

- [MemPalace](https://github.com/milla-jovovich/mempalace) — palace structure, AAAK dialect, MCP server
- [claude-session-tracker](https://github.com/ej31/claude-session-tracker) — GitHub Issues session backup, hooks installer

## License

MIT
