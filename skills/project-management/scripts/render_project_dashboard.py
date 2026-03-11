#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def project_row(project: dict) -> str:
    return (
        f"| {project.get('project_name', '')} | {project.get('category', '')} | "
        f"{project.get('status', '')} | {project.get('priority', '')} | "
        f"{project.get('owner', '')} | {project.get('target_date', '') or '-'} | "
        f"{project.get('next_action_due', '') or '-'} | "
        f"{project.get('next_action', '') or '-'} |"
    )


def build_dashboard(registry: dict) -> str:
    projects = registry.get("projects", [])
    status_counts = Counter(project.get("status", "unknown") for project in projects)
    category_counts = Counter(project.get("category", "unknown") for project in projects)

    lines = [
        "# Project Dashboard",
        "",
        f"- Fund: `{registry.get('fund_name', 'Fund')}`",
        f"- Last updated: `{registry.get('last_updated', '')}`",
        f"- Total projects: `{len(projects)}`",
        "",
        "## Status Counts",
        "",
    ]

    for status, count in sorted(status_counts.items()):
        lines.append(f"- `{status}`: `{count}`")

    lines.extend(
        [
            "",
            "## Category Counts",
            "",
        ]
    )

    for category, count in sorted(category_counts.items()):
        lines.append(f"- `{category}`: `{count}`")

    lines.extend(
        [
            "",
            "## Active Projects",
            "",
            "| Project | Category | Status | Priority | Owner | Target | Due | Next Action |",
            "| --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    active = [project for project in projects if project.get("status") in {"planned", "in_progress", "blocked"}]
    active.sort(key=lambda item: (item.get("target_date") or "9999-99-99", item.get("project_name", "")))
    for project in active:
        lines.append(project_row(project))

    lines.extend(["", "## Detailed Notes", ""])
    for project in sorted(projects, key=lambda item: item.get("project_name", "")):
        lines.extend(
            [
                f"### {project.get('project_name', '')}",
                "",
                f"- Category: `{project.get('category', '')}`",
                f"- Status: `{project.get('status', '')}`",
                f"- Priority: `{project.get('priority', '')}`",
                f"- Owner: `{project.get('owner', '') or '-'}`",
                f"- Description: {project.get('description', '') or '-'}",
                f"- Target date: `{project.get('target_date', '') or '-'}`",
                f"- Start date: `{project.get('start_date', '') or '-'}`",
                f"- Completion date: `{project.get('completion_date', '') or '-'}`",
                f"- Next action owner: `{project.get('next_action_owner', '') or '-'}`",
                f"- Next action: {project.get('next_action', '') or '-'}",
                f"- Next action due: `{project.get('next_action_due', '') or '-'}`",
            ]
        )
        assumptions = project.get("assumptions", [])
        if assumptions:
            lines.append("- Assumptions:")
            for item in assumptions:
                lines.append(f"  - {item}")
        blockers = project.get("blockers", [])
        if blockers:
            lines.append("- Blockers:")
            for blocker in blockers:
                if isinstance(blocker, dict):
                    lines.append(f"  - {blocker.get('description', '')} (owner: {blocker.get('owner', '-')})")
                else:
                    lines.append(f"  - {blocker}")
        success_criteria = project.get("success_criteria", [])
        if success_criteria:
            lines.append("- Success criteria:")
            for item in success_criteria:
                lines.append(f"  - {item}")
        docs = project.get("docs", [])
        if docs:
            lines.append("- Artifacts:")
            for doc in docs:
                if isinstance(doc, str):
                    lines.append(f"  - `{doc}`")
                else:
                    lines.append(f"  - `{doc}`")
        notes = project.get("notes", [])
        if notes:
            lines.append("- Notes:")
            for note in notes:
                if isinstance(note, dict):
                    lines.append(f"  - {note.get('date', '')} ({note.get('author', '')}): {note.get('content', '')}")
                else:
                    lines.append(f"  - {note}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def normalize_for_site(registry: dict, repo_root: Path) -> dict:
    data = {
        "fund_name": registry.get("fund_name", "Fund"),
        "last_updated": registry.get("last_updated", ""),
        "schema_version": registry.get("schema_version", 1),
        "projects": [],
    }

    for project in registry.get("projects", []):
        normalized = dict(project)
        docs = []
        for doc in project.get("docs", []):
            if isinstance(doc, str) and doc.startswith(str(repo_root)):
                docs.append({
                    "absolute": doc,
                    "repo_relative": doc[len(str(repo_root)):].lstrip("/"),
                })
            else:
                docs.append({
                    "absolute": doc,
                    "repo_relative": doc,
                })
        normalized["docs"] = docs
        data["projects"].append(normalized)

    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the markdown dashboard from projects/projects.json")
    parser.add_argument("--input", default="projects/projects.json")
    parser.add_argument("--output", default="projects/dashboard.md")
    parser.add_argument("--site-data-output", default="projects/dashboard/data/projects.json")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    site_data_output = Path(args.site_data_output)
    registry = json.loads(input_path.read_text(encoding="utf-8"))
    output_path.write_text(build_dashboard(registry), encoding="utf-8")
    site_data_output.parent.mkdir(parents=True, exist_ok=True)
    site_data_output.write_text(
        json.dumps(normalize_for_site(registry, Path.cwd()), indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
