#!/usr/bin/env python3
"""
VFT Project Init — Universal Project Workspace Scaffolder

Creates typed project workspaces from templates and seeds the appropriate registry.
Supports: dd, hiring, research, conversations, operations.

Usage:
    python init_project_workspace.py --type hiring --name "Senior Engineer"
    python init_project_workspace.py --type dd --name "Acme Corp" --sector "B2B SaaS"
    python init_project_workspace.py --type research --name "AI Infrastructure Market"
    python init_project_workspace.py --type conversations --name "John Smith"
    python init_project_workspace.py --type operations --name "Office Move"
"""

import argparse
import json
import re
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATES_ROOT = SKILL_ROOT / "assets" / "templates"

DEALS_PATH = REPO_ROOT / "fund" / "crm" / "deals.json"
PROJECTS_PATH = REPO_ROOT / "projects" / "projects.json"

VALID_TYPES = {"dd", "hiring", "research", "conversations", "operations"}

# Map project type to base path
TYPE_PATHS = {
    "dd": REPO_ROOT / "fund" / "companies",
    "hiring": REPO_ROOT / "projects" / "hiring",
    "research": REPO_ROOT / "projects" / "research",
    "conversations": REPO_ROOT / "projects" / "conversations",
    "operations": REPO_ROOT / "projects" / "operations",
}

# Map project type to lifecycle stages
TYPE_LIFECYCLES = {
    "dd": ["sourced", "screening", "first_meeting", "dataroom", "deep_diligence", "ic_prep", "decision"],
    "hiring": ["open", "sourcing", "screening", "interviewing", "offer", "closed_hired", "closed_unfilled"],
    "research": ["scoping", "active", "synthesis", "published", "archived"],
    "conversations": ["active", "dormant", "archived"],
    "operations": ["active", "blocked", "completed", "archived"],
}

# Folder structures per type (beyond what templates provide)
TYPE_FOLDERS = {
    "dd": ["meetings", "diligence", "messages", "dataroom", "research"],
    "hiring": ["candidates", "messages", "research", "templates"],
    "research": ["sources", "data", "outputs", "messages"],
    "conversations": ["messages", "shared-docs"],
    "operations": ["messages", "docs", "research"],
}


def slugify(name: str) -> str:
    """Generate a URL-friendly slug from a name."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:60]


def load_template(path: Path, replacements: dict) -> str:
    """Load a template file and apply replacements."""
    content = path.read_text(encoding="utf-8")
    for key, value in replacements.items():
        content = content.replace(f"{{{{{key}}}}}", value)
    return content


def write_file(path: Path, content: str, force: bool = False) -> bool:
    """Write a file, creating parent dirs. Returns True if written."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not force:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def load_registry(path: Path, key: str) -> dict:
    """Load a JSON registry file."""
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    base = {
        "schema_version": 1,
        "fund_name": "Fund",
        "last_updated": date.today().isoformat(),
    }
    base[key] = []
    return base


def slug_exists(registry: dict, slug: str, key: str) -> bool:
    """Check if a slug already exists in the registry."""
    for item in registry.get(key, []):
        if item.get("slug") == slug:
            return True
    return False


def init_dd(name: str, slug: str, args) -> dict:
    """Scaffold a DD workspace."""
    workspace = TYPE_PATHS["dd"] / slug
    replacements = {"company_name": name, "project_name": name}

    # Create template files
    template_dir = TEMPLATES_ROOT / "dd"
    for tmpl in template_dir.glob("*.md"):
        content = load_template(tmpl, replacements)
        write_file(workspace / tmpl.name, content, args.force)

    # Create subfolders
    for folder in TYPE_FOLDERS["dd"]:
        (workspace / folder).mkdir(parents=True, exist_ok=True)

    # Create IC snapshot from dealflow orchestrator template if available
    ic_template = REPO_ROOT / "skills" / "fund-dealflow-orchestrator" / "assets" / "ic-snapshot-template.md"
    if ic_template.exists():
        write_file(workspace / "diligence" / "ic-snapshot.md", ic_template.read_text(), args.force)

    write_file(workspace / "meetings" / "notes.md", "# Meeting Notes\n", args.force)

    # Seed deals.json
    registry = load_registry(DEALS_PATH, "companies")
    if slug_exists(registry, slug, "companies"):
        print(f"[VFT] Deal '{slug}' already exists in registry, skipping seed.")
    else:
        record = {
            "slug": slug,
            "company_name": name,
            "status": "active",
            "stage": "sourced",
            "owner": args.owner,
            "source": args.source or "manual",
            "domains": [],
            "contact_emails": [],
            "sector": args.sector or "",
            "round": "",
            "raise_usd": 0,
            "valuation_cap_usd": 0,
            "decision_posture": "open",
            "priority": args.priority,
            "last_touch": date.today().isoformat(),
            "next_action": "Review initial materials and determine fit",
            "next_action_owner": args.owner,
            "next_action_due": "",
            "thesis": "",
            "open_questions": [],
            "assumptions": [],
            "artifacts": {
                "company_workspace": str(workspace),
                "meeting_notes": str(workspace / "meetings" / "notes.md"),
                "ic_note": str(workspace / "diligence" / "ic-snapshot.md"),
            },
            "diligence": {
                "commercial": "not_started",
                "product_technical": "not_started",
                "finance_legal": "not_started",
                "memo": "not_started",
            },
        }
        registry["companies"].append(record)
        registry["last_updated"] = date.today().isoformat()
        DEALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEALS_PATH.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
        print(f"[VFT] Seeded deal record for '{slug}' in deals.json")

    return {"workspace": str(workspace), "registry": str(DEALS_PATH), "slug": slug}


def init_generic(project_type: str, name: str, slug: str, args) -> dict:
    """Scaffold a non-DD project workspace."""
    workspace = TYPE_PATHS[project_type] / slug
    replacements = {"project_name": name, "company_name": name, "candidate_name": "Candidate"}

    # Create template files
    template_dir = TEMPLATES_ROOT / project_type
    if template_dir.exists():
        for tmpl in template_dir.glob("*.md"):
            content = load_template(tmpl, replacements)
            write_file(workspace / tmpl.name, content, args.force)

    # Create subfolders
    for folder in TYPE_FOLDERS.get(project_type, []):
        (workspace / folder).mkdir(parents=True, exist_ok=True)

    # Seed projects.json
    registry = load_registry(PROJECTS_PATH, "projects")
    if slug_exists(registry, slug, "projects"):
        print(f"[VFT] Project '{slug}' already exists in registry, skipping seed.")
    else:
        # Map project type to category
        category_map = {
            "hiring": "hiring",
            "research": "research",
            "conversations": "conversations",
            "operations": "operations",
        }

        record = {
            "slug": slug,
            "project_name": name,
            "name": name,
            "project_type": project_type,
            "category": category_map.get(project_type, "operations"),
            "status": TYPE_LIFECYCLES[project_type][0],  # First stage
            "priority": args.priority,
            "owner": args.owner,
            "created": date.today().isoformat(),
            "last_updated": date.today().isoformat(),
            "description": "",
            "keywords": slugify(name).replace("-", " ").split(),
            "contact_emails": [],
            "artifacts": {
                "workspace": str(workspace),
            },
        }
        registry["projects"].append(record)
        registry["last_updated"] = date.today().isoformat()
        PROJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROJECTS_PATH.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
        print(f"[VFT] Seeded project record for '{slug}' in projects.json")

    return {"workspace": str(workspace), "registry": str(PROJECTS_PATH), "slug": slug}


def main() -> int:
    parser = argparse.ArgumentParser(description="VFT Project Init — Universal Scaffolder")
    parser.add_argument("--type", required=True, choices=sorted(VALID_TYPES),
                        help="Project type")
    parser.add_argument("--name", required=True, help="Project name")
    parser.add_argument("--slug", type=str, help="Custom slug (auto-generated if omitted)")
    parser.add_argument("--owner", default="fund", help="Project owner")
    parser.add_argument("--priority", default="medium", choices=["low", "medium", "high", "urgent"])
    parser.add_argument("--source", default="", help="How this project was sourced")
    parser.add_argument("--sector", default="", help="Sector (for DD type)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    args = parser.parse_args()

    slug = args.slug or slugify(args.name)
    project_type = args.type

    print(f"[VFT] Initializing {project_type} project: {args.name} ({slug})")

    if project_type == "dd":
        result = init_dd(args.name, slug, args)
    else:
        result = init_generic(project_type, args.name, slug, args)

    print(f"[VFT] Workspace created at: {result['workspace']}")
    print(f"[VFT] Registry updated: {result['registry']}")

    # Remind to rebuild index
    print(f"\n[VFT] Run rebuild_index.py to update the classification index:")
    print(f"  python fund/metadata/rebuild_index.py")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
