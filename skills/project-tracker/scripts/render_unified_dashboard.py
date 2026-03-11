#!/usr/bin/env python3
"""
VFT Unified Dashboard Renderer

Combines deals.json and projects.json into a single dashboard.md
grouped by project type. Optionally includes message counts from
the unified messages table.

Usage:
    python render_unified_dashboard.py
    python render_unified_dashboard.py --output dashboard.md
    python render_unified_dashboard.py --include-message-counts
"""

import argparse
import json
import sqlite3
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DEALS_PATH = REPO_ROOT / "fund" / "crm" / "deals.json"
PROJECTS_PATH = REPO_ROOT / "projects" / "projects.json"
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"


def load_json(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def get_message_counts(db_path: Path) -> dict:
    """Get message counts per project tag from unified messages table."""
    counts = {}
    if not db_path.exists():
        return counts
    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=OFF")
        rows = conn.execute("SELECT project_tags FROM messages WHERE project_tags != '[]'").fetchall()
        for row in rows:
            try:
                tags = json.loads(row[0])
                for tag in tags:
                    counts[tag] = counts.get(tag, 0) + 1
            except (json.JSONDecodeError, TypeError):
                pass

        # Also get last message date per project
        all_msgs = conn.execute(
            "SELECT project_tags, MAX(timestamp) as last_msg FROM messages WHERE project_tags != '[]' GROUP BY project_tags"
        ).fetchall()
        last_dates = {}
        for row in all_msgs:
            try:
                tags = json.loads(row[0])
                for tag in tags:
                    existing = last_dates.get(tag, "")
                    if row[1] and row[1] > existing:
                        last_dates[tag] = row[1]
            except (json.JSONDecodeError, TypeError):
                pass

        conn.close()
        return {"counts": counts, "last_dates": last_dates}
    except Exception:
        return {"counts": {}, "last_dates": {}}


def deal_row(deal: dict, msg_info: dict) -> str:
    raise_amt = deal.get("raise_usd") or 0
    raise_text = f"${raise_amt:,.0f}" if raise_amt else "-"
    msg_count = msg_info.get("counts", {}).get(deal["slug"], 0)
    msg_col = f" {msg_count}" if msg_count else ""
    return (
        f"| {deal.get('company_name', '')} | {deal.get('stage', '')} | "
        f"{deal.get('decision_posture', '')} | {raise_text} | "
        f"{deal.get('priority', '')} | {deal.get('last_touch', '') or '-'} | "
        f"{deal.get('next_action', '') or '-'}{msg_col} |"
    )


def project_row(project: dict, msg_info: dict) -> str:
    msg_count = msg_info.get("counts", {}).get(project["slug"], 0)
    msg_col = f" {msg_count}" if msg_count else ""
    return (
        f"| {project.get('project_name', '')} | {project.get('status', '')} | "
        f"{project.get('priority', '')} | {project.get('owner', '')} | "
        f"{project.get('last_updated', '') or '-'} | "
        f"{project.get('next_action', '') or '-'}{msg_col} |"
    )


def build_unified_dashboard(deals_data: dict, projects_data: dict, msg_info: dict) -> str:
    companies = deals_data.get("companies", [])
    projects = projects_data.get("projects", [])

    # Group projects by type
    by_type = {}
    for p in projects:
        ptype = p.get("project_type", p.get("category", "operations"))
        by_type.setdefault(ptype, []).append(p)

    now = datetime.now()
    stale_threshold = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    lines = [
        "# Unified Dashboard",
        "",
        f"*Last rendered: {now.strftime('%Y-%m-%d %H:%M')}*",
        "",
        "## Summary",
        "",
        f"| Type | Active | Total |",
        f"| --- | --- | --- |",
        f"| Due Diligence | {sum(1 for c in companies if c.get('status') == 'active')} | {len(companies)} |",
    ]

    for ptype in ["hiring", "research", "conversations", "operations"]:
        type_projects = by_type.get(ptype, [])
        active = sum(1 for p in type_projects if p.get("status") not in ("archived", "completed", "closed_hired", "closed_unfilled"))
        lines.append(f"| {ptype.title()} | {active} | {len(type_projects)} |")

    # Uncategorized
    other_types = set(by_type.keys()) - {"hiring", "research", "conversations", "operations"}
    for ptype in sorted(other_types):
        type_projects = by_type[ptype]
        active = sum(1 for p in type_projects if p.get("status") not in ("archived", "completed"))
        lines.append(f"| {ptype.title()} | {active} | {len(type_projects)} |")

    # DD Pipeline
    lines.extend([
        "",
        "---",
        "",
        "## Due Diligence Pipeline",
        "",
        "| Company | Stage | Posture | Raise | Priority | Last Touch | Next Action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ])
    active_deals = [c for c in companies if c.get("status") == "active"]
    active_deals.sort(key=lambda c: c.get("last_touch", "") or "", reverse=True)
    for deal in active_deals:
        lines.append(deal_row(deal, msg_info))

    # Hiring
    hiring = by_type.get("hiring", [])
    if hiring:
        lines.extend([
            "",
            "---",
            "",
            "## Hiring",
            "",
            "| Role | Status | Priority | Owner | Last Updated | Next Action |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for p in sorted(hiring, key=lambda x: x.get("last_updated", "") or "", reverse=True):
            lines.append(project_row(p, msg_info))

    # Research
    research = by_type.get("research", [])
    if research:
        lines.extend([
            "",
            "---",
            "",
            "## Research",
            "",
            "| Project | Status | Priority | Owner | Last Updated | Next Action |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for p in sorted(research, key=lambda x: x.get("last_updated", "") or "", reverse=True):
            lines.append(project_row(p, msg_info))

    # Conversations
    convos = by_type.get("conversations", [])
    if convos:
        lines.extend([
            "",
            "---",
            "",
            "## Conversations",
            "",
            "| Thread | Status | Priority | Owner | Last Updated | Next Action |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for p in sorted(convos, key=lambda x: x.get("last_updated", "") or "", reverse=True):
            lines.append(project_row(p, msg_info))

    # Operations + other
    ops = by_type.get("operations", [])
    for ptype in sorted(other_types):
        ops.extend(by_type[ptype])
    if ops:
        lines.extend([
            "",
            "---",
            "",
            "## Operations & Other",
            "",
            "| Project | Status | Priority | Owner | Last Updated | Next Action |",
            "| --- | --- | --- | --- | --- | --- |",
        ])
        for p in sorted(ops, key=lambda x: x.get("last_updated", "") or "", reverse=True):
            lines.append(project_row(p, msg_info))

    # Needs Attention
    stale_deals = [c for c in active_deals if (c.get("last_touch") or "9999") < stale_threshold]
    stale_projects = [p for p in projects if p.get("status") not in ("archived", "completed", "closed_hired", "closed_unfilled") and (p.get("last_updated") or "9999") < stale_threshold]

    if stale_deals or stale_projects:
        lines.extend([
            "",
            "---",
            "",
            "## Needs Attention",
            "",
            "*Items with no activity in 7+ days:*",
            "",
        ])
        for deal in stale_deals:
            lines.append(f"- **[DD]** {deal['company_name']} — last touch: {deal.get('last_touch', 'never')}")
        for p in stale_projects:
            ptype = p.get("project_type", p.get("category", ""))
            lines.append(f"- **[{ptype}]** {p['project_name']} — last updated: {p.get('last_updated', 'never')}")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Render unified dashboard")
    parser.add_argument("--output", default="dashboard.md")
    parser.add_argument("--include-message-counts", action="store_true", default=True)
    parser.add_argument("--no-message-counts", action="store_false", dest="include_message_counts")
    args = parser.parse_args()

    deals = load_json(DEALS_PATH)
    projects = load_json(PROJECTS_PATH)

    msg_info = {"counts": {}, "last_dates": {}}
    if args.include_message_counts:
        msg_info = get_message_counts(DB_PATH)

    dashboard = build_unified_dashboard(deals, projects, msg_info)

    output_path = REPO_ROOT / args.output
    output_path.write_text(dashboard, encoding="utf-8")
    print(f"[VFT] Unified dashboard written to {output_path}")

    # Also re-render type-specific dashboards
    import subprocess, sys
    dealflow_script = REPO_ROOT / "skills" / "fund-dealflow-orchestrator" / "scripts" / "render_dealflow_dashboard.py"
    project_script = REPO_ROOT / "skills" / "project-management" / "scripts" / "render_project_dashboard.py"

    for script in [dealflow_script, project_script]:
        if script.exists():
            try:
                subprocess.run([sys.executable, str(script)], cwd=str(REPO_ROOT), timeout=30, capture_output=True)
            except Exception as e:
                print(f"[VFT] Warning: {script.name} failed: {e}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
