#!/usr/bin/env python3
"""
VFT Index Rebuilder

Rebuilds the company_index and project_index tables in the ingestion database
from the current deals.json and projects.json files. Run this after manually
editing deal/project records to keep the classifier's matching data current.

Usage:
    python rebuild_index.py
    python rebuild_index.py --db /path/to/ingestion.db --deals /path/to/deals.json --projects /path/to/projects.json
"""

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from slug_utils import slugify  # noqa: E402


def find_repo_root() -> str:
    """Walk up from this script to find the due_diligences root."""
    p = Path(__file__).resolve()
    while p != p.parent:
        if (p / "fund" / "crm" / "deals.json").exists():
            return str(p)
        p = p.parent
    raise FileNotFoundError("Cannot find due_diligences repo root")


def extract_domain(email: str) -> str:
    """Extract domain from an email address."""
    if "@" in email:
        return email.split("@")[-1].lower().strip()
    return email.lower().strip()


def rebuild_company_index(conn: sqlite3.Connection, deals_path: str):
    """Rebuild company_index from deals.json."""
    with open(deals_path, "r") as f:
        data = json.load(f)

    conn.execute("DELETE FROM company_index")

    # Support both flat array and {"companies": [...]} formats
    if isinstance(data, list):
        companies = data
    else:
        companies = data.get("companies", [])

    for company in companies:
        slug = company["slug"]
        name = company.get("company_name", slug)

        # Build domains list from explicit domains + any contact emails
        domains = set()
        for d in company.get("domains", []):
            domains.add(d.lower().strip())
        for email in company.get("contact_emails", []):
            domains.add(extract_domain(email))
        # Also infer domain from slug (common pattern)
        domains.add(f"{slug}.com")

        # Build keywords from name, slug, sector, thesis
        keywords = set()
        keywords.update(slugify(name).split("-"))
        keywords.add(slug)
        if company.get("sector"):
            keywords.update(slugify(company["sector"]).split("-"))
        for kw in company.get("keywords", []):
            keywords.add(kw.lower().strip())

        # Contact emails
        contacts = company.get("contact_emails", [])

        conn.execute(
            """INSERT OR REPLACE INTO company_index
               (company_slug, company_name, domains, keywords, contact_emails, last_touch, stage, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                slug,
                name,
                ",".join(sorted(domains)),
                ",".join(sorted(keywords)),
                ",".join(contacts),
                company.get("last_touch", ""),
                company.get("stage", ""),
                company.get("status", ""),
            ),
        )

    count = conn.execute("SELECT COUNT(*) FROM company_index").fetchone()[0]
    print(f"[VFT] Rebuilt company_index: {count} companies")


def rebuild_project_index(conn: sqlite3.Connection, projects_path: str):
    """Rebuild project_index from projects.json."""
    with open(projects_path, "r") as f:
        data = json.load(f)

    conn.execute("DELETE FROM project_index")

    # Support both flat array and {"projects": [...]} formats
    if isinstance(data, list):
        project_list = data
    else:
        project_list = data.get("projects", [])

    for project in project_list:
        slug = project["slug"]
        name = project.get("project_name", project.get("name", slug))

        # Keywords from name, slug, category, explicit keywords
        keywords = set()
        keywords.update(slugify(name).split("-"))
        keywords.add(slug)
        if project.get("category"):
            keywords.update(slugify(project["category"]).split("-"))
        for kw in project.get("keywords", []):
            keywords.add(kw.lower().strip())

        contacts = project.get("contact_emails", [])

        conn.execute(
            """INSERT OR REPLACE INTO project_index
               (project_slug, project_name, keywords, contact_emails, category, status)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                slug,
                name,
                ",".join(sorted(keywords)),
                ",".join(contacts),
                project.get("category", ""),
                project.get("status", ""),
            ),
        )

    count = conn.execute("SELECT COUNT(*) FROM project_index").fetchone()[0]
    print(f"[VFT] Rebuilt project_index: {count} projects")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rebuild VFT classification indexes")
    parser.add_argument("--db", type=str, help="Path to ingestion.db")
    parser.add_argument("--deals", type=str, help="Path to deals.json")
    parser.add_argument("--projects", type=str, help="Path to projects.json")
    args = parser.parse_args()

    repo_root = find_repo_root()

    db_path = args.db or os.path.join(repo_root, "fund", "metadata", "db", "ingestion.db")
    deals_path = args.deals or os.path.join(repo_root, "fund", "crm", "deals.json")
    projects_path = args.projects or os.path.join(repo_root, "projects", "projects.json")

    if not os.path.exists(db_path):
        print(f"[VFT] Database not found at {db_path}, initializing...")
        from init_db import init_db
        conn = init_db(db_path)
    else:
        conn = sqlite3.connect(db_path)

    rebuild_company_index(conn, deals_path)
    rebuild_project_index(conn, projects_path)

    conn.commit()
    conn.close()
    print("[VFT] Index rebuild complete.")
