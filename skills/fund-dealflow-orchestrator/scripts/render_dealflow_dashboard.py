#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def company_row(company: dict) -> str:
    raise_cap = company.get("valuation_cap_usd") or 0
    raise_amt = company.get("raise_usd") or 0
    valuation = f"${raise_cap:,.0f}" if raise_cap else "-"
    raise_text = f"${raise_amt:,.0f}" if raise_amt else "-"
    return (
        f"| {company.get('company_name', '')} | {company.get('stage', '')} | "
        f"{company.get('decision_posture', '')} | {raise_text} @ {valuation} | "
        f"{company.get('owner', '')} | {company.get('next_action_due', '') or '-'} | "
        f"{company.get('next_action', '') or '-'} |"
    )


def build_dashboard(registry: dict) -> str:
    companies = registry.get("companies", [])
    stage_counts = Counter(company.get("stage", "unknown") for company in companies)

    lines = [
        "# Fund Dashboard",
        "",
        f"- Fund: `{registry.get('fund_name', 'Fund')}`",
        f"- Last updated: `{registry.get('last_updated', '')}`",
        f"- Total companies: `{len(companies)}`",
        "",
        "## Stage Counts",
        "",
    ]

    for stage, count in sorted(stage_counts.items()):
        lines.append(f"- `{stage}`: `{count}`")

    lines.extend(
        [
            "",
            "## Active Pipeline",
            "",
            "| Company | Stage | Posture | Raise | Owner | Due | Next Action |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )

    active = [company for company in companies if company.get("status") in {"active", "invested"}]
    active.sort(key=lambda item: (item.get("next_action_due") or "9999-99-99", item.get("company_name", "")))
    for company in active:
        lines.append(company_row(company))

    lines.extend(["", "## Detailed Notes", ""])
    for company in sorted(companies, key=lambda item: item.get("company_name", "")):
        lines.extend(
            [
                f"### {company.get('company_name', '')}",
                "",
                f"- Stage: `{company.get('stage', '')}`",
                f"- Status: `{company.get('status', '')}`",
                f"- Decision posture: `{company.get('decision_posture', '')}`",
                f"- Thesis: {company.get('thesis', '') or '-'}",
                f"- Last touch: `{company.get('last_touch', '') or '-'}`",
                f"- Next action owner: `{company.get('next_action_owner', '') or '-'}`",
                f"- Next action: {company.get('next_action', '') or '-'}",
            ]
        )
        assumptions = company.get("assumptions", [])
        if assumptions:
            lines.append("- Assumptions:")
            for item in assumptions:
                lines.append(f"  - {item}")
        questions = company.get("open_questions", [])
        if questions:
            lines.append("- Open questions:")
            for item in questions:
                lines.append(f"  - {item}")
        artifacts = company.get("artifacts", {})
        if artifacts:
            lines.append("- Artifacts:")
            for key in sorted(artifacts):
                lines.append(f"  - `{key}`: `{artifacts[key]}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def normalize_for_site(registry: dict, repo_root: Path) -> dict:
    data = {
        "fund_name": registry.get("fund_name", "Fund"),
        "last_updated": registry.get("last_updated", ""),
        "schema_version": registry.get("schema_version", 1),
        "companies": [],
    }

    for company in registry.get("companies", []):
        normalized = dict(company)
        artifacts = {}
        for key, value in company.get("artifacts", {}).items():
            if isinstance(value, str) and value.startswith(str(repo_root)):
                artifacts[key] = {
                    "absolute": value,
                    "repo_relative": value[len(str(repo_root)) :].lstrip("/"),
                }
            else:
                artifacts[key] = {
                    "absolute": value,
                    "repo_relative": value,
                }
        normalized["artifacts"] = artifacts
        data["companies"].append(normalized)

    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the markdown dashboard from fund/crm/deals.json")
    parser.add_argument("--input", default="fund/crm/deals.json")
    parser.add_argument("--output", default="fund/crm/dashboard.md")
    parser.add_argument("--site-data-output", default="fund/dashboard/data/deals.json")
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
