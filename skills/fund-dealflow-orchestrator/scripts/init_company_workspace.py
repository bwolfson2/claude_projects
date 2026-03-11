#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, contents: str, force: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return
    path.write_text(contents, encoding="utf-8")


def load_registry(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "fund_name": "Fund",
        "last_updated": date.today().isoformat(),
        "companies": [],
    }


def ensure_company(registry: dict, record: dict) -> None:
    for company in registry["companies"]:
        if company["slug"] == record["slug"]:
            return
    registry["companies"].append(record)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a company workspace and seed the deal registry.")
    parser.add_argument("--name", required=True, help="Company name")
    parser.add_argument("--slug", required=True, help="Slug used in fund/companies/<slug>")
    parser.add_argument("--stage", default="sourced")
    parser.add_argument("--status", default="active")
    parser.add_argument("--owner", default="unassigned")
    parser.add_argument("--source", default="")
    parser.add_argument("--sector", default="")
    parser.add_argument("--round", default="")
    parser.add_argument("--raise-usd", type=int, default=0)
    parser.add_argument("--valuation-cap-usd", type=int, default=0)
    parser.add_argument("--priority", default="medium")
    parser.add_argument("--decision-posture", default="open")
    parser.add_argument("--fund-root", default="fund")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    repo_root = Path.cwd()
    skill_root = repo_root / "skills" / "fund-dealflow-orchestrator"
    fund_root = repo_root / args.fund_root
    company_root = fund_root / "companies" / args.slug
    registry_path = fund_root / "crm" / "deals.json"

    company_template = load_template(skill_root / "assets" / "company-record-template.md")
    next_actions_template = load_template(skill_root / "assets" / "next-actions-template.md")
    ic_template = load_template(skill_root / "assets" / "ic-snapshot-template.md")

    company_md = company_template.replace("{{company_name}}", args.name)

    write_text(company_root / "company.md", company_md, args.force)
    write_text(company_root / "next-actions.md", next_actions_template, args.force)
    write_text(company_root / "diligence" / "ic-snapshot.md", ic_template, args.force)
    write_text(company_root / "meetings" / "notes.md", "# Meeting Notes\n", args.force)

    registry = load_registry(registry_path)
    record = {
        "slug": args.slug,
        "company_name": args.name,
        "status": args.status,
        "stage": args.stage,
        "owner": args.owner,
        "source": args.source,
        "sector": args.sector,
        "round": args.round,
        "raise_usd": args.raise_usd,
        "valuation_cap_usd": args.valuation_cap_usd,
        "decision_posture": args.decision_posture,
        "priority": args.priority,
        "last_touch": "",
        "next_action": "",
        "next_action_owner": "",
        "next_action_due": "",
        "thesis": "",
        "open_questions": [],
        "assumptions": [],
        "artifacts": {
            "company_workspace": str(company_root),
            "meeting_notes": str(company_root / "meetings" / "notes.md"),
            "ic_note": str(company_root / "diligence" / "ic-snapshot.md"),
        },
        "diligence": {
            "commercial": "not_started",
            "product_technical": "not_started",
            "finance_legal": "not_started",
            "memo": "not_started",
        },
    }
    ensure_company(registry, record)
    registry["last_updated"] = date.today().isoformat()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
