---
description: Run the VFT setup wizard to configure your fund tools, communication channels, and connectors
argument-hint: ""
---

# /setup

> Configure VFT fund tools for first use or reconfigure an existing setup.

## Execution

Run the setup wizard interactively by following the workflow in `skills/project-init/scripts/setup_wizard.py`.

### Steps

1. **Check for existing config** — Call `load_config()` from setup_wizard.py. If config exists and `setup_completed` is true, ask the user if they want to reconfigure.

2. **Fund Identity** — Ask for fund name, primary user name, and email address.

3. **Communication Channels** — Ask which channels to enable:
   - Email (Outlook or Gmail)
   - Calendar (Google Calendar or Outlook Calendar)
   - Slack (workspace name)
   - WhatsApp (groups/contacts to monitor)
   - Signal
   - Granola (meeting transcripts)

4. **Connector Check** — Call `check_connector_status()` to verify which MCP connectors are available. Report what's connected vs what will use browser automation.

5. **Google Sheets** — Optionally configure dashboard sync to Google Sheets.

6. **Initialize** — Run database init and index rebuild.

7. **Summary** — Show what was configured and any remaining manual steps.

### Quick Validation

To just check if setup is complete:
```
python skills/project-init/scripts/setup_wizard.py --check
```

To view current configuration:
```
python skills/project-init/scripts/setup_wizard.py --show
```
