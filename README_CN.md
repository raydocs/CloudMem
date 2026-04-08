[English](README.md) | [中文](README_CN.md)

<div align="center">

# 🏛️ CloudMem

**AI 记忆，云端同步**

*AAAK 压缩 · 宫殿式架构 · GitHub 持久化存储*

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests: 49 passing](https://img.shields.io/badge/tests-49%20passing-brightgreen?logo=pytest&logoColor=white)]()
[![Version 2.0.0](https://img.shields.io/badge/version-2.0.0-blue)]()
[![MCP Tools: 48](https://img.shields.io/badge/MCP%20tools-48-purple)]()

</div>

---

## 问题背景

AI 助手在会话之间会遗忘一切。上下文窗口既昂贵又有限。你不得不一遍又一遍地重新解释你的项目、偏好和决策。**CloudMem** 为你的 AI 提供了一套持久化、可压缩、可搜索的记忆系统，能自动同步到 GitHub，并跟随你到任何设备。它使用约 30 倍的 AAAK 无损压缩，让你的整个知识库只占上下文窗口的极小部分，且任何 LLM 都能原生读取——无需专门的解码器。

---

## ✨ 核心特性

| | 特性 | 说明 |
|---|------|------|
| 🧠 | **AAAK 压缩** | 约 30 倍无损压缩——任何 LLM 均可原生读取 |
| 🏛️ | **宫殿架构** | Wing → Room → Closet → Drawer 层级结构，检索准确率提升 34% |
| 🔌 | **48 个 MCP 工具** | 24 个 `mempalace_*` + 24 个 `cloudmem_*` 别名——完整的读写/搜索/图谱访问 |
| ☁️ | **GitHub 云同步** | 推送、拉取，或将宫殿克隆到任意设备 |
| 📊 | **四层记忆栈** | 从始终加载的身份信息（50 token）到深度语义搜索 |
| 🪝 | **自动钩子** | SessionEnd、Stop、PreCompact——记忆自动保存 |
| 📓 | **线程账本** | AMP 风格的按会话追踪，可选 Cloudflare 远程存储 |
| 🔍 | **语义搜索** | 基于 ChromaDB 向量存储与本地嵌入——无需 API 密钥 |
| 📦 | **可移植快照** | 通过 JSON 导出/导入——而非原始 Chroma 文件 |
| 🧩 | **知识图谱** | 基于 SQLite 的时序实体图谱，用于关系追踪 |

---

## 🚀 快速开始

### 1. 安装

```bash
pip install -e .

# 开发/测试依赖
pip install -e ".[dev]"

# Node 安装器（用于钩子）
npm install
```

### 2. 初始化宫殿

```bash
# 生成宫殿配置 + 扫描项目结构
cloudmem init <project-dir>

# 将项目文件挖掘到记忆中
cloudmem mine <project-dir>

# 交互式引导（身份、实体、AAAK）
cloudmem onboard
```

### 3. 连接 MCP 服务器

```bash
claude mcp add cloudmem -- python -m cloudmem.mcp_server
```

### 4. 关联云同步

```bash
# 先创建一个 GitHub 私有仓库，然后：
cloudmem sync-init git@github.com:you/my-palace.git
```

### 5. 安装钩子

```bash
node bin/install.mjs
```

大功告成。你的 AI 现在会记住一切，并自动同步到云端。

---

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code / LLM                        │
└──────────────┬───────────────────────────────────┬──────────────┘
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

## 🧱 记忆栈

| 层级 | 内容 | 大小 | 加载时机 | 说明 |
|:----:|------|:----:|----------|------|
| **L0** | 身份信息 | ~50 token | 始终加载 | 你是谁——姓名、角色、偏好 |
| **L1** | 关键事实（AAAK） | ~120 token | 始终加载 | 关键决策、架构选型，经无损压缩 |
| **L2** | 房间回溯 | 可变 | 按需加载 | 当相关主题出现时，加载完整房间内容 |
| **L3** | 深度语义搜索 | 可变 | 按需加载 | 在整个宫殿中进行向量相似度搜索 |

> L0 + L1 在唤醒时自动加载（共约 170 token）。L2 和 L3 仅在 AI 需要更深层上下文时激活——让你的 token 预算保持精简。

---

## 💻 CLI 命令参考

| 命令 | 说明 |
|------|------|
| `cloudmem init <dir>` | 根据目录结构检测房间，生成配置 |
| `cloudmem mine <dir>` | 将文件挖掘到宫殿中 |
| `cloudmem search <query>` | 在所有记忆中进行语义搜索 |
| `cloudmem compress <file>` | 使用 AAAK 方言压缩文件 |
| `cloudmem wake-up` | 显示 L0 + L1 唤醒上下文 |
| `cloudmem split <file>` | 将超大文件拆分为宫殿友好的分块 |
| `cloudmem status` | 显示已归档内容 |
| `cloudmem onboard` | 交互式引导（身份、实体、AAAK） |
| `cloudmem sync-init <url>` | 将存储关联到 GitHub 私有仓库 |
| `cloudmem sync-status` | 显示云同步状态 |
| `cloudmem push` | 将宫殿推送到 GitHub |
| `cloudmem pull` | 从 GitHub 拉取最新宫殿 |
| `cloudmem clone <url>` | 在新设备上恢复宫殿 |
| `cloudmem export` | 将宫殿导出为可移植 JSON 快照 |
| `cloudmem import <file>` | 导入 JSON 快照（会重建嵌入） |
| `cloudmem thread list` | 列出近期线程摘要 |
| `cloudmem thread show <id>` | 查看指定线程详情 |
| `cloudmem thread serve` | 启动线程本地 Web 界面（端口 8788） |
| `cloudmem session-finalize` | 摄取会话记录并同步（由钩子调用） |

---

## 🔌 MCP 工具

共 48 个工具——每个 `mempalace_*` 工具都有对应的 `cloudmem_*` 别名。

| 分组 | 工具 | 说明 |
|------|------|------|
| **读取** | `status`, `list_wings`, `list_rooms`, `get_taxonomy`, `search`, `check_duplicate` | 查询宫殿结构与搜索记忆 |
| **写入** | `add_drawer`, `delete_drawer` | 存入和删除记忆条目 |
| **图谱导航** | `traverse`, `find_tunnels`, `graph_stats` | 浏览宫殿拓扑与交叉引用 |
| **知识图谱** | `kg_add_entity`, `kg_add_relation`, `kg_query`, `kg_timeline`, `kg_stats` | 带关系的时序实体图谱 |
| **同步** | `sync_status`, `push`, `pull` | 通过 MCP 进行云同步操作 |
| **线程** | `thread_list`, `thread_show`, `thread_events` | 在会话中查询线程账本 |
| **记忆** | `wake_up`, `compress`, `layers_info` | AAAK 压缩与层级管理 |

```bash
# 连接到 Claude Code
claude mcp add cloudmem -- python -m cloudmem.mcp_server
```

---

## ☁️ 云同步

CloudMem 通过可移植的 JSON 快照将宫殿同步到 GitHub 私有仓库——而非原始 ChromaDB 文件。这意味着任何设备都可以从快照恢复完整宫殿，并按需重建本地嵌入。

```bash
# 初始设置（仅需一次）
cloudmem sync-init git@github.com:you/my-palace.git

# 日常工作流（通过钩子自动执行，也可手动操作）
cloudmem push                # 将宫殿推送到 GitHub
cloudmem pull                # 在同一设备上拉取最新版本
cloudmem clone <url>         # 在新设备上恢复
```

> **自动同步：** SessionEnd 钩子会运行 `session-finalize`，自动摄取会话记录并推送到 GitHub。你无需手动同步。

---

## 📓 线程账本

AMP 风格的按会话追踪——包括持续时间、提示数、token/费用统计、diff 统计、工具使用情况及同步状态。

```bash
cloudmem thread list --limit 20       # 近期线程
cloudmem thread show <thread_id>      # 详细视图
cloudmem thread serve --port 8788     # 本地 Web 界面
```

### 可选：Cloudflare 远程存储

部署 Cloudflare Worker + D1 + R2，实现始终在线的线程存储：

```bash
cd cloudflare && ./setup.sh
source ~/.cloudmem/thread_remote.env
```

通过环境变量配置：

| 变量 | 用途 |
|------|------|
| `CLOUDMEM_THREAD_REMOTE_URL` | Worker 端点 URL |
| `CLOUDMEM_THREAD_REMOTE_TOKEN` | 认证令牌 |
| `CLOUDMEM_THREAD_REMOTE_HMAC_SECRET` | HMAC 签名密钥 |

完整设置请参阅 [`docs/thread_cloudflare.md`](docs/thread_cloudflare.md)。

---

## 🪝 钩子

CloudMem 通过 `node bin/install.mjs` 注册三个 Claude Code 钩子：

| 钩子 | 脚本 | 功能 |
|------|------|------|
| **SessionEnd** | `post-session.sh` | 将会话记录摄取到宫殿中，并推送到 GitHub |
| **Stop** | `mempal_save_hook.sh` | 检查点保存——提醒 AI 持久化重要发现 |
| **PreCompact** | `mempal_precompact_hook.sh` | 在上下文压缩前保存记忆，防止丢失 |

钩子状态存储在 `~/.cloudmem/hook_state` 中。

---

## 📂 数据路径

所有数据存放在 `~/.cloudmem` 下：

```
~/.cloudmem/
├── palace/                    # 本地 ChromaDB 向量缓存（可从快照重建）
├── identity.txt               # 用户身份描述
├── entity_registry.json       # 实体注册表
├── knowledge_graph.sqlite3    # 时序知识图谱
├── sessions/                  # 会话清单
├── palace_export.json         # 可移植同步快照
└── hook_state/                # 钩子检查点状态
```

> **可移植性：** 跨设备同步使用 JSON 快照（`palace_export.json`），而非原始 ChromaDB 文件。嵌入在导入时本地重建。

---

## 🖥️ 平台支持

| 平台 | 状态 | 备注 |
|------|------|------|
| **macOS** | ✅ 完全支持 | 主要开发平台 |
| **Linux** | ✅ 完全支持 | 所有功能正常 |
| **Windows** | ⚠️ 需通过 WSL | 钩子和 Shell 脚本需要 WSL；原生支持计划中 |

**环境要求：**
- Python ≥ 3.9
- `chromadb >= 0.4.0, < 1.0`
- `pyyaml >= 6.0`
- Node.js（仅用于钩子安装）
- Git（用于云同步）

---

## 🔗 可选集成

- **[claude-session-tracker](https://github.com/ej31/claude-session-tracker)** — 自动将会话关联到 GitHub Issues，便于项目追踪。未安装时会话仍可正常归档，仅 Issue 元数据为空。
- **Cloudflare Worker + D1 + R2** — 远程线程存储，提供始终在线的 Web 界面。详见 [`docs/thread_cloudflare.md`](docs/thread_cloudflare.md)。

---

## 🤝 参与贡献

```bash
# 克隆并安装开发依赖
git clone https://github.com/raydocs/cloudmem.git
cd cloudmem
pip install -e ".[dev]"
npm install

# 运行测试
pytest
```

49 个测试，全部通过。提交新功能时请附带测试。

---

## 🙏 致谢

- **[MemPalace](https://github.com/milla-jovovich/mempalace)** — 宫殿结构、AAAK 方言、MCP 服务器基础
- **[claude-session-tracker](https://github.com/ej31/claude-session-tracker)** — 可选的 GitHub Issues 会话追踪集成

---

## 📄 许可证

[MIT](https://opensource.org/licenses/MIT) © CloudMem Contributors
