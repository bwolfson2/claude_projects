#!/usr/bin/env python3
"""
VFT Deal & Project Classifier — Unified Messages Classifier (v2)

Classifies messages from the unified messages table against known companies
and projects. Extends the original classify_batch.py to work with the v2
schema while preserving the same scoring algorithm.

Usage:
    python classify_messages.py                          # Classify all unclassified messages
    python classify_messages.py --dry-run                # Score without applying
    python classify_messages.py --source outlook         # Only classify from one source
    python classify_messages.py --threshold 0.5          # Lower confidence threshold
    python classify_messages.py --llm-fallback           # Enable LLM fallback for ambiguous items
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

# ── Weights (same as v1) ────────────────────────────────────────────────
W_DOMAIN = 0.40
W_KEYWORD = 0.35
W_PARTICIPANT = 0.20
W_RECENCY = 0.05

# ── Thresholds ──────────────────────────────────────────────────────────
DEFAULT_MATCH_THRESHOLD = 0.60
LOW_CONFIDENCE_THRESHOLD = 0.30
LLM_FALLBACK_RANGE = (0.30, 0.59)  # Trigger LLM classification in this range

# ── Deal-like keywords ──────────────────────────────────────────────────
DEAL_KEYWORDS = {
    "intro", "pitch", "fundraise", "fundraising", "round", "investment",
    "deck", "safe", "term sheet", "termsheet", "valuation", "cap table",
    "pre-seed", "seed", "series", "venture", "startup", "founder",
    "raise", "dilution", "convertible", "equity",
}

# Import scoring functions from v1
sys.path.insert(0, str(Path(__file__).parent))
from classify_batch import (
    score_domain,
    score_keywords,
    score_participants,
    score_recency,
    tokenize,
    log_classification,
)


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.row_factory = sqlite3.Row
    return conn


def extract_signals_from_message(msg: dict) -> dict:
    """Extract matching signals from a unified message record."""
    # Extract domains from sender
    item_domains = set()
    sender = msg.get("sender") or ""
    if "@" in sender:
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', sender)
        if email_match:
            item_domains.add(email_match.group().split("@")[-1].lower())

    # Extract domains from recipients
    recipients = []
    try:
        recipients = json.loads(msg.get("recipients") or "[]")
    except (json.JSONDecodeError, TypeError):
        if msg.get("recipients"):
            recipients = [r.strip() for r in msg["recipients"].split(",") if r.strip()]

    for r in recipients:
        if "@" in str(r):
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', str(r))
            if email_match:
                item_domains.add(email_match.group().split("@")[-1].lower())

    # Extract tokens
    subject_tokens = tokenize(msg.get("subject") or "")
    body_tokens = tokenize(msg.get("body") or "")
    all_tokens = subject_tokens | body_tokens

    # Extract emails
    item_emails = set()
    if "@" in sender:
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', sender)
        if email_match:
            item_emails.add(email_match.group().lower())
    for r in recipients:
        if "@" in str(r):
            email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', str(r))
            if email_match:
                item_emails.add(email_match.group().lower())

    # Also check metadata for sender_domain
    try:
        metadata = json.loads(msg.get("metadata") or "{}")
        if metadata.get("sender_domain"):
            item_domains.add(metadata["sender_domain"].lower())
    except (json.JSONDecodeError, TypeError):
        pass

    return {
        "item_domains": item_domains,
        "subject_tokens": subject_tokens,
        "all_tokens": all_tokens,
        "item_emails": item_emails,
    }


def classify_message(conn: sqlite3.Connection, msg: dict) -> list:
    """Classify a single unified message against all known entities.

    Returns a list of all matches above LOW_CONFIDENCE_THRESHOLD.
    """
    signals = extract_signals_from_message(msg)
    item_domains = signals["item_domains"]
    subject_tokens = signals["subject_tokens"]
    all_tokens = signals["all_tokens"]
    item_emails = signals["item_emails"]

    matches = []

    # Score against companies
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

    # Score against projects
    projects = conn.execute("SELECT * FROM project_index").fetchall()
    for project in projects:
        idx_keywords = set((project["keywords"] or "").split(",")) - {""}
        idx_contacts = set((project["contact_emails"] or "").split(",")) - {""}

        k_score, k_detail = score_keywords(all_tokens, idx_keywords, subject_tokens)
        p_score, p_detail = score_participants(item_emails, idx_contacts)

        final = (k_score * (W_DOMAIN + W_KEYWORD)) + (p_score * W_PARTICIPANT)

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

    matches.sort(key=lambda m: m["confidence"], reverse=True)

    if matches:
        return matches

    # No matches — auto-create logic
    text = ((msg.get("subject") or "") + " " + (msg.get("body") or "")).lower()
    deal_hits = sum(1 for kw in DEAL_KEYWORDS if kw in text)

    return [{
        "matched_slug": None,
        "match_type": "new_deal" if deal_hits >= 1 else "new_project",
        "confidence": 0.0,
        "rule_hits": {"auto_create": True, "deal_keyword_hits": deal_hits},
    }]


def update_project_tags(conn: sqlite3.Connection, message_id: int, matches: list):
    """Update the project_tags array on a message with matched slugs."""
    slugs = [m["matched_slug"] for m in matches if m.get("matched_slug")]
    if slugs:
        conn.execute(
            "UPDATE messages SET project_tags = ? WHERE id = ?",
            (json.dumps(slugs), message_id),
        )


def run_message_batch(
    source_filter: str = "all",
    threshold: float = DEFAULT_MATCH_THRESHOLD,
    dry_run: bool = False,
    rebuild_index: bool = True,
    llm_fallback: bool = False,
) -> dict:
    """Run batch classification on unclassified messages in unified table."""
    conn = get_db()

    # Rebuild indexes
    if rebuild_index:
        sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))
        from rebuild_index import rebuild_company_index, rebuild_project_index
        rebuild_company_index(conn, str(DEALS_PATH))
        rebuild_project_index(conn, str(PROJECTS_PATH))
        conn.commit()

    # Query unclassified messages
    if source_filter == "all":
        messages = conn.execute(
            "SELECT * FROM messages WHERE classified = 0"
        ).fetchall()
    else:
        messages = conn.execute(
            "SELECT * FROM messages WHERE classified = 0 AND source = ?",
            (source_filter,),
        ).fetchall()

    results = {"messages": [], "summary": {}}
    all_matches = []

    for msg in messages:
        msg_dict = dict(msg)
        matches = classify_message(conn, msg_dict)

        item_result = {
            "message_id": msg["id"],
            "source": msg["source"],
            "subject": msg["subject"],
            "matches": matches,
            "top_match_type": matches[0]["match_type"] if matches else "unclassified",
            "top_matched_slug": matches[0]["matched_slug"] if matches else None,
            "top_confidence": matches[0]["confidence"] if matches else 0.0,
            "needs_llm_fallback": (
                llm_fallback
                and matches
                and LLM_FALLBACK_RANGE[0] <= matches[0]["confidence"] <= LLM_FALLBACK_RANGE[1]
            ),
        }

        if not dry_run:
            # Log all matches
            for match in matches:
                log_classification(conn, "message", msg["id"], match)

            # Update project_tags on the message
            update_project_tags(conn, msg["id"], matches)

            # Mark as classified
            conn.execute(
                "UPDATE messages SET classified = 1 WHERE id = ?",
                (msg["id"],),
            )

        results["messages"].append(item_result)
        all_matches.extend(matches)

    if not dry_run:
        conn.commit()

    # Summary
    results["summary"] = {
        "total_messages": len(messages),
        "total_classifications": len(all_matches),
        "multi_match_messages": sum(1 for m in results["messages"] if len(m.get("matches", [])) > 1),
        "matched_deals": sum(1 for m in all_matches if m["match_type"] == "deal"),
        "matched_projects": sum(1 for m in all_matches if m["match_type"] == "project"),
        "new_deals": sum(1 for m in all_matches if m["match_type"] == "new_deal"),
        "new_projects": sum(1 for m in all_matches if m["match_type"] == "new_project"),
        "needs_llm_fallback": sum(1 for m in results["messages"] if m.get("needs_llm_fallback")),
        "avg_confidence": (
            sum(m["confidence"] for m in all_matches) / len(all_matches)
            if all_matches else 0
        ),
        "dry_run": dry_run,
    }

    conn.close()
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Unified Messages Classifier (v2)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--threshold", type=float, default=DEFAULT_MATCH_THRESHOLD)
    parser.add_argument("--source", choices=["outlook", "slack", "whatsapp", "signal", "granola", "web", "all"], default="all")
    parser.add_argument("--rebuild-index", action="store_true", default=True)
    parser.add_argument("--no-rebuild-index", action="store_false", dest="rebuild_index")
    parser.add_argument("--llm-fallback", action="store_true", help="Enable LLM fallback for ambiguous items")
    args = parser.parse_args()

    print(f"[VFT Classifier v2] Running unified message classification...")
    print(f"  Source filter: {args.source}")
    print(f"  Threshold: {args.threshold}")
    print(f"  LLM fallback: {args.llm_fallback}")
    print(f"  Dry run: {args.dry_run}")

    results = run_message_batch(
        source_filter=args.source,
        threshold=args.threshold,
        dry_run=args.dry_run,
        rebuild_index=args.rebuild_index,
        llm_fallback=args.llm_fallback,
    )

    s = results["summary"]
    print(f"\n[VFT Classifier v2] Results:")
    print(f"  Total messages: {s['total_messages']}")
    print(f"  Total classifications: {s['total_classifications']}")
    print(f"  Multi-match messages: {s['multi_match_messages']}")
    print(f"  Matched to deals: {s['matched_deals']}")
    print(f"  Matched to projects: {s['matched_projects']}")
    print(f"  New deals to create: {s['new_deals']}")
    print(f"  New projects to create: {s['new_projects']}")
    print(f"  Needs LLM fallback: {s['needs_llm_fallback']}")
    print(f"  Avg confidence: {s['avg_confidence']:.3f}")

    for msg_r in results["messages"]:
        matches = msg_r.get("matches", [])
        label = f"[{msg_r['source']}] {msg_r.get('subject', '?')[:50]}"
        llm_tag = " [LLM?]" if msg_r.get("needs_llm_fallback") else ""
        if len(matches) == 1:
            m = matches[0]
            conf_bar = "█" * int(m["confidence"] * 10)
            print(f"  {label} → {m['match_type']}:{m.get('matched_slug', 'NEW')} ({m['confidence']:.2f}) {conf_bar}{llm_tag}")
        else:
            print(f"  {label} → {len(matches)} matches:{llm_tag}")
            for m in matches:
                conf_bar = "█" * int(m["confidence"] * 10)
                print(f"      ↳ {m['match_type']}:{m.get('matched_slug', 'NEW')} ({m['confidence']:.2f}) {conf_bar}")
