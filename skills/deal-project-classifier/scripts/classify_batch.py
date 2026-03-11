#!/usr/bin/env python3
"""
VFT Deal & Project Classifier — Batch Classification Engine

Scores unclassified emails and transcripts against known companies and
projects using rule-based matching. Logs all classifications and triggers
updates to the deal/project pipeline.

Usage:
    python classify_batch.py                      # Classify all unclassified items
    python classify_batch.py --dry-run             # Score without applying
    python classify_batch.py --source-type email   # Only classify emails
    python classify_batch.py --threshold 0.5       # Lower confidence threshold
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
DEALS_PATH = REPO_ROOT / "fund" / "crm" / "deals.json"
PROJECTS_PATH = REPO_ROOT / "projects" / "projects.json"

# ── Weights ──────────────────────────────────────────────────────────────
W_DOMAIN = 0.40
W_KEYWORD = 0.35
W_PARTICIPANT = 0.20
W_RECENCY = 0.05

# ── Thresholds ───────────────────────────────────────────────────────────
DEFAULT_MATCH_THRESHOLD = 0.60
LOW_CONFIDENCE_THRESHOLD = 0.30

# ── Deal-like keywords (for auto-create logic) ──────────────────────────
DEAL_KEYWORDS = {
    "intro", "pitch", "fundraise", "fundraising", "round", "investment",
    "deck", "safe", "term sheet", "termsheet", "valuation", "cap table",
    "pre-seed", "seed", "series", "venture", "startup", "founder",
    "raise", "dilution", "convertible", "equity",
}


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row
    return conn


def tokenize(text: str) -> set:
    """Extract lowercase tokens from text."""
    if not text:
        return set()
    return set(re.findall(r'[a-z0-9]+', text.lower()))


def score_domain(item_domains: set, index_domains: set) -> tuple:
    """Score domain match between item and index entry."""
    if not item_domains or not index_domains:
        return 0.0, {}

    for d in item_domains:
        if d in index_domains:
            return 1.0, {"match": d, "type": "exact"}
        # Check subdomain match
        for idx_d in index_domains:
            if d.endswith(f".{idx_d}") or idx_d.endswith(f".{d}"):
                return 0.7, {"match": f"{d}~{idx_d}", "type": "subdomain"}

    return 0.0, {}


def score_keywords(item_tokens: set, index_keywords: set, subject_tokens: set = None) -> tuple:
    """Score keyword match."""
    if not index_keywords:
        return 0.0, {}

    # Check for company/project name exact match in subject
    if subject_tokens:
        for kw in index_keywords:
            if kw in subject_tokens and len(kw) > 2:  # avoid matching tiny tokens
                return 1.0, {"matches": [kw], "type": "subject_exact"}

    # Overlap ratio
    overlap = item_tokens & index_keywords
    if not overlap:
        return 0.0, {}

    ratio = len(overlap) / max(len(index_keywords), 1)
    score = min(ratio * 2, 1.0)  # Scale up — even partial overlap is significant

    return score, {"matches": sorted(overlap), "total_keywords": len(index_keywords)}


def score_participants(item_emails: set, index_contacts: set) -> tuple:
    """Score participant/contact match."""
    if not item_emails or not index_contacts:
        return 0.0, {}

    matches = item_emails & index_contacts
    if not matches:
        return 0.0, {}

    score = 1.0 if len(matches) > 1 else 0.8
    return score, {"matches": sorted(matches)}


def score_recency(last_touch: str) -> tuple:
    """Score based on how recently the entity was touched."""
    if not last_touch:
        return 0.0, {"note": "no last_touch"}

    try:
        lt = datetime.fromisoformat(last_touch)
        days = (datetime.now() - lt).days
        if days <= 7:
            return 1.0, {"last_touch_days": days}
        elif days <= 30:
            return 0.5, {"last_touch_days": days}
        else:
            return 0.0, {"last_touch_days": days}
    except (ValueError, TypeError):
        return 0.0, {"note": "invalid last_touch"}


def _extract_signals(source_type: str, item: dict) -> dict:
    """Extract matching signals (domains, tokens, emails) from an item."""
    if source_type == "email":
        item_domains = {item.get("sender_domain", "")} if item.get("sender_domain") else set()
        for r in (item.get("recipients", "") or "").split(","):
            r = r.strip()
            if "@" in r:
                item_domains.add(r.split("@")[-1].lower())

        subject_tokens = tokenize(item.get("subject", ""))
        body_tokens = tokenize(item.get("body_preview", ""))
        all_tokens = subject_tokens | body_tokens

        item_emails = set()
        sender = item.get("sender", "")
        if "@" in sender:
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', sender)
            if email_match:
                item_emails.add(email_match.group().lower())
        for r in (item.get("recipients", "") or "").split(","):
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', r)
            if email_match:
                item_emails.add(email_match.group().lower())
    else:  # transcript
        item_domains = set()
        item_emails = set()
        for p in (item.get("participants", "") or "").split(","):
            p = p.strip()
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', p)
            if email_match:
                email = email_match.group().lower()
                item_emails.add(email)
                item_domains.add(email.split("@")[-1])

        subject_tokens = tokenize(item.get("title", ""))
        body_tokens = tokenize(item.get("summary", ""))
        all_tokens = subject_tokens | body_tokens

    return {
        "item_domains": item_domains,
        "subject_tokens": subject_tokens,
        "all_tokens": all_tokens,
        "item_emails": item_emails,
    }


def classify_item(
    conn: sqlite3.Connection,
    source_type: str,
    item: dict,
) -> list:
    """
    Classify a single email or transcript against all known companies and projects.
    Returns a LIST of all matches above LOW_CONFIDENCE_THRESHOLD, sorted by score.
    An item can match multiple deals AND projects simultaneously.
    If nothing matches, returns a single auto-create entry.
    """
    signals = _extract_signals(source_type, item)
    item_domains = signals["item_domains"]
    subject_tokens = signals["subject_tokens"]
    all_tokens = signals["all_tokens"]
    item_emails = signals["item_emails"]

    matches = []  # list of {matched_slug, match_type, confidence, rule_hits}

    # Score against all companies
    companies = conn.execute("SELECT * FROM company_index").fetchall()
    for company in companies:
        idx_domains = set((company["domains"] or "").split(",")) - {""}
        idx_keywords = set((company["keywords"] or "").split(",")) - {""}
        idx_contacts = set((company["contact_emails"] or "").split(",")) - {""}

        d_score, d_detail = score_domain(item_domains, idx_domains)
        k_score, k_detail = score_keywords(all_tokens, idx_keywords, subject_tokens)
        p_score, p_detail = score_participants(item_emails, idx_contacts)
        r_score, r_detail = score_recency(company["last_touch"])

        final = (d_score * W_DOMAIN) + (k_score * W_KEYWORD) + (p_score * W_PARTICIPANT) + (r_score * W_RECENCY)

        if final >= LOW_CONFIDENCE_THRESHOLD:
            matches.append({
                "matched_slug": company["company_slug"],
                "match_type": "deal",
                "confidence": round(final, 4),
                "rule_hits": {
                    "domain": {"score": d_score, **d_detail},
                    "keyword": {"score": k_score, **k_detail},
                    "participant": {"score": p_score, **p_detail},
                    "recency": {"score": r_score, **r_detail},
                },
            })

    # Score against all projects
    projects = conn.execute("SELECT * FROM project_index").fetchall()
    for project in projects:
        idx_keywords = set((project["keywords"] or "").split(",")) - {""}
        idx_contacts = set((project["contact_emails"] or "").split(",")) - {""}

        k_score, k_detail = score_keywords(all_tokens, idx_keywords, subject_tokens)
        p_score, p_detail = score_participants(item_emails, idx_contacts)

        # Redistribute domain weight to keywords for projects
        final = (k_score * (W_DOMAIN + W_KEYWORD)) + (p_score * W_PARTICIPANT) + (0.0 * W_RECENCY)

        if final >= LOW_CONFIDENCE_THRESHOLD:
            matches.append({
                "matched_slug": project["project_slug"],
                "match_type": "project",
                "confidence": round(final, 4),
                "rule_hits": {
                    "domain": {"score": 0, "note": "projects have no domain matching"},
                    "keyword": {"score": k_score, **k_detail},
                    "participant": {"score": p_score, **p_detail},
                    "recency": {"score": 0, "note": "N/A"},
                },
            })

    # Sort by confidence descending
    matches.sort(key=lambda m: m["confidence"], reverse=True)

    # If we have matches, return them all
    if matches:
        return matches

    # No matches — auto-create logic
    text = (item.get("subject", "") + " " + item.get("title", "") + " " + item.get("body_preview", "") + " " + item.get("summary", "")).lower()
    deal_hits = sum(1 for kw in DEAL_KEYWORDS if kw in text)
    if deal_hits >= 1:
        match_type = "new_deal"
    else:
        match_type = "new_project"

    return [{
        "matched_slug": None,
        "match_type": match_type,
        "confidence": 0.0,
        "rule_hits": {"auto_create": True, "deal_keyword_hits": deal_hits},
    }]


def log_classification(
    conn: sqlite3.Connection,
    source_type: str,
    source_id: int,
    result: dict,
) -> int:
    """Log a classification result to the database.

    Multi-match aware: uses (source_type, source_id, matched_slug) as the
    composite key, so one email/transcript can have multiple classification
    entries — one per matched deal/project.
    """
    matched_slug = result.get("matched_slug")

    # Check if this specific match already exists and was human-reviewed
    existing = conn.execute(
        """SELECT id, reviewed FROM classification_log
           WHERE source_type = ? AND source_id = ? AND (matched_slug = ? OR (matched_slug IS NULL AND ? IS NULL))""",
        (source_type, source_id, matched_slug, matched_slug),
    ).fetchone()

    if existing and existing["reviewed"]:
        return existing["id"]

    if existing:
        conn.execute(
            """UPDATE classification_log
               SET match_type = ?, confidence = ?, rule_hits = ?, created_at = datetime('now')
               WHERE id = ?""",
            (
                result["match_type"],
                result["confidence"],
                json.dumps(result["rule_hits"]),
                existing["id"],
            ),
        )
        return existing["id"]
    else:
        conn.execute(
            """INSERT INTO classification_log
               (source_type, source_id, matched_slug, match_type, confidence, rule_hits)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                source_type,
                source_id,
                matched_slug,
                result["match_type"],
                result["confidence"],
                json.dumps(result["rule_hits"]),
            ),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def run_batch(
    source_type: str = "all",
    threshold: float = DEFAULT_MATCH_THRESHOLD,
    dry_run: bool = False,
    rebuild_index: bool = True,
) -> dict:
    """Run batch classification on all unclassified items.

    Each item can produce MULTIPLE classification matches (deal + project,
    or multiple deals). All matches above LOW_CONFIDENCE_THRESHOLD are logged.
    """
    conn = get_db()

    # Optionally rebuild indexes
    if rebuild_index:
        sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))
        from rebuild_index import rebuild_company_index, rebuild_project_index
        rebuild_company_index(conn, str(DEALS_PATH))
        rebuild_project_index(conn, str(PROJECTS_PATH))
        conn.commit()

    results = {"emails": [], "transcripts": [], "summary": {}}

    # Classify emails
    if source_type in ("all", "email"):
        emails = conn.execute(
            "SELECT * FROM emails WHERE classified = 0"
        ).fetchall()
        for email in emails:
            item = dict(email)
            matches = classify_item(conn, "email", item)  # now returns a list

            item_result = {
                "source_id": email["id"],
                "subject": email["subject"],
                "matches": matches,
                # Keep top match for backward compat
                "match_type": matches[0]["match_type"] if matches else "unclassified",
                "matched_slug": matches[0]["matched_slug"] if matches else None,
                "confidence": matches[0]["confidence"] if matches else 0.0,
            }

            if not dry_run:
                # Log ALL matches for this item
                for match in matches:
                    log_classification(conn, "email", email["id"], match)
                conn.execute(
                    "UPDATE emails SET classified = 1 WHERE id = ?",
                    (email["id"],),
                )

            results["emails"].append(item_result)

    # Classify transcripts
    if source_type in ("all", "transcript"):
        transcripts = conn.execute(
            "SELECT * FROM transcripts WHERE classified = 0"
        ).fetchall()
        for transcript in transcripts:
            item = dict(transcript)
            matches = classify_item(conn, "transcript", item)

            item_result = {
                "source_id": transcript["id"],
                "title": transcript["title"],
                "matches": matches,
                "match_type": matches[0]["match_type"] if matches else "unclassified",
                "matched_slug": matches[0]["matched_slug"] if matches else None,
                "confidence": matches[0]["confidence"] if matches else 0.0,
            }

            if not dry_run:
                for match in matches:
                    log_classification(conn, "transcript", transcript["id"], match)
                conn.execute(
                    "UPDATE transcripts SET classified = 1 WHERE id = ?",
                    (transcript["id"],),
                )

            results["transcripts"].append(item_result)

    if not dry_run:
        conn.commit()

    # Summary — count all classification log entries (multi-match aware)
    all_items = results["emails"] + results["transcripts"]
    all_matches = []
    for item in all_items:
        all_matches.extend(item.get("matches", []))

    results["summary"] = {
        "total_items": len(all_items),
        "total_classifications": len(all_matches),
        "multi_match_items": sum(1 for i in all_items if len(i.get("matches", [])) > 1),
        "matched_deals": sum(1 for m in all_matches if m["match_type"] == "deal"),
        "matched_projects": sum(1 for m in all_matches if m["match_type"] == "project"),
        "new_deals": sum(1 for m in all_matches if m["match_type"] == "new_deal"),
        "new_projects": sum(1 for m in all_matches if m["match_type"] == "new_project"),
        "avg_confidence": (
            sum(m["confidence"] for m in all_matches) / len(all_matches)
            if all_matches else 0
        ),
        "dry_run": dry_run,
    }

    conn.close()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Batch Classifier")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--threshold", type=float, default=DEFAULT_MATCH_THRESHOLD)
    parser.add_argument("--source-type", choices=["email", "transcript", "all"], default="all")
    parser.add_argument("--rebuild-index", action="store_true", default=True)
    parser.add_argument("--no-rebuild-index", action="store_false", dest="rebuild_index")
    args = parser.parse_args()

    print(f"[VFT Classifier] Running batch classification...")
    print(f"  Source type: {args.source_type}")
    print(f"  Threshold: {args.threshold}")
    print(f"  Dry run: {args.dry_run}")

    results = run_batch(
        source_type=args.source_type,
        threshold=args.threshold,
        dry_run=args.dry_run,
        rebuild_index=args.rebuild_index,
    )

    print(f"\n[VFT Classifier] Results:")
    s = results["summary"]
    print(f"  Total items: {s['total_items']}")
    print(f"  Total classifications: {s['total_classifications']}")
    print(f"  Multi-match items: {s['multi_match_items']}")
    print(f"  Matched to deals: {s['matched_deals']}")
    print(f"  Matched to projects: {s['matched_projects']}")
    print(f"  New deals to create: {s['new_deals']}")
    print(f"  New projects to create: {s['new_projects']}")
    print(f"  Avg confidence: {s['avg_confidence']:.3f}")

    # Print detail (multi-match aware)
    for email_r in results["emails"]:
        matches = email_r.get("matches", [])
        label = email_r.get("subject", "?")[:50]
        if len(matches) == 1:
            m = matches[0]
            conf_bar = "█" * int(m["confidence"] * 10)
            print(f"  📧 {label} → {m['match_type']}:{m.get('matched_slug', 'NEW')} ({m['confidence']:.2f}) {conf_bar}")
        else:
            print(f"  📧 {label} → {len(matches)} matches:")
            for m in matches:
                conf_bar = "█" * int(m["confidence"] * 10)
                print(f"      ↳ {m['match_type']}:{m.get('matched_slug', 'NEW')} ({m['confidence']:.2f}) {conf_bar}")

    for trans_r in results["transcripts"]:
        matches = trans_r.get("matches", [])
        label = trans_r.get("title", "?")[:50]
        if len(matches) == 1:
            m = matches[0]
            conf_bar = "█" * int(m["confidence"] * 10)
            print(f"  🎙 {label} → {m['match_type']}:{m.get('matched_slug', 'NEW')} ({m['confidence']:.2f}) {conf_bar}")
        else:
            print(f"  🎙 {label} → {len(matches)} matches:")
            for m in matches:
                conf_bar = "█" * int(m["confidence"] * 10)
                print(f"      ↳ {m['match_type']}:{m.get('matched_slug', 'NEW')} ({m['confidence']:.2f}) {conf_bar}")
