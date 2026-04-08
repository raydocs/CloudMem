[English](README.md) | [中文](README_CN.md)

<div align="center">

# 🏛️ CloudMem

**AI memory with cloud sync**

*AAAK compression · Palace architecture · GitHub-backed persistence*

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests: 49 passing](https://img.shields.io/badge/tests-49%20passing-brightgreen?logo=pytest&logoColor=white)]()
[![Version 2.0.0](https://img.shields.io/badge/version-2.0.0-blue)]()
[![MCP Tools: 48](https://img.shields.io/badge/MCP%20tools-48-purple)]()

</div>

---

## The Problem

AI assistants forget everything between sessions. Context windows are expensive and finite. You end up re-explaining your project, your preferences, and your decisions — every single time. **CloudMem** gives your AI a persistent, compressed, searchable memory that syncs to GitHub and follows you to any machine. It uses ~30× lossless AAAK compression so your entire knowledge base fits in a fraction of a context window, and any LLM can read it natively — no special decoder needed.

---

## ✨ Key Features

| | Feature | Description |
|---|---------|-------------|
| 🧠 | **AAAK Compression** | ~30× lossless compression — any LLM reads it natively |
| 🏛️ | **Palace Architecture** | Wing → Room → Closet → Drawer hierarchy, +34% retrieval accuracy |
| 🔌 | **48 MCP Tools** | 24 `mempalace_*` + 24 `cloudmem_*` aliases — full read/write/search/graph access |
| ☁️ | **GitHub Cloud Sync** | Push, pull, or clone your palace to any machine |
| 📊 | **4-Layer Memory Stack** | From always-on identity (50 tokens) to deep semantic search |
| 🪝 | **Auto Hooks** | SessionEnd, Stop, PreCompact — memory saves itself |
| 📓 | **Thread Ledger** | AMP-style per-session tracking with optional Cloudflare remote |
| 🔍 | **Semantic Search** | ChromaDB vector store with local embeddings — no API key needed |
| 📦 | **Portable Snapshots** | Export/import via JSON — not raw Chroma files |
| 🧩 | **Knowledge Graph** | Temporal entity graph in SQLite for relationship tracking |

---

## 🚀 Quick Start

### 1. Install

```bash
pip install -e .

# Dev/test dependencies
pip install -e ".[dev]"

# Node installer for hooks
npm install
```

### 2. Initialize your palace

```bash
# Generate palace config + scan project structure
cloudmem init <project-dir>

# Mine project files into memory
cloudmem mine <project-dir>

# Interactive onboarding (identity, entities, AAAK)
cloudmem onboard
```

### 3. Connect MCP server

```bash
claude mcp add cloudmem -- python -m cloudmem.mcp_server
```

### 4. Link cloud sync

```bash
# Create a private GitHub repo, then:
cloudmem sync-init git@github.com:you/my-palace.git
```

### 5. Install hooks

```bash
node bin/install.mjs
```

That's it. Your AI now remembers everything and syncs to the cloud automatically.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code / LLM                        │
└──────────────┬───────────────────────────────┬──────────────────┘
               │ MCP (48 tools)                │ Hooks
               ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────────┐
│     cloudmem.mcp_server  │    │  SessionEnd · Stop ·         │
│  24 mempalace_* tools    │    │  PreCompact                  │
│  24 cloudmem_* aliases   │    │  → session-finalize          │
└────────────┬─────────────┘    │  → checkpoint save           │
             │                  │  → save before compact       │
             ▼                  └──────────────┬───────────────┘
┌──────────────────────────────────────────────┐
│              CloudMem Core                    │
│                                               │
│  ┌─────────┐ ┌──────────┐ ┌───────────────┐  │
│  │ AAAK    │ │ Layers   │ │ Knowledge     │  │
│  │ Dialect │ │ L0–L3    │ │ Graph (SQLite)│  │
│  └────┬────┘ └────┬─────┘ └───────┬───────┘  │
│       │           │               │           │
│       ▼           ▼               ▼           │
│  ┌────────────────────────────────────────┐   │
│  │  ChromaDB Vector Store (local)        │   │
│  │  Palace: Wing/Room/Closet/Drawer      │   │
│  └────────────────────────────────────────┘   │
└──────────────────┬───────────────────────────┘
                   │
        ┌──────────┼──────────┐
        ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────────────┐
│ JSON     │ │ Git Sync │ │ Thread Ledger    │
│ Snapshot │ │ push/pull│ │ local + optional │
│ Export   │ │ /clone   │ │ Cloudflare remote│
└──────────┘ └────┬─────┘ └──────────────────┘
                  │
                  ▼
          ┌──────────────┐
          │    GitHub     │
          │ Private Repo  │
          └──────────────┘
```

---

## 🧱 Memory Stack

| Layer | Content | Size | Loaded | Description |
|:-----:|---------|:----:|--------|-------------|
| **L0** | Identity | ~50 tokens | Always | Who you are — name, role, preferences |
| **L1** | Critical Facts (AAAK) | ~120 tokens | Always | Key decisions, architecture choices, compressed losslessly |
| **L2** | Room Recall | Variable | On demand | Full room contents when a relevant topic surfaces |
| **L3** | Deep Semantic Search | Variable | On demand | Vector similarity search across entire palace |

> L0 + L1 load automatically on wake-up (~170 tokens total). L2 and L3 activate only when the AI needs deeper context — keeping your token budget lean.

---

## 💻 CLI Reference

| Command | Description |
|---------|-------------|
| `cloudmem init <dir>` | Detect rooms from folder structure, generate config |
| `cloudmem mine <dir>` | Mine files into the palace |
| `cloudmem search <query>` | Semantic search across all memories |
| `cloudmem compress <file>` | Compress a file using AAAK dialect |
| `cloudmem wake-up` | Show L0 + L1 wake-up context |
| `cloudmem split <file>` | Split oversized files into palace-friendly chunks |
| `cloudmem status` | Show what's been filed |
| `cloudmem onboard` | Interactive onboarding (identity, entities, AAAK) |
| `cloudmem sync-init <url>` | Link storage to a private GitHub repo |
| `cloudmem sync-status` | Show cloud sync status |
| `cloudmem push` | Push palace to GitHub |
| `cloudmem pull` | Pull latest palace from GitHub |
| `cloudmem clone <url>` | Restore palace on a new machine |
| `cloudmem export` | Export palace to portable JSON snapshot |
| `cloudmem import <file>` | Import a JSON snapshot (rebuilds embeddings) |
| `cloudmem thread list` | List recent thread summaries |
| `cloudmem thread show <id>` | Show details for a specific thread |
| `cloudmem thread serve` | Launch local web UI for threads (port 8788) |
| `cloudmem session-finalize` | Ingest transcript + sync (called by hooks) |

---

## 🔌 MCP Tools

48 tools total — every `mempalace_*` tool has a `cloudmem_*` alias.

| Group | Tools | Description |
|-------|-------|-------------|
| **Read** | `status`, `list_wings`, `list_rooms`, `get_taxonomy`, `search`, `check_duplicate` | Query palace structure and search memories |
| **Write** | `add_drawer`, `delete_drawer` | File and remove memory entries |
| **Graph** | `traverse`, `find_tunnels`, `graph_stats` | Navigate palace topology and cross-references |
| **Knowledge Graph** | `kg_add_entity`, `kg_add_relation`, `kg_query`, `kg_timeline`, `kg_stats` | Temporal entity graph with relationships |
| **Sync** | `sync_status`, `push`, `pull` | Cloud sync operations via MCP |
| **Thread** | `thread_list`, `thread_show`, `thread_events` | Query thread ledger from within a session |
| **Memory** | `wake_up`, `compress`, `layers_info` | AAAK compression and layer management |

```bash
# Connect to Claude Code
claude mcp add cloudmem -- python -m cloudmem.mcp_server
```

---

## ☁️ Cloud Sync

CloudMem syncs your palace to a private GitHub repository via portable JSON snapshots — not raw ChromaDB files. This means any machine can restore a full palace from the snapshot, rebuilding local embeddings on demand.

```bash
# Initial setup (once)
cloudmem sync-init git@github.com:you/my-palace.git

# Daily workflow (automatic via hooks, or manual)
cloudmem push                # push palace to GitHub
cloudmem pull                # pull latest on same machine
cloudmem clone <url>         # restore on a new machine
```

> **Auto-sync:** The SessionEnd hook runs `session-finalize` which ingests the session transcript and pushes to GitHub automatically. You don't need to remember to sync.

---

## 📓 Thread Ledger

AMP-style per-session tracking — duration, prompts, token/cost stats, diff stats, tool usage, and sync status.

```bash
cloudmem thread list --limit 20       # recent threads
cloudmem thread show <thread_id>      # detailed view
cloudmem thread serve --port 8788     # local web UI
```

### Optional: Cloudflare Remote

Deploy a Cloudflare Worker + D1 + R2 for always-online thread storage:

```bash
cd cloudflare && ./setup.sh
source ~/.cloudmem/thread_remote.env
```

Configure via environment variables:

| Variable | Purpose |
|----------|--------|
| `CLOUDMEM_THREAD_REMOTE_URL` | Worker endpoint URL |
| `CLOUDMEM_THREAD_REMOTE_TOKEN` | Authentication token |
| `CLOUDMEM_THREAD_REMOTE_HMAC_SECRET` | HMAC signing secret |

See [`docs/thread_cloudflare.md`](docs/thread_cloudflare.md) for full setup.

---

## 🪝 Hooks

CloudMem registers three Claude Code hooks via `node bin/install.mjs`:

| Hook | Script | What it does |
|------|--------|--------------|
| **SessionEnd** | `post-session.sh` | Ingests session transcript into palace, pushes to GitHub |
| **Stop** | `mempal_save_hook.sh` | Checkpoint save — reminds AI to persist important findings |
| **PreCompact** | `mempal_precompact_hook.sh` | Saves memory before context compaction to prevent loss |

Hook state is stored in `~/.cloudmem/hook_state`.

---

## 📂 Data Paths

All data lives under `~/.cloudmem`:

```
~/.cloudmem/
├── palace/                    # Local ChromaDB vector cache (rebuildable from snapshot)
├── identity.txt               # User identity description
├── entity_registry.json       # Entity registry
├── knowledge_graph.sqlite3    # Temporal knowledge graph
├── sessions/                  # Session manifests
├── palace_export.json         # Portable sync snapshot
└── hook_state/                # Hook checkpoint state
```

> **Portability:** Cross-machine sync uses the JSON snapshot (`palace_export.json`), not raw ChromaDB files. Embeddings are rebuilt locally on import.

---

## 🖥️ Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| **macOS** | ✅ Fully supported | Primary development platform |
| **Linux** | ✅ Fully supported | All features work |
| **Windows** | ⚠️ Via WSL | Hooks and shell scripts require WSL; native support planned |

**Requirements:**
- Python ≥ 3.9
- `chromadb >= 0.4.0, < 1.0`
- `pyyaml >= 6.0`
- Node.js (for hook installer only)
- Git (for cloud sync)

---

## 🔗 Optional Integrations

- **[claude-session-tracker](https://github.com/ej31/claude-session-tracker)** — Automatically link sessions to GitHub Issues for project tracking. If not installed, sessions still archive normally; issue metadata is simply empty.
- **Cloudflare Worker + D1 + R2** — Remote thread storage with an always-online web UI. See [`docs/thread_cloudflare.md`](docs/thread_cloudflare.md).

---

## 🤝 Contributing

```bash
# Clone and install dev dependencies
git clone https://github.com/raydocs/cloudmem.git
cd cloudmem
pip install -e ".[dev]"
npm install

# Run tests
pytest
```

49 tests, all passing. Please include tests for new features.

---

## 🙏 Credits

- **[MemPalace](https://github.com/milla-jovovich/mempalace)** — Palace structure, AAAK dialect, MCP server foundation
- **[claude-session-tracker](https://github.com/ej31/claude-session-tracker)** — Optional GitHub Issues session tracking integration

---

## 📄 License

[MIT](https://opensource.org/licenses/MIT) © CloudMem Contributors
