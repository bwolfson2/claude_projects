#!/usr/bin/env python3
"""
VFT Apply Updates — Pipeline Updater

Takes classification results from the classification_log and applies them
to deals.json and projects.json. Creates new entries for unmatched items.
Runs tracker-sync at the end to update the Excel master tracker.

Usage:
    python apply_updates.py                # Apply all pending updates
    python apply_updates.py --dry-run      # Preview changes without writing
"""

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
DEALS_PATH = REPO_ROOT / "fund" / "crm" / "deals.json"
PROJECTS_PATH = REPO_ROOT / "projects" / "projects.json"
TRACKER_SYNC = REPO_ROOT / "skills" / "tracker-sync" / "scripts" / "sync_to_xlsx.py"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row
    return conn


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", slug)[:40]


def load_json(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def save_json(path: Path, data: dict):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def infer_company_name(item: dict, source_type: str) -> str:
    """Infer a company name from an email or transcript."""
    if source_type == "email":
        sender = item.get("sender", "")
        domain = item.get("sender_domain", "")
        # Try to get company from domain
        if domain and domain not in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"):
            # Capitalize the domain name part
            name_part = domain.split(".")[0]
            return name_part.capitalize()
        # Fall back to subject
        subject = item.get("subject", "Unknown Company")
        return subject[:40]
    else:
        return item.get("title", "Unknown Meeting")[:40]


def apply_deal_update(deals: dict, slug: str, item: dict, source_type: str) -> bool:
    """Update an existing deal's last_touch and add a note."""
    for company in deals.get("companies", []):
        if company["slug"] == slug:
            company["last_touch"] = datetime.now().strftime("%Y-%m-%d")
            # Don't overwrite existing next_action — just update touch date
            return True
    return False


def create_new_deal(deals: dict, item: dict, source_type: str) -> str:
    """Create a new deal entry from an unmatched item."""
    name = infer_company_name(item, source_type)
    slug = slugify(name)

    # Ensure unique slug
    existing_slugs = {c["slug"] for c in deals.get("companies", [])}
    base_slug = slug
    counter = 2
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1

    new_deal = {
        "slug": slug,
        "company_name": name,
        "status": "active",
        "stage": "sourced",
        "owner": "fund",
        "source": f"auto_{source_type}_scanner",
        "sector": "",
        "round": "",
        "raise_usd": 0,
        "valuation_cap_usd": 0,
        "decision_posture": "pending_review",
        "priority": "medium",
        "last_touch": datetime.now().strftime("%Y-%m-%d"),
        "next_action": "Review auto-created deal entry and complete details",
        "next_action_owner": "fund",
        "next_action_due": "",
        "thesis": "",
        "open_questions": [f"Auto-created from {source_type} — needs review"],
        "assumptions": [],
        "artifacts": {},
        "diligence": {
            "commercial": "not_started",
            "product_technical": "not_started",
            "finance_legal": "not_started",
            "memo": "not_started",
        },
    }

    if "companies" not in deals:
        deals["companies"] = []
    deals["companies"].append(new_deal)

    return slug


def create_new_project(projects: dict, item: dict, source_type: str) -> str:
    """Create a new project entry from an unmatched item."""
    if source_type == "email":
        name = item.get("subject", "Untitled Project")[:60]
    else:
        name = item.get("title", "Untitled Project")[:60]

    slug = slugify(name)

    existing_slugs = {p["slug"] for p in projects.get("projects", [])}
    base_slug = slug
    counter = 2
    while slug in existing_slugs:
        slug = f"{base_slug}-{counter}"
        counter += 1

    new_project = {
        "slug": slug,
        "project_name": name,
        "name": name,
        "category": "uncategorized",
        "status": "active",
        "priority": "medium",
        "owner": "fund",
        "created": datetime.now().strftime("%Y-%m-%d"),
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "description": f"Auto-created from {source_type} — needs review",
        "keywords": [],
        "contact_emails": [],
    }

    if "projects" not in projects:
        projects["projects"] = []
    projects["projects"].append(new_project)

    return slug


def apply_all_updates(dry_run: bool = False) -> dict:
    """Apply all pending classification results to the pipeline."""
    conn = get_db()

    # Get unprocessed classifications (multi-match aware: join on cl.id not source_id)
    pending = conn.execute(
        """SELECT cl.*
           FROM classification_log cl
           LEFT JOIN processed_items pi
             ON pi.source_type = cl.source_type
             AND pi.source_id = cl.source_id
             AND pi.action_taken = 'applied_' || cl.id
           WHERE pi.id IS NULL
           ORDER BY cl.created_at"""
    ).fetchall()

    if not pending:
        print("[VFT] No pending classifications to apply.")
        return {"applied": 0}

    deals = load_json(DEALS_PATH)
    projects = load_json(PROJECTS_PATH)

    stats = {
        "deal_updates": 0,
        "project_updates": 0,
        "new_deals": [],
        "new_projects": [],
        "skipped": 0,
    }

    for cl in pending:
        source_type = cl["source_type"]
        source_id = cl["source_id"]
        match_type = cl["match_type"]
        matched_slug = cl["matched_slug"]

        # Fetch the original item
        if source_type == "email":
            item = conn.execute("SELECT * FROM emails WHERE id = ?", (source_id,)).fetchone()
        else:
            item = conn.execute("SELECT * FROM transcripts WHERE id = ?", (source_id,)).fetchone()

        if not item:
            stats["skipped"] += 1
            continue

        item = dict(item)

        if match_type == "deal" and matched_slug:
            if apply_deal_update(deals, matched_slug, item, source_type):
                stats["deal_updates"] += 1
            else:
                stats["skipped"] += 1

        elif match_type == "project" and matched_slug:
            # Update project last_updated
            for p in projects.get("projects", []):
                if p["slug"] == matched_slug:
                    p["last_updated"] = datetime.now().strftime("%Y-%m-%d")
                    stats["project_updates"] += 1
                    break

        elif match_type == "new_deal":
            if not os.environ.get("VFT_NO_AUTO_CREATE"):
                slug = create_new_deal(deals, item, source_type)
                stats["new_deals"].append(slug)
                # Update the classification log with the new slug
                if not dry_run:
                    conn.execute(
                        "UPDATE classification_log SET matched_slug = ?, auto_created = 1 WHERE id = ?",
                        (slug, cl["id"]),
                    )
            else:
                stats["skipped"] += 1

        elif match_type == "new_project":
            if not os.environ.get("VFT_NO_AUTO_CREATE"):
                slug = create_new_project(projects, item, source_type)
                stats["new_projects"].append(slug)
                if not dry_run:
                    conn.execute(
                        "UPDATE classification_log SET matched_slug = ?, auto_created = 1 WHERE id = ?",
                        (slug, cl["id"]),
                    )
            else:
                stats["skipped"] += 1

        # Mark this specific classification entry as processed
        if not dry_run:
            conn.execute(
                """INSERT OR IGNORE INTO processed_items
                   (source_type, source_id, action_taken)
                   VALUES (?, ?, ?)""",
                (source_type, source_id, f"applied_{cl['id']}"),
            )

    if not dry_run:
        # Save updated files
        deals["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        save_json(DEALS_PATH, deals)

        projects["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        save_json(PROJECTS_PATH, projects)

        conn.commit()

        # Run tracker sync if available
        if TRACKER_SYNC.exists():
            print("[VFT] Running tracker sync...")
            try:
                subprocess.run(
                    [sys.executable, str(TRACKER_SYNC)],
                    cwd=str(REPO_ROOT),
                    timeout=60,
                )
            except Exception as e:
                print(f"[VFT] Tracker sync warning: {e}")

    conn.close()
    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Apply Updates")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    prefix = "[DRY RUN] " if args.dry_run else ""
    print(f"{prefix}[VFT] Applying classification updates...")

    stats = apply_all_updates(dry_run=args.dry_run)

    print(f"\n{prefix}[VFT] Update Results:")
    print(f"  Deal updates: {stats.get('deal_updates', 0)}")
    print(f"  Project updates: {stats.get('project_updates', 0)}")
    print(f"  New deals created: {stats.get('new_deals', [])}")
    print(f"  New projects created: {stats.get('new_projects', [])}")
    print(f"  Skipped: {stats.get('skipped', 0)}")
