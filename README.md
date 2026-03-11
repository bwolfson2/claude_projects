# vft-fund-tools

A Claude Code / Cowork plugin for VC fund management. 30 skills and 5 slash commands covering the full fund workflow: deal sourcing, dataroom diligence, document processing, communication scanning, project management, and unified dashboards.

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

| Command | Description |
|---------|-------------|
| `/vft-fund-tools:status` | Unified dashboard across all workstreams |
| `/vft-fund-tools:new-deal` | Onboard a new company into the deal pipeline |
| `/vft-fund-tools:process-dataroom` | Extract and analyze dataroom documents |
| `/vft-fund-tools:scan-comms` | Scan all communication channels |
| `/vft-fund-tools:new-project` | Create a new project workspace |

## Skills (auto-invoked)

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
- **deal-project-classifier** — Message classification and routing
- **project-management** — Non-DD project tracking
- **project-init** — Template-based workspace creation
- **project-tracker** — Unified cross-workstream dashboard
- **tracker-sync** — JSON to Excel sync

### Communication
- **comms-hub** — Master communication orchestrator
- **email-scanner** — Outlook inbox scanning
- **slack-scanner** — Slack workspace scanning
- **whatsapp-scanner** — WhatsApp Web scanning
- **signal-scanner** — Signal Desktop scanning
- **transcript-ingestion** — Meeting transcript ingestion
- **message-ingestion** — Unified message storage

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
| **Outlook** | email-scanner, comms-hub |
| **Slack** | slack-scanner, comms-hub |
| **Google Drive** | dataroom-intake, document-processor |
| **Granola** | transcript-ingestion |

## Dependencies

```bash
pip install pymupdf openpyxl python-pptx
# Optional OCR: pip install pytesseract Pillow && brew install tesseract
```

## License

MIT
