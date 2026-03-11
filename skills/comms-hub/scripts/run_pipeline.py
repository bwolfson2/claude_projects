#!/usr/bin/env python3
"""
VFT Comms Hub — Master Pipeline Orchestrator

Coordinates all scanners, classification, and dashboard rendering.
Designed to be called by Claude or by scheduled tasks.

Usage:
    python run_pipeline.py                          # Full pipeline
    python run_pipeline.py --scanners outlook,slack  # Specific scanners only
    python run_pipeline.py --project midbound        # Project-specific query
    python run_pipeline.py --classify-only           # Skip scanning, just classify
    python run_pipeline.py --dashboard-only          # Skip scanning/classify, just render
    python run_pipeline.py --dry-run                 # Preview without changes
"""

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
DEALS_PATH = REPO_ROOT / "fund" / "crm" / "deals.json"
PROJECTS_PATH = REPO_ROOT / "projects" / "projects.json"

# Scanner script paths
SCANNERS = {
    "outlook": REPO_ROOT / "skills" / "email-scanner" / "scripts" / "scan_outlook.py",
    "slack": REPO_ROOT / "skills" / "slack-scanner" / "scripts" / "scan_slack.py",
    "whatsapp": REPO_ROOT / "skills" / "whatsapp-scanner" / "scripts" / "scan_whatsapp.py",
    "signal": REPO_ROOT / "skills" / "signal-scanner" / "scripts" / "scan_signal.py",
    "granola": REPO_ROOT / "skills" / "transcript-ingestion" / "scripts" / "ingest_transcripts.py",
}

CLASSIFIER_SCRIPT = REPO_ROOT / "skills" / "deal-project-classifier" / "scripts" / "classify_messages.py"
APPLY_UPDATES_SCRIPT = REPO_ROOT / "skills" / "deal-project-classifier" / "scripts" / "apply_updates.py"
DASHBOARD_SCRIPT = REPO_ROOT / "skills" / "project-tracker" / "scripts" / "render_unified_dashboard.py"
TRACKER_SYNC_SCRIPT = REPO_ROOT / "skills" / "tracker-sync" / "scripts" / "sync_to_xlsx.py"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row
    return conn


def get_message_counts_before() -> dict:
    """Snapshot message counts before scanning."""
    if not DB_PATH.exists():
        return {}
    conn = get_db()
    try:
        rows = conn.execute("SELECT source, COUNT(*) as cnt FROM messages GROUP BY source").fetchall()
        counts = {row["source"]: row["cnt"] for row in rows}
        conn.close()
        return counts
    except Exception:
        conn.close()
        return {}


def get_message_counts_after() -> dict:
    """Snapshot message counts after scanning."""
    return get_message_counts_before()


def run_script(script_path: Path, args: list = None, timeout: int = 120) -> dict:
    """Run a Python script and capture results."""
    if not script_path.exists():
        return {"status": "not_found", "script": str(script_path)}

    cmd = [sys.executable, str(script_path)] + (args or [])
    try:
        result = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            timeout=timeout,
            capture_output=True,
            text=True,
        )
        return {
            "status": "success" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout[-500:] if result.stdout else "",
            "stderr": result.stderr[-500:] if result.stderr else "",
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "script": str(script_path)}
    except Exception as e:
        return {"status": "error", "error": str(e)}


def query_project_messages(project_slug: str) -> dict:
    """Query messages tagged to a specific project."""
    if not DB_PATH.exists():
        return {"messages": [], "count": 0}

    conn = get_db()
    try:
        # SQLite JSON search
        rows = conn.execute(
            "SELECT * FROM messages WHERE project_tags LIKE ? ORDER BY timestamp DESC LIMIT 20",
            (f'%"{project_slug}"%',),
        ).fetchall()

        messages = []
        for row in rows:
            messages.append({
                "id": row["id"],
                "source": row["source"],
                "type": row["type"],
                "subject": row["subject"],
                "sender": row["sender"],
                "timestamp": row["timestamp"],
                "channel": row["channel"],
            })

        conn.close()
        return {"messages": messages, "count": len(messages)}

    except Exception as e:
        conn.close()
        return {"messages": [], "count": 0, "error": str(e)}


def run_pipeline(
    scanners: list = None,
    classify: bool = True,
    dashboard: bool = True,
    project_slug: str = None,
    dry_run: bool = False,
) -> dict:
    """Run the full comms-hub pipeline."""
    results = {
        "timestamp": datetime.now().isoformat(),
        "stages": {},
        "summary": {},
    }

    # Project-specific query mode
    if project_slug:
        project_msgs = query_project_messages(project_slug)
        results["stages"]["project_query"] = project_msgs
        results["summary"] = {
            "mode": "project_query",
            "project": project_slug,
            "message_count": project_msgs["count"],
        }
        return results

    # Full pipeline mode
    counts_before = get_message_counts_before()

    # Stage 1: Scan
    if scanners:
        scan_results = {}
        for scanner_name in scanners:
            if scanner_name in SCANNERS:
                print(f"[VFT] Running {scanner_name} scanner...")
                extra_args = ["--status"] if dry_run else []
                scan_results[scanner_name] = run_script(SCANNERS[scanner_name], extra_args)
            else:
                scan_results[scanner_name] = {"status": "unknown_scanner"}
        results["stages"]["scanning"] = scan_results

    counts_after = get_message_counts_after()

    # Calculate new messages
    new_messages = {}
    for source in set(list(counts_before.keys()) + list(counts_after.keys())):
        before = counts_before.get(source, 0)
        after = counts_after.get(source, 0)
        if after > before:
            new_messages[source] = after - before
    results["stages"]["new_messages"] = new_messages

    # Stage 2: Classify
    if classify and not dry_run:
        print("[VFT] Running classifier...")
        classify_result = run_script(CLASSIFIER_SCRIPT, ["--rebuild-index"])
        results["stages"]["classification"] = classify_result

        # Apply updates
        print("[VFT] Applying updates...")
        apply_result = run_script(APPLY_UPDATES_SCRIPT)
        results["stages"]["apply_updates"] = apply_result

    # Stage 3: Dashboard
    if dashboard:
        print("[VFT] Rendering dashboard...")
        dashboard_result = run_script(DASHBOARD_SCRIPT)
        results["stages"]["dashboard"] = dashboard_result

        # Tracker sync
        if TRACKER_SYNC_SCRIPT.exists() and not dry_run:
            print("[VFT] Syncing tracker...")
            sync_result = run_script(TRACKER_SYNC_SCRIPT)
            results["stages"]["tracker_sync"] = sync_result

    # Summary
    total_new = sum(new_messages.values())
    results["summary"] = {
        "mode": "full_pipeline",
        "total_new_messages": total_new,
        "new_by_source": new_messages,
        "scanners_run": scanners or [],
        "classified": classify,
        "dashboard_rendered": dashboard,
        "dry_run": dry_run,
    }

    return results


def print_summary(results: dict):
    """Print a human-readable pipeline summary."""
    s = results.get("summary", {})
    mode = s.get("mode", "unknown")

    if mode == "project_query":
        print(f"\n[VFT] Project: {s.get('project', '?')}")
        print(f"  Messages found: {s.get('message_count', 0)}")
        msgs = results.get("stages", {}).get("project_query", {}).get("messages", [])
        for msg in msgs[:10]:
            print(f"  [{msg['source']}] {msg['timestamp']} — {msg.get('subject', 'no subject')}")
        return

    print(f"\n[VFT] Pipeline Summary ({results.get('timestamp', '')})")
    print(f"  New messages: {s.get('total_new_messages', 0)}")
    for source, count in s.get("new_by_source", {}).items():
        print(f"    {source}: +{count}")

    if not s.get("total_new_messages"):
        print("  No new messages found.")

    # Print errors from stages
    for stage_name, stage_result in results.get("stages", {}).items():
        if isinstance(stage_result, dict) and stage_result.get("status") == "error":
            print(f"  Warning: {stage_name} had errors")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Comms Hub Pipeline")
    parser.add_argument("--scanners", type=str, default="all",
                        help="Comma-separated scanner names or 'all'")
    parser.add_argument("--classify", action="store_true", default=True)
    parser.add_argument("--no-classify", action="store_false", dest="classify")
    parser.add_argument("--dashboard", action="store_true", default=True)
    parser.add_argument("--no-dashboard", action="store_false", dest="dashboard")
    parser.add_argument("--classify-only", action="store_true")
    parser.add_argument("--dashboard-only", action="store_true")
    parser.add_argument("--project", type=str, help="Query specific project")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    # Parse scanners
    if args.classify_only:
        scanners = None
        args.classify = True
        args.dashboard = True
    elif args.dashboard_only:
        scanners = None
        args.classify = False
        args.dashboard = True
    elif args.scanners == "all":
        scanners = list(SCANNERS.keys())
    elif args.scanners == "none":
        scanners = None
    else:
        scanners = [s.strip() for s in args.scanners.split(",")]

    print(f"[VFT] Comms Hub Pipeline")
    print(f"  Scanners: {scanners or 'none'}")
    print(f"  Classify: {args.classify}")
    print(f"  Dashboard: {args.dashboard}")
    if args.project:
        print(f"  Project filter: {args.project}")
    if args.dry_run:
        print(f"  DRY RUN")

    results = run_pipeline(
        scanners=scanners,
        classify=args.classify,
        dashboard=args.dashboard,
        project_slug=args.project,
        dry_run=args.dry_run,
    )

    print_summary(results)
