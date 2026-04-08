#!/usr/bin/env python3
"""
CloudMem — AI memory with cloud sync. No API key required.

Two ways to ingest:
  Projects:      cloudmem mine ~/projects/my_app          (code, docs, notes)
  Conversations: cloudmem mine ~/chats/ --mode convos     (Claude, ChatGPT, Slack)

Same palace. Same search. Different ingest strategies.

Commands:
    cloudmem init <dir>                   Detect rooms from folder structure
    cloudmem split <dir>                  Split concatenated mega-files into per-session files
    cloudmem mine <dir>                   Mine project files (default)
    cloudmem mine <dir> --mode convos     Mine conversation exports
    cloudmem search "query"               Find anything, exact words
    cloudmem wake-up                      Show L0 + L1 wake-up context
    cloudmem wake-up --wing my_app        Wake-up for a specific project
    cloudmem status                       Show what's been filed
    cloudmem sync-init <github-url>       Link palace to a private GitHub repo
    cloudmem push                         Push palace to GitHub
    cloudmem pull                         Pull palace from GitHub (same machine, different session)
    cloudmem clone <github-url>           Restore palace on a new machine

Examples:
    cloudmem init ~/projects/my_app
    cloudmem mine ~/projects/my_app
    cloudmem mine ~/.claude/projects/ --mode convos
    cloudmem search "why did we switch to GraphQL"
    cloudmem sync-init git@github.com:you/my-palace.git
    cloudmem push
    cloudmem clone git@github.com:you/my-palace.git   # new machine
"""

import os
import sys
import argparse
from pathlib import Path

from .config import MempalaceConfig


def cmd_init(args):
    import json
    from pathlib import Path
    from .entity_detector import scan_for_detection, detect_entities, confirm_entities
    from cloudmem.project_init import bootstrap_project_config

    # Pass 1: auto-detect people and projects from file content
    print(f"\n  Scanning for entities in: {args.dir}")
    files = scan_for_detection(args.dir)
    if files:
        print(f"  Reading {len(files)} files...")
        detected = detect_entities(files)
        total = len(detected["people"]) + len(detected["projects"]) + len(detected["uncertain"])
        if total > 0:
            confirmed = confirm_entities(detected, yes=getattr(args, "yes", False))
            # Save confirmed entities to <project>/entities.json for the miner
            if confirmed["people"] or confirmed["projects"]:
                entities_path = Path(args.dir).expanduser().resolve() / "entities.json"
                with open(entities_path, "w") as f:
                    json.dump(confirmed, f, indent=2)
                print(f"  Entities saved: {entities_path}")
        else:
            print("  No entities detected — proceeding with directory-based rooms.")

    config_path = bootstrap_project_config(args.dir)
    if config_path.exists():
        print(f"[cloudmem] Project config: {config_path}")

    # Pass 2: initialize config (room detection via folder structure is done at mine time)
    MempalaceConfig().init()
    print(f"  Initialized palace config.")


def cmd_mine(args):
    palace_path = os.path.expanduser(args.palace) if args.palace else MempalaceConfig().palace_path
    quiet = getattr(args, "quiet", False)

    if args.mode == "convos":
        from .convo_miner import mine_convos

        mine_convos(
            convo_dir=args.dir,
            palace_path=palace_path,
            wing=args.wing,
            agent=args.agent,
            limit=args.limit,
            dry_run=args.dry_run,
            extract_mode=args.extract,
            quiet=quiet,
        )
    else:
        from .miner import mine

        mine(
            project_dir=args.dir,
            palace_path=palace_path,
            wing_override=args.wing,
            agent=args.agent,
            limit=args.limit,
            dry_run=args.dry_run,
        )


def cmd_search(args):
    from .searcher import search

    palace_path = os.path.expanduser(args.palace) if args.palace else MempalaceConfig().palace_path
    search(
        query=args.query,
        palace_path=palace_path,
        wing=args.wing,
        room=args.room,
        n_results=args.results,
    )


def cmd_wakeup(args):
    """Show L0 (identity) + L1 (essential story) — the wake-up context."""
    from .layers import MemoryStack

    palace_path = os.path.expanduser(args.palace) if args.palace else MempalaceConfig().palace_path
    stack = MemoryStack(palace_path=palace_path)

    text = stack.wake_up(wing=args.wing)
    tokens = len(text) // 4
    print(f"Wake-up text (~{tokens} tokens):")
    print("=" * 50)
    print(text)


def cmd_split(args):
    """Split concatenated transcript mega-files into per-session files."""
    from .split_mega_files import main as split_main
    import sys

    # Rebuild argv for split_mega_files argparse
    argv = [args.dir]
    if args.output_dir:
        argv += ["--output-dir", args.output_dir]
    if args.dry_run:
        argv.append("--dry-run")
    if args.min_sessions != 2:
        argv += ["--min-sessions", str(args.min_sessions)]

    old_argv = sys.argv
    sys.argv = ["cloudmem split"] + argv
    try:
        split_main()
    finally:
        sys.argv = old_argv


def cmd_status(args):
    from .miner import status

    palace_path = os.path.expanduser(args.palace) if args.palace else MempalaceConfig().palace_path
    status(palace_path=palace_path)


def cmd_onboard(args):
    from .onboarding import run_onboarding

    config_dir = None
    if getattr(args, "config_dir", None):
        config_dir = Path(args.config_dir).expanduser().resolve()

    run_onboarding(
        directory=getattr(args, "directory", "."),
        config_dir=config_dir,
        auto_detect=not getattr(args, "no_auto_detect", False),
    )


def cmd_compress(args):
    """Compress drawers in a wing using AAAK Dialect."""
    from .dialect import Dialect
    from .storage import get_chroma_client, get_collection_name

    palace_path = os.path.expanduser(args.palace) if args.palace else MempalaceConfig().palace_path

    # Load dialect (with optional entity config)
    config_path = args.config
    if not config_path:
        for candidate in ["entities.json", os.path.join(palace_path, "entities.json")]:
            if os.path.exists(candidate):
                config_path = candidate
                break

    if config_path and os.path.exists(config_path):
        dialect = Dialect.from_config(config_path)
        print(f"  Loaded entity config: {config_path}")
    else:
        dialect = Dialect()

    # Connect to palace
    try:
        client = get_chroma_client(Path(palace_path))
        col = client.get_collection(get_collection_name())
    except Exception:
        print(f"\n  No palace found at {palace_path}")
        print("  Run: cloudmem init <dir> then cloudmem mine <dir>")
        sys.exit(1)

    # Query drawers in the wing
    where = {"wing": args.wing} if args.wing else None
    try:
        kwargs = {"include": ["documents", "metadatas"]}
        if where:
            kwargs["where"] = where
        results = col.get(**kwargs)
    except Exception as e:
        print(f"\n  Error reading drawers: {e}")
        sys.exit(1)

    docs = results["documents"]
    metas = results["metadatas"]
    ids = results["ids"]

    if not docs:
        wing_label = f" in wing '{args.wing}'" if args.wing else ""
        print(f"\n  No drawers found{wing_label}.")
        return

    print(
        f"\n  Compressing {len(docs)} drawers"
        + (f" in wing '{args.wing}'" if args.wing else "")
        + "..."
    )
    print()

    total_original = 0
    total_compressed = 0
    compressed_entries = []

    for doc, meta, doc_id in zip(docs, metas, ids):
        compressed = dialect.compress(doc, metadata=meta)
        stats = dialect.compression_stats(doc, compressed)

        total_original += stats["original_chars"]
        total_compressed += stats["compressed_chars"]

        compressed_entries.append((doc_id, compressed, meta, stats))

        if args.dry_run:
            wing_name = meta.get("wing", "?")
            room_name = meta.get("room", "?")
            source = Path(meta.get("source_file", "?")).name
            print(f"  [{wing_name}/{room_name}] {source}")
            print(
                f"    {stats['original_tokens']}t -> {stats['compressed_tokens']}t ({stats['ratio']:.1f}x)"
            )
            print(f"    {compressed}")
            print()

    # Store compressed versions (unless dry-run)
    if not args.dry_run:
        try:
            comp_col = client.get_or_create_collection("mempalace_compressed")
            for doc_id, compressed, meta, stats in compressed_entries:
                comp_meta = dict(meta)
                comp_meta["compression_ratio"] = round(stats["ratio"], 1)
                comp_meta["original_tokens"] = stats["original_tokens"]
                comp_col.upsert(
                    ids=[doc_id],
                    documents=[compressed],
                    metadatas=[comp_meta],
                )
            print(
                f"  Stored {len(compressed_entries)} compressed drawers in 'mempalace_compressed' collection."
            )
        except Exception as e:
            print(f"  Error storing compressed drawers: {e}")
            sys.exit(1)

    # Summary
    ratio = total_original / max(total_compressed, 1)
    orig_tokens = Dialect.count_tokens("x" * total_original)
    comp_tokens = Dialect.count_tokens("x" * total_compressed)
    print(f"  Total: {orig_tokens:,}t -> {comp_tokens:,}t ({ratio:.1f}x compression)")
    if args.dry_run:
        print("  (dry run -- nothing stored)")


def cmd_export(args):
    """Export palace drawers to a portable JSON snapshot."""
    from datetime import datetime
    from .snapshot import export_snapshot

    palace_path = os.path.expanduser(args.palace) if args.palace else MempalaceConfig().palace_path
    output = args.output or f"cloudmem_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    wing_filter = getattr(args, "wing", None)

    try:
        snapshot = export_snapshot(output, palace_path=palace_path, wing=wing_filter)
    except Exception as e:
        print(f"✗ Export failed: {e}")
        sys.exit(1)

    print(f"✓ Exported {snapshot['count']} drawers → {output}")


def cmd_import(args):
    """Import a portable JSON snapshot into the palace (rebuilds ChromaDB embeddings)."""
    import json
    from .snapshot import import_snapshot

    palace_path = os.path.expanduser(args.palace) if args.palace else MempalaceConfig().palace_path
    dry_run = getattr(args, "dry_run", False)

    with open(args.file) as f:
        snapshot = json.load(f)

    drawers = snapshot.get("drawers", [])
    print(f"  Found {len(drawers)} drawers in snapshot (exported: {snapshot.get('exported_at', 'unknown')})")

    if dry_run:
        print(f"  DRY RUN — would import {len(drawers)} drawers into {palace_path}")
        return

    try:
        result = import_snapshot(args.file, palace_path=palace_path, replace=False)
    except Exception as e:
        print(f"✗ Import failed: {e}")
        sys.exit(1)

    print(
        f"✓ Imported {result['imported']} drawers ({result['skipped']} already existed) → {palace_path}"
    )


def cmd_thread_list(args):
    from .thread_ledger import format_thread_line, list_threads

    rows = list_threads(limit=getattr(args, "limit", 20))
    if not rows:
        print("No thread records yet.")
        return

    for row in rows:
        print(format_thread_line(row))


def cmd_thread_show(args):
    import json
    from .thread_ledger import load_thread

    row = load_thread(args.thread_id)
    if row is None:
        print(f"✗ Thread not found: {args.thread_id}")
        sys.exit(1)

    print(json.dumps(row, indent=2, ensure_ascii=False))


def cmd_thread_serve(args):
    from .thread_web import serve_threads

    serve_threads(host=args.host, port=args.port)


def main():
    parser = argparse.ArgumentParser(
        description="CloudMem — AI memory with cloud sync. No API key required.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--palace",
        default=None,
        help="Where the palace lives (default: ~/.cloudmem/palace)",
    )

    sub = parser.add_subparsers(dest="command")

    # init
    p_init = sub.add_parser("init", help="Detect rooms from your folder structure")
    p_init.add_argument("dir", help="Project directory to set up")
    p_init.add_argument(
        "--yes", action="store_true", help="Auto-accept all detected entities (non-interactive)"
    )

    # mine
    p_mine = sub.add_parser("mine", help="Mine files into the palace")
    p_mine.add_argument("dir", help="Directory to mine")
    p_mine.add_argument(
        "--mode",
        choices=["projects", "convos"],
        default="projects",
        help="Ingest mode: 'projects' for code/docs (default), 'convos' for chat exports",
    )
    p_mine.add_argument("--wing", default=None, help="Wing name (default: directory name)")
    p_mine.add_argument(
        "--agent",
        default="mempalace",
        help="Your name — recorded on every drawer", 
    )
    p_mine.add_argument("--limit", type=int, default=0, help="Max files to process (0 = all)")
    p_mine.add_argument(
        "--dry-run", action="store_true", help="Show what would be filed without filing"
    )
    p_mine.add_argument(
        "--quiet", action="store_true", help="Suppress stdout, only log errors to stderr"
    )
    p_mine.add_argument(
        "--extract",
        choices=["exchange", "general"],
        default="exchange",
        help="Extraction strategy for convos mode: 'exchange' (default) or 'general' (5 memory types)",
    )

    # search
    p_search = sub.add_parser("search", help="Find anything, exact words")
    p_search.add_argument("query", help="What to search for")
    p_search.add_argument("--wing", default=None, help="Limit to one project")
    p_search.add_argument("--room", default=None, help="Limit to one room")
    p_search.add_argument("--results", type=int, default=5, help="Number of results")

    # compress
    p_compress = sub.add_parser(
        "compress", help="Compress drawers using AAAK Dialect (~30x reduction)"
    )
    p_compress.add_argument("--wing", default=None, help="Wing to compress (default: all wings)")
    p_compress.add_argument(
        "--dry-run", action="store_true", help="Preview compression without storing"
    )
    p_compress.add_argument(
        "--config", default=None, help="Entity config JSON (e.g. entities.json)"
    )

    # wake-up
    p_wakeup = sub.add_parser("wake-up", help="Show L0 + L1 wake-up context (~600-900 tokens)")
    p_wakeup.add_argument("--wing", default=None, help="Wake-up for a specific project/wing")

    # split
    p_split = sub.add_parser(
        "split",
        help="Split concatenated transcript mega-files into per-session files (run before mine)",
    )
    p_split.add_argument("dir", help="Directory containing transcript files")
    p_split.add_argument(
        "--output-dir",
        default=None,
        help="Write split files here (default: same directory as source files)",
    )
    p_split.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be split without writing files",
    )
    p_split.add_argument(
        "--min-sessions",
        type=int,
        default=2,
        help="Only split files containing at least N sessions (default: 2)",
    )

    # status
    sub.add_parser("status", help="Show what's been filed")

    # onboard
    p_onboard = sub.add_parser(
        "onboard",
        help="Run interactive onboarding to build identity, entity registry, and AAAK entities",
    )
    p_onboard.add_argument(
        "--directory",
        default=".",
        help="Directory to scan for auto-detected entities (default: current directory)",
    )
    p_onboard.add_argument(
        "--config-dir",
        default=None,
        help="Override CloudMem config directory (default: ~/.cloudmem)",
    )
    p_onboard.add_argument(
        "--no-auto-detect",
        action="store_true",
        help="Skip optional file scan for additional entity candidates",
    )

    # sync-init
    p_sync_init = sub.add_parser("sync-init", help="Link CloudMem storage root to a private GitHub repo")
    p_sync_init.add_argument("url", help="GitHub remote URL (SSH or HTTPS)")

    # sync-status
    sub.add_parser("sync-status", help="Show cloud sync status")

    # push
    p_push = sub.add_parser("push", help="Push palace to GitHub")
    p_push.add_argument("--message", "-m", default=None, help="Commit message")

    # pull
    sub.add_parser("pull", help="Pull palace from GitHub")

    # clone
    p_clone = sub.add_parser("clone", help="Restore palace on a new machine")
    p_clone.add_argument("url", help="GitHub remote URL")

    # export
    p_export = sub.add_parser("export", help="Export palace to portable AAAK JSON snapshot")
    p_export.add_argument("--output", "-o", default=None, help="Output file (default: cloudmem_export_YYYYMMDD.json)")
    p_export.add_argument("--wing", default=None, help="Export only this wing")

    # import
    p_import = sub.add_parser("import", help="Import an AAAK JSON snapshot (rebuilds ChromaDB embeddings)")
    p_import.add_argument("file", help="Path to export file")
    p_import.add_argument("--dry-run", action="store_true", help="Preview without importing")

    # thread ledger
    p_thread = sub.add_parser("thread", help="Inspect AMP-style thread logs")
    sub_thread = p_thread.add_subparsers(dest="thread_cmd")

    p_thread_list = sub_thread.add_parser("list", help="List recent threads")
    p_thread_list.add_argument("--limit", type=int, default=20, help="Max rows (default: 20)")

    p_thread_show = sub_thread.add_parser("show", help="Show one thread by id")
    p_thread_show.add_argument("thread_id", help="Thread/session identifier")

    p_thread_serve = sub_thread.add_parser("serve", help="Serve local web UI for threads")
    p_thread_serve.add_argument("--host", default="127.0.0.1", help="Bind host (default 127.0.0.1)")
    p_thread_serve.add_argument("--port", type=int, default=8788, help="Bind port (default 8788)")

    # session-finalize (called by post-session.sh hook, reads stdin JSON)
    p_sf = sub.add_parser("session-finalize", help=argparse.SUPPRESS)
    p_sf.add_argument("--hook-json-stdin", action="store_true",
                      help="Read Claude Code hook JSON from stdin")
    p_sf.add_argument("--session-id", default=None)
    p_sf.add_argument("--transcript", default=None, help="Path to transcript file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    def _sync_cmd(fn_name, *fn_args):
        from .sync import SyncManager
        mgr = SyncManager()
        result = getattr(mgr, fn_name)(*fn_args)
        d = result.to_dict()
        if d.get("ok"):
            print(f"✓ {d.get('operation', fn_name)}", d.get("detail", d.get("message", "")))
        else:
            print(f"✗ {d.get('error', 'failed')}", d.get("hint", d.get("detail", "")),
                  file=sys.stderr)
            sys.exit(1)

    if args.command == "thread":
        if args.thread_cmd == "list":
            cmd_thread_list(args)
            return
        if args.thread_cmd == "show":
            cmd_thread_show(args)
            return
        if args.thread_cmd == "serve":
            cmd_thread_serve(args)
            return
        p_thread.print_help()
        return

    dispatch = {
        "init": cmd_init,
        "mine": cmd_mine,
        "split": cmd_split,
        "search": cmd_search,
        "compress": cmd_compress,
        "wake-up": cmd_wakeup,
        "status": cmd_status,
        "onboard": cmd_onboard,
        "sync-init": lambda a: _sync_cmd("init_sync", a.url),
        "sync-status": lambda a: _sync_cmd("status"),
        "push": lambda a: _sync_cmd("push", a.message),
        "pull": lambda a: _sync_cmd("pull"),
        "clone": lambda a: _sync_cmd("clone", a.url),
        "export": cmd_export,
        "import": cmd_import,
        "session-finalize": lambda a: _cmd_session_finalize(a),
    }
    dispatch[args.command](args)


def _cmd_session_finalize(args):
    """Orchestrate post-session: ingest transcript + push palace."""
    from .session_finalizer import SessionFinalizer

    finalizer = SessionFinalizer()
    ok = finalizer.run(
        hook_json_stdin=getattr(args, "hook_json_stdin", False),
        session_id=getattr(args, "session_id", None),
        transcript_path=getattr(args, "transcript", None),
    )
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
