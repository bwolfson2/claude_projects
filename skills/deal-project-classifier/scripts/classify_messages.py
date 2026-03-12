#!/usr/bin/env python3
"""
VFT Deal & Project Classifier — RLM Data Access CLI

Provides subcommands for Claude Code to drive message classification
conversationally. Instead of running a scoring algorithm, Claude reads
the context (deals, projects, signals) and pending messages, then uses
its own reasoning to decide which messages belong to which entities.

    python classify_messages.py pending                          # List unclassified messages
    python classify_messages.py context                          # Show deals/projects + signals
    python classify_messages.py detail --id 42                   # Full message content
    python classify_messages.py classify --message-id 42 --slug midbound --match-type deal
    python classify_messages.py batch-classify --decisions '[...]'
    python classify_messages.py auto-create --type deal --name "WidgetCo"
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(os.environ.get("VFT_REPO_ROOT",
    Path(__file__).resolve().parents[3]))
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
DEALS_PATH = REPO_ROOT / "fund" / "crm" / "deals.json"
PROJECTS_PATH = REPO_ROOT / "projects" / "projects.json"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=OFF")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def slugify(name: str) -> str:
    """Convert a name to a URL-safe slug."""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug


# ── Subcommand: pending ──────────────────────────────────────────────────

def cmd_pending(args):
    """List unclassified messages with previews."""
    conn = get_db()

    query = "SELECT * FROM messages WHERE classified = 0"
    params = []

    if args.source and args.source != "all":
        query += " AND source = ?"
        params.append(args.source)

    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(args.limit)

    rows = conn.execute(query, params).fetchall()

    # Also get total count
    count_q = "SELECT COUNT(*) as cnt FROM messages WHERE classified = 0"
    if args.source and args.source != "all":
        total = conn.execute(count_q + " AND source = ?", [args.source]).fetchone()["cnt"]
    else:
        total = conn.execute(count_q).fetchone()["cnt"]

    messages = []
    for r in rows:
        body = r["body"] or ""
        sender = r["sender"] or ""

        # Extract sender domain
        sender_domain = ""
        email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', sender)
        if email_match:
            sender_domain = email_match.group().split("@")[-1].lower()

        messages.append({
            "id": r["id"],
            "source": r["source"],
            "sender": sender,
            "sender_domain": sender_domain,
            "subject": r["subject"] or "",
            "body_preview": body[:300],
            "timestamp": r["timestamp"] or "",
            "attachments": r["attachments"] or "",
            "channel": r["channel"] or "",
            "recipients": r["recipients"] or "",
        })

    print(json.dumps({
        "pending_count": total,
        "showing": len(messages),
        "messages": messages,
    }, indent=2))
    conn.close()


# ── Subcommand: context ──────────────────────────────────────────────────

def cmd_context(args):
    """Show all known deals/projects with signals for classification."""
    conn = get_db()

    # Optionally rebuild indexes
    if args.rebuild_index:
        try:
            sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))
            from rebuild_index import rebuild_company_index, rebuild_project_index
            rebuild_company_index(conn, str(DEALS_PATH))
            rebuild_project_index(conn, str(PROJECTS_PATH))
            conn.commit()
        except Exception as e:
            print(json.dumps({"warning": f"Index rebuild failed: {e}"}), file=sys.stderr)

    # Get deals from company_index
    deals = []
    for r in conn.execute("SELECT * FROM company_index").fetchall():
        deal = {
            "slug": r["company_slug"],
            "company_name": r["company_name"],
            "domains": [d for d in (r["domains"] or "").split(",") if d],
            "keywords": [k for k in (r["keywords"] or "").split(",") if k],
            "contact_emails": [e for e in (r["contact_emails"] or "").split(",") if e],
            "last_touch": r["last_touch"] or "",
        }
        # Get stage/status from deals.json if available
        if DEALS_PATH.exists():
            try:
                all_deals = json.loads(DEALS_PATH.read_text())
                for d in all_deals:
                    if d.get("slug") == r["company_slug"]:
                        deal["stage"] = d.get("stage", "")
                        deal["status"] = d.get("status", "")
                        break
            except (json.JSONDecodeError, IOError):
                pass
        if args.active_only and deal.get("status") == "passed":
            continue
        deals.append(deal)

    # Get projects from project_index
    projects = []
    for r in conn.execute("SELECT * FROM project_index").fetchall():
        proj = {
            "slug": r["project_slug"],
            "project_name": r["project_name"],
            "keywords": [k for k in (r["keywords"] or "").split(",") if k],
            "contact_emails": [e for e in (r["contact_emails"] or "").split(",") if e],
        }
        if PROJECTS_PATH.exists():
            try:
                all_projects = json.loads(PROJECTS_PATH.read_text())
                for p in all_projects:
                    if p.get("slug") == r["project_slug"]:
                        proj["status"] = p.get("status", "")
                        proj["project_type"] = p.get("project_type", "")
                        break
            except (json.JSONDecodeError, IOError):
                pass
        if args.active_only and proj.get("status") in ("archived", "cancelled"):
            continue
        projects.append(proj)

    # Recent classifications for context
    recent = conn.execute("""
        SELECT source_type, source_id, matched_slug, match_type, confidence, created_at
        FROM classification_log
        ORDER BY created_at DESC LIMIT 20
    """).fetchall()

    recent_list = [dict(r) for r in recent]

    print(json.dumps({
        "deals_count": len(deals),
        "projects_count": len(projects),
        "deals": deals,
        "projects": projects,
        "recent_classifications": recent_list,
    }, indent=2))
    conn.close()


# ── Subcommand: detail ───────────────────────────────────────────────────

def cmd_detail(args):
    """Get full message content for a specific message."""
    conn = get_db()
    row = conn.execute("SELECT * FROM messages WHERE id = ?", (args.id,)).fetchone()

    if not row:
        print(json.dumps({"error": f"Message {args.id} not found"}))
        conn.close()
        return

    msg = dict(row)
    # Parse metadata if JSON
    try:
        msg["metadata"] = json.loads(msg.get("metadata") or "{}")
    except (json.JSONDecodeError, TypeError):
        pass

    print(json.dumps(msg, indent=2, default=str))
    conn.close()


# ── Subcommand: classify ─────────────────────────────────────────────────

def cmd_classify(args):
    """Store Claude's classification decision for a message."""
    conn = get_db()

    # Check if human-reviewed classification exists
    existing = conn.execute(
        """SELECT id, reviewed FROM classification_log
           WHERE source_type = 'message' AND source_id = ?
           AND (matched_slug = ? OR (matched_slug IS NULL AND ? IS NULL))""",
        (args.message_id, args.slug, args.slug),
    ).fetchone()

    if existing and existing["reviewed"]:
        print(json.dumps({
            "status": "skipped",
            "reason": "human-reviewed classification exists",
            "message_id": args.message_id,
        }))
        conn.close()
        return

    # Parse reasoning
    reasoning = args.reasoning or "{}"
    try:
        reasoning_obj = json.loads(reasoning)
    except json.JSONDecodeError:
        reasoning_obj = {"note": reasoning}

    if existing:
        conn.execute(
            """UPDATE classification_log
               SET match_type = ?, confidence = ?, rule_hits = ?, created_at = datetime('now')
               WHERE id = ?""",
            (args.match_type, args.confidence, json.dumps(reasoning_obj), existing["id"]),
        )
    else:
        conn.execute(
            """INSERT INTO classification_log
               (source_type, source_id, matched_slug, match_type, confidence, rule_hits)
               VALUES ('message', ?, ?, ?, ?, ?)""",
            (args.message_id, args.slug, args.match_type, args.confidence,
             json.dumps(reasoning_obj)),
        )

    # Mark message as classified
    conn.execute("UPDATE messages SET classified = 1 WHERE id = ?", (args.message_id,))

    # Update project_tags
    if args.slug:
        row = conn.execute("SELECT project_tags FROM messages WHERE id = ?",
                           (args.message_id,)).fetchone()
        existing_tags = []
        try:
            existing_tags = json.loads(row["project_tags"] or "[]")
        except (json.JSONDecodeError, TypeError):
            pass
        if args.slug not in existing_tags:
            existing_tags.append(args.slug)
        conn.execute("UPDATE messages SET project_tags = ? WHERE id = ?",
                     (json.dumps(existing_tags), args.message_id))

    conn.commit()
    print(json.dumps({
        "status": "classified",
        "message_id": args.message_id,
        "matched_slug": args.slug,
        "match_type": args.match_type,
        "confidence": args.confidence,
    }))
    conn.close()


# ── Subcommand: batch-classify ───────────────────────────────────────────

def cmd_batch_classify(args):
    """Store multiple classification decisions at once."""
    conn = get_db()

    try:
        decisions = json.loads(args.decisions)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        return

    classified = 0
    skipped = 0
    errors = 0

    for d in decisions:
        try:
            msg_id = d["message_id"]
            slug = d.get("slug")
            match_type = d.get("match_type", "deal")
            confidence = d.get("confidence", 1.0)
            reasoning = d.get("reasoning", {})

            # Check reviewed
            existing = conn.execute(
                """SELECT id, reviewed FROM classification_log
                   WHERE source_type = 'message' AND source_id = ?
                   AND (matched_slug = ? OR (matched_slug IS NULL AND ? IS NULL))""",
                (msg_id, slug, slug),
            ).fetchone()

            if existing and existing["reviewed"]:
                skipped += 1
                continue

            reasoning_str = json.dumps(reasoning) if isinstance(reasoning, dict) else str(reasoning)

            if existing:
                conn.execute(
                    """UPDATE classification_log
                       SET match_type = ?, confidence = ?, rule_hits = ?, created_at = datetime('now')
                       WHERE id = ?""",
                    (match_type, confidence, reasoning_str, existing["id"]),
                )
            else:
                conn.execute(
                    """INSERT INTO classification_log
                       (source_type, source_id, matched_slug, match_type, confidence, rule_hits)
                       VALUES ('message', ?, ?, ?, ?, ?)""",
                    (msg_id, slug, match_type, confidence, reasoning_str),
                )

            # Mark classified + update tags
            conn.execute("UPDATE messages SET classified = 1 WHERE id = ?", (msg_id,))
            if slug:
                row = conn.execute("SELECT project_tags FROM messages WHERE id = ?", (msg_id,)).fetchone()
                tags = []
                try:
                    tags = json.loads(row["project_tags"] or "[]") if row else []
                except (json.JSONDecodeError, TypeError):
                    pass
                if slug not in tags:
                    tags.append(slug)
                conn.execute("UPDATE messages SET project_tags = ? WHERE id = ?",
                             (json.dumps(tags), msg_id))

            classified += 1
        except Exception as e:
            errors += 1
            print(json.dumps({"warning": f"Error on message {d.get('message_id')}: {e}"}),
                  file=sys.stderr)

    conn.commit()
    print(json.dumps({
        "status": "batch_complete",
        "classified": classified,
        "skipped": skipped,
        "errors": errors,
    }))
    conn.close()


# ── Subcommand: auto-create ──────────────────────────────────────────────

def cmd_auto_create(args):
    """Create a new deal or project entry for an unmatched message."""
    slug = args.slug or slugify(args.name)
    extra = {}
    if args.extra:
        try:
            extra = json.loads(args.extra)
        except json.JSONDecodeError:
            pass

    if args.type == "deal":
        # Create in deals.json
        deals = []
        if DEALS_PATH.exists():
            try:
                deals = json.loads(DEALS_PATH.read_text())
            except (json.JSONDecodeError, IOError):
                pass

        # Check for duplicate
        if any(d.get("slug") == slug for d in deals):
            print(json.dumps({"status": "exists", "type": "deal", "slug": slug}))
            return

        new_deal = {
            "slug": slug,
            "company_name": args.name,
            "stage": extra.get("stage", "sourced"),
            "status": "active",
            "source": args.source,
            "created": datetime.now().isoformat()[:10],
            "last_touch": datetime.now().isoformat()[:10],
            **{k: v for k, v in extra.items() if k not in ("stage",)},
        }
        deals.append(new_deal)
        DEALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        DEALS_PATH.write_text(json.dumps(deals, indent=2))
        entity_type = "deal"

    else:  # project
        projects = []
        if PROJECTS_PATH.exists():
            try:
                projects = json.loads(PROJECTS_PATH.read_text())
            except (json.JSONDecodeError, IOError):
                pass

        if any(p.get("slug") == slug for p in projects):
            print(json.dumps({"status": "exists", "type": "project", "slug": slug}))
            return

        new_project = {
            "slug": slug,
            "project_name": args.name,
            "project_type": extra.get("project_type", "general"),
            "category": extra.get("category", "uncategorized"),
            "status": "active",
            "source": args.source,
            "created": datetime.now().isoformat()[:10],
            "last_updated": datetime.now().isoformat()[:10],
            **{k: v for k, v in extra.items() if k not in ("project_type", "category")},
        }
        projects.append(new_project)
        PROJECTS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROJECTS_PATH.write_text(json.dumps(projects, indent=2))
        entity_type = "project"

    # If message_id provided, classify it to the new entity
    if args.message_id:
        conn = get_db()
        match_type = f"new_{entity_type}"
        conn.execute(
            """INSERT INTO classification_log
               (source_type, source_id, matched_slug, match_type, confidence, rule_hits)
               VALUES ('message', ?, ?, ?, 1.0, ?)""",
            (args.message_id, slug, match_type,
             json.dumps({"auto_created": True, "created_by": "claude"})),
        )
        conn.execute("UPDATE messages SET classified = 1 WHERE id = ?", (args.message_id,))
        conn.execute("UPDATE messages SET project_tags = ? WHERE id = ?",
                     (json.dumps([slug]), args.message_id))
        conn.commit()
        conn.close()

    # Rebuild indexes
    try:
        conn = get_db()
        sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))
        from rebuild_index import rebuild_company_index, rebuild_project_index
        rebuild_company_index(conn, str(DEALS_PATH))
        rebuild_project_index(conn, str(PROJECTS_PATH))
        conn.commit()
        conn.close()
    except Exception:
        pass

    print(json.dumps({
        "status": "created",
        "type": entity_type,
        "slug": slug,
        "name": args.name,
    }))


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="VFT RLM Classifier CLI — used by Claude Code for message classification",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # pending
    p_pending = subparsers.add_parser("pending", help="List unclassified messages")
    p_pending.add_argument("--source", default="all",
                           choices=["outlook", "slack", "whatsapp", "signal", "granola", "web", "calendar", "file_intake", "all"])
    p_pending.add_argument("--limit", type=int, default=50)

    # context
    p_context = subparsers.add_parser("context", help="Show deals/projects with signals")
    p_context.add_argument("--active-only", action="store_true", default=False)
    p_context.add_argument("--rebuild-index", action="store_true", default=True)
    p_context.add_argument("--no-rebuild-index", action="store_false", dest="rebuild_index")

    # detail
    p_detail = subparsers.add_parser("detail", help="Get full message content")
    p_detail.add_argument("--id", type=int, required=True)

    # classify
    p_classify = subparsers.add_parser("classify", help="Store a classification decision")
    p_classify.add_argument("--message-id", type=int, required=True)
    p_classify.add_argument("--slug", required=True, help="Deal/project slug")
    p_classify.add_argument("--match-type", required=True,
                            choices=["deal", "project", "new_deal", "new_project"])
    p_classify.add_argument("--confidence", type=float, default=1.0)
    p_classify.add_argument("--reasoning", type=str, default="{}")

    # batch-classify
    p_batch = subparsers.add_parser("batch-classify", help="Store multiple decisions")
    p_batch.add_argument("--decisions", required=True,
                         help='JSON array: [{"message_id": 1, "slug": "x", "match_type": "deal", ...}]')

    # auto-create
    p_create = subparsers.add_parser("auto-create", help="Create new deal/project")
    p_create.add_argument("--type", required=True, choices=["deal", "project"])
    p_create.add_argument("--name", required=True, help="Company/project name")
    p_create.add_argument("--slug", help="Override slug (auto-generated from name if omitted)")
    p_create.add_argument("--source", default="auto_classifier")
    p_create.add_argument("--message-id", type=int, help="Originating message ID")
    p_create.add_argument("--extra", help="JSON with additional fields")

    args = parser.parse_args()

    commands = {
        "pending": cmd_pending,
        "context": cmd_context,
        "detail": cmd_detail,
        "classify": cmd_classify,
        "batch-classify": cmd_batch_classify,
        "auto-create": cmd_auto_create,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
