# Connectors

## How tool references work

Plugin files use `~~category` as a placeholder for whatever tool the user connects in that category. For example, `~~email` might mean Gmail or Outlook, and `~~file storage` might mean Google Drive or OneDrive.

Plugins are **tool-agnostic** — they describe workflows in terms of categories rather than specific products. The `.mcp.json` pre-configures specific MCP servers, but any MCP server in that category works.

## Connectors for this plugin

| Category | Placeholder | Included servers | Other options |
|----------|-------------|-----------------|---------------|
| Calendar | `~~calendar` | Google Calendar, Microsoft 365 | — |
| Chat | `~~chat` | Slack | Microsoft Teams |
| Email | `~~email` | Gmail, Microsoft 365 | — |
| File storage | `~~file storage` | Google Drive (built-in connector) | OneDrive (via ms365), Dropbox, Box |
| Knowledge base | `~~knowledge base` | Notion | Confluence, Guru |
| Meeting transcription | `~~transcripts` | Granola | Fireflies, Gong, Otter.ai |

## MCP Servers (in .mcp.json)

These are pre-configured in the plugin and will prompt for OAuth connection when installed:

| Server | URL | What it provides |
|--------|-----|-----------------|
| **ms365** | `microsoft365.mcp.claude.com/mcp` | Outlook email, OneDrive, SharePoint, Teams |
| **gmail** | `gmail.mcp.claude.com/mcp` | Gmail search and send |
| **google-calendar** | `gcal.mcp.claude.com/mcp` | Google Calendar events |
| **slack** | `mcp.slack.com/mcp` | Slack channels, DMs, threads |
| **notion** | `mcp.notion.com/mcp` | Notion pages and databases |
| **granola** | `mcp.granola.ai/mcp` | Meeting transcripts and notes |

## Built-in Cowork Connectors

These are activated through the Cowork UI (Customize > Connectors) rather than `.mcp.json`:

| Connector | How to enable | Skills enhanced |
|-----------|--------------|----------------|
| **Google Drive** | Cowork UI > Connectors > Google Drive | dataroom-intake, document-processor, ingest |

## No connectors? No problem.

Every skill in this plugin works standalone. Without connectors:
- Paste email content or forward to yourself and use `/ingest`
- Drop files into `fund/datarooms/` and run `/process-dataroom`
- Paste meeting notes and use `/summarize-thread`
- Manually enter deal info with `/new-deal`

Connectors make it faster, but nothing is blocked without them.
