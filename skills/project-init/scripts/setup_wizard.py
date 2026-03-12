#!/usr/bin/env python3
"""
VFT Setup Wizard — Interactive Configuration for Fund Tools

This script is designed to be executed by Claude (not run standalone).
Claude reads this script, follows the WORKFLOW section, asks the user
questions conversationally, and calls the helper functions to write
configuration and initialize the system.

Standalone helpers:
    python setup_wizard.py --check       # Validate existing config
    python setup_wizard.py --show        # Show current config
    python setup_wizard.py --init-only   # Just init DB + rebuild index
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parents[3]  # skills/project-init/scripts → repo root
CONFIG_PATH = REPO_ROOT / "fund" / "metadata" / "config.json"
DB_PATH = REPO_ROOT / "fund" / "metadata" / "db" / "ingestion.db"
MCP_CONFIG_PATH = REPO_ROOT / ".mcp.json"

# ── Default Config ───────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "fund_name": "",
    "primary_user": "",
    "primary_email": "",
    "channels": {
        "email": {"enabled": True, "provider": "outlook"},
        "calendar": {"enabled": True, "provider": "google", "fallback_provider": "outlook"},
        "slack": {"enabled": True, "workspace": ""},
        "whatsapp": {"enabled": False, "targets": []},
        "signal": {"enabled": False},
        "granola": {"enabled": True},
    },
    "google_sheet_id": None,
    "setup_completed": False,
    "setup_date": None,
}

# ── Channel Descriptions ────────────────────────────────────────────────
CHANNEL_INFO = {
    "email": {
        "name": "Email",
        "description": "Scan inbox for deal-related emails",
        "providers": {"outlook": "Microsoft Outlook (via ms365 MCP or Chrome)",
                      "gmail": "Gmail (via Gmail MCP or Chrome)"},
        "mcp_keys": {"outlook": "ms365", "gmail": "gmail"},
    },
    "calendar": {
        "name": "Calendar",
        "description": "Scan calendar events and match attendees to deals",
        "providers": {"google": "Google Calendar (via MCP or Chrome)",
                      "outlook": "Outlook Calendar (via ms365 MCP or Chrome)"},
        "mcp_keys": {"google": "google-calendar", "outlook": "ms365"},
    },
    "slack": {
        "name": "Slack",
        "description": "Scan Slack channels and DMs for deal-related messages",
        "providers": None,
        "mcp_keys": {"default": "slack"},
    },
    "whatsapp": {
        "name": "WhatsApp",
        "description": "Scan WhatsApp groups and contacts for messages",
        "providers": None,
        "mcp_keys": {"default": "whatsapp"},
    },
    "signal": {
        "name": "Signal",
        "description": "Scan Signal conversations for messages",
        "providers": None,
        "mcp_keys": {"default": "signal"},
    },
    "granola": {
        "name": "Granola (Meeting Transcripts)",
        "description": "Pull meeting transcripts from Granola",
        "providers": None,
        "mcp_keys": {"default": "granola"},
    },
}


def load_config() -> dict:
    """Load existing config or return defaults."""
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> str:
    """Save config to fund/metadata/config.json. Returns the path."""
    config["setup_completed"] = True
    config["setup_date"] = datetime.now().strftime("%Y-%m-%d")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return str(CONFIG_PATH)


def validate_config(config: dict) -> list:
    """Validate config and return list of issues."""
    issues = []
    if not config.get("fund_name"):
        issues.append("fund_name is empty")
    if not config.get("primary_email"):
        issues.append("primary_email is empty")
    channels = config.get("channels", {})
    if not any(ch.get("enabled") for ch in channels.values()):
        issues.append("No communication channels are enabled")
    return issues


def get_mcp_connectors() -> dict:
    """Read .mcp.json to find configured connectors."""
    if MCP_CONFIG_PATH.exists():
        try:
            data = json.loads(MCP_CONFIG_PATH.read_text())
            return data.get("mcpServers", {})
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def check_connector_status() -> dict:
    """Check which MCP connectors are configured in .mcp.json."""
    connectors = get_mcp_connectors()
    status = {}
    for channel_key, info in CHANNEL_INFO.items():
        mcp_keys = info.get("mcp_keys", {})
        found = []
        for label, mcp_key in mcp_keys.items():
            if mcp_key in connectors:
                found.append({"key": mcp_key, "label": label,
                              "type": connectors[mcp_key].get("type", "unknown")})
        status[channel_key] = {
            "name": info["name"],
            "configured_connectors": found,
            "has_connector": len(found) > 0,
        }
    return status


def init_database() -> bool:
    """Initialize the ingestion database if it doesn't exist."""
    if DB_PATH.exists():
        return True
    try:
        sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))
        from init_db import init_db
        init_db(str(DB_PATH))
        return True
    except Exception as e:
        print(f"[VFT] Failed to initialize database: {e}")
        return False


def rebuild_index() -> bool:
    """Rebuild the classification index."""
    try:
        sys.path.insert(0, str(REPO_ROOT / "fund" / "metadata"))
        from rebuild_index import rebuild_index as _rebuild
        conn = _rebuild(str(DB_PATH))
        if hasattr(conn, 'close'):
            conn.close()
        return True
    except Exception as e:
        print(f"[VFT] Failed to rebuild index: {e}")
        return False


def get_setup_summary(config: dict) -> str:
    """Generate a human-readable summary of the configuration."""
    lines = []
    lines.append(f"Fund: {config.get('fund_name', 'Not set')}")
    lines.append(f"User: {config.get('primary_user', 'Not set')} ({config.get('primary_email', 'Not set')})")
    lines.append("")
    lines.append("Channels:")
    channels = config.get("channels", {})
    for key, info in CHANNEL_INFO.items():
        ch = channels.get(key, {})
        enabled = ch.get("enabled", False)
        status_str = "Enabled" if enabled else "Disabled"
        provider = ch.get("provider", "")
        extra = f" ({provider})" if provider else ""
        lines.append(f"  {info['name']}: {status_str}{extra}")
        if key == "whatsapp" and enabled:
            targets = ch.get("targets", [])
            if targets:
                lines.append(f"    Targets: {', '.join(targets)}")
        if key == "slack" and enabled:
            ws = ch.get("workspace", "")
            if ws:
                lines.append(f"    Workspace: {ws}")
    lines.append("")
    sheet_id = config.get("google_sheet_id")
    lines.append(f"Google Sheet: {'Configured' if sheet_id else 'Not configured'}")
    lines.append(f"Database: {'Exists' if DB_PATH.exists() else 'Not initialized'}")
    return "\n".join(lines)


# ── WORKFLOW (for Claude to follow) ──────────────────────────────────────
"""
CLAUDE SETUP WIZARD WORKFLOW:

This is a conversational setup flow. Ask the user questions one at a time
using the AskUserQuestion tool, validate answers, and build the config.

1. LOAD EXISTING CONFIG
   - Call load_config() to check if config.json already exists
   - If it exists and setup_completed is True, ask the user if they want
     to reconfigure or just view the current config
   - If no config exists, proceed with fresh setup

2. FUND IDENTITY
   Ask the user:
   - "What is your fund name?" (e.g., "VFT", "Acme Ventures")
   - "What is your name?" (primary user)
   - "What is your email address?" (primary email, used for calendar matching)

3. COMMUNICATION CHANNELS
   For each channel, ask if they want to enable it:
   - "Which communication channels do you use?"
     Options: Email, Calendar, Slack, WhatsApp, Signal, Granola
     (multi-select)

   For enabled channels with provider options:
   - Email: "Do you use Outlook or Gmail?"
   - Calendar: "Do you use Google Calendar or Outlook Calendar?"

   For Slack: "What is your Slack workspace name?"
   For WhatsApp: "Which WhatsApp groups/contacts should be monitored?"
     (collect as comma-separated list)

4. CHECK CONNECTORS
   - Call check_connector_status() to see which MCP connectors are configured
   - Report to the user:
     "I found these connectors configured: [list]"
     "These channels will need browser automation: [list]"
   - If a needed connector is missing, suggest:
     "You can connect [service] later via the MCP connector settings"

5. GOOGLE SHEETS (optional)
   - "Do you want to sync your dashboard to Google Sheets?"
   - If yes: "What is your Google Sheet ID?" (or note to run create_sheet.py later)

6. INITIALIZE SYSTEM
   - Call init_database() to ensure DB exists
   - Call save_config(config) to write config.json
   - Call rebuild_index() to seed classification indexes
   - Report results

7. SUMMARY
   - Call get_setup_summary(config) and display to user
   - List any remaining manual steps:
     - MCP connectors that need to be connected
     - Google Sheets service account setup
     - WhatsApp Web / Signal session setup
   - Mention: "Run /scan-comms to start scanning your messages"
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VFT Setup Wizard helpers")
    parser.add_argument("--check", action="store_true",
                        help="Validate existing config")
    parser.add_argument("--show", action="store_true",
                        help="Show current config")
    parser.add_argument("--init-only", action="store_true",
                        help="Just init DB and rebuild index")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing config")
    args = parser.parse_args()

    if args.show:
        config = load_config()
        if config.get("setup_completed"):
            print(get_setup_summary(config))
        else:
            print("[VFT] No configuration found. Run /setup to configure.")
        sys.exit(0)

    if args.check:
        config = load_config()
        if not config.get("setup_completed"):
            print("[VFT] Setup not completed. Run /setup to configure.")
            sys.exit(1)
        issues = validate_config(config)
        if issues:
            print(f"[VFT] Config issues found:")
            for issue in issues:
                print(f"  - {issue}")
            sys.exit(1)
        else:
            print("[VFT] Config is valid.")
            connector_status = check_connector_status()
            for key, status in connector_status.items():
                channels = config.get("channels", {})
                ch = channels.get(key, {})
                if ch.get("enabled"):
                    icon = "OK" if status["has_connector"] else "BROWSER"
                    print(f"  {status['name']}: {icon}")
        sys.exit(0)

    if args.init_only:
        print("[VFT] Initializing database...")
        if init_database():
            print("[VFT] Database ready.")
        print("[VFT] Rebuilding index...")
        if rebuild_index():
            print("[VFT] Index rebuilt.")
        sys.exit(0)

    # Default: show help
    print("[VFT] Setup wizard helpers.")
    print("  This script is designed to be run by Claude via the /setup command.")
    print("  Available flags:")
    print("    --check     Validate existing config")
    print("    --show      Show current config")
    print("    --init-only Init DB and rebuild index")
    print("    --force     Overwrite existing config")
