# vft-fund-tools

A Claude Code / Cowork plugin for VC fund management. 33 skills and 15 slash commands covering the full fund workflow: deal sourcing, dataroom diligence, document processing, communication scanning, reactive monitoring, CRM contacts, Google Sheets dashboard, project management, and unified dashboards.

## Install

**Claude Code (local dev):**
```bash
claude --plugin-dir /path/to/this/repo
```

**Claude Code (from GitHub):**
```
/plugin marketplace add bwolfson2/claude_projects
/plugin install vft-fund-tools
```

**Cowork (Claude Desktop):**
Open Cowork tab > Customize > Browse plugins > Install `vft-fund-tools`, or upload the plugin directory.

## Commands

### Core Workflow
| Command | Description |
|---------|-------------|
| `/vft-fund-tools:status` | Unified dashboard across all workstreams |
| `/vft-fund-tools:new-deal` | Onboard a new company into the deal pipeline |
| `/vft-fund-tools:new-project` | Create a new project workspace |
| `/vft-fund-tools:process-dataroom` | Extract and analyze dataroom documents |
| `/vft-fund-tools:ingest` | Point at any URL, folder, or Drive link — auto-classify and route |

### Summaries & Memos
| Command | Description |
|---------|-------------|
| `/vft-fund-tools:summarize-deal` | Current-state deal summary with findings, risks, and next actions |
| `/vft-fund-tools:summarize-week` | Weekly digest across all workstreams |
| `/vft-fund-tools:summarize-thread` | Summarize any conversation thread |
| `/vft-fund-tools:write-memo` | Generate an IC-ready investment memo |

### CRM & Dashboard
| Command | Description |
|---------|-------------|
| `/vft-fund-tools:add-contact` | Add or update a contact in the CRM |
| `/vft-fund-tools:sync-sheet` | Push deals, projects, contacts to the Google Sheets dashboard |

### Monitoring & Automation
| Command | Description |
|---------|-------------|
| `/vft-fund-tools:scan-comms` | Scan all communication channels |
| `/vft-fund-tools:monitor` | Full sweep: scan → classify → reactively dispatch workflows |
| `/vft-fund-tools:watch` | Set up scheduled monitoring for all data feeds |
| `/vft-fund-tools:calendar` | Review upcoming meetings and auto-prep for calls |

## Skills (33, auto-invoked)

### Due Diligence
- **dataroom-intake** — Inventory and categorize dataroom files
- **document-processor** — RLM-style text extraction and structured analysis
- **startup-diligence-orchestrator** — End-to-end diligence coordination
- **finance-legal-diligence** — Financial and legal risk review
- **commercial-diligence-review** — Commercial quality assessment
- **product-technical-diligence** — Product and technical evaluation
- **diligence-memo-writer** — IC-ready memo generation

### CRM & Projects
- **fund-dealflow-orchestrator** — Deal pipeline and CRM management
- **crm-contacts** — Unified contact CRM across all communication platforms
- **deal-project-classifier** — Message classification and routing
- **project-management** — Non-DD project tracking
- **project-init** — Template-based workspace creation
- **project-tracker** — Unified cross-workstream dashboard
- **tracker-sync** — JSON to Excel sync
- **sheet-sync** — Google Sheets dashboard sync via gspread API

### Communication
- **comms-hub** — Master communication orchestrator
- **email-scanner** — Outlook inbox scanning
- **slack-scanner** — Slack workspace scanning
- **whatsapp-scanner** — WhatsApp Web scanning
- **signal-scanner** — Signal Desktop scanning
- **transcript-ingestion** — Meeting transcript ingestion
- **message-ingestion** — Unified message storage

### Monitoring & Routing
- **reactive-router** — Analyze incoming messages and dispatch workflows (dataroom processing, meeting prep, deal creation, urgent flagging)

### Research
- **web-researcher** — Company and market research via Chrome
- **data-puller** — API and web data fetching
- **source-analyst** — Individual source analysis
- **synthesis-writer** — Multi-source research synthesis

### Hiring
- **candidate-screener** — Resume evaluation
- **interview-coordinator** — Interview planning
- **comp-researcher** — Compensation benchmarking
- **outreach-drafter** — Candidate outreach

### Cross-cutting
- **action-extractor** — Action item extraction from messages
- **thread-summarizer** — Conversation thread summaries

## Connectors (Optional)

Connect external tools to supercharge the plugin:

| Connector | Skills Enhanced |
|-----------|----------------|
| **Outlook** | email-scanner, comms-hub, calendar |
| **Slack** | slack-scanner, comms-hub |
| **Google Drive** | dataroom-intake, document-processor, ingest |
| **Google Calendar** | calendar, monitor (morning prep) |
| **Granola** | transcript-ingestion |

## Reactive Monitoring

The `/monitor` command and `reactive-router` skill form a closed-loop system:

```
Data Feeds (email, Slack, WhatsApp, Signal, calendar, file drops)
    ↓ scan
Messages Table (ingestion.db)
    ↓ classify
Classification Log (deal/project matching)
    ↓ route
Reactive Router (pattern matching → action plan)
    ↓ execute
Fund Workflows (dataroom processing, deal creation, meeting prep, alerts)
```

Use `/watch` to automate this on a schedule.

## Dependencies

```bash
pip install pymupdf openpyxl python-pptx gspread google-auth
# Optional OCR: pip install pytesseract Pillow && brew install tesseract
```

## Google Sheets Dashboard

The plugin syncs fund data to a shared Google Sheet with tabs for DD Pipeline, Projects, CRM Contacts, and per-deal/per-project detail sheets.

**Setup:**
1. Create a Google Cloud service account with Sheets API enabled
2. Download the JSON key to `~/.config/gspread/service_account.json`
3. Run `/vft-fund-tools:sync-sheet setup` to create the sheet
4. Share the sheet with your team

**Google Drive sync:** The repo folder should be synced with Google Drive Desktop for automatic file access.

## License

MIT
