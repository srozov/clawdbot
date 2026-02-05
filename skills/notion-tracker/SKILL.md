# Notion Tracker Skill

**Version:** 1.0.0  
**Description:** Sync job applications to Notion database with OAuth authentication  
**Dependencies:** notion-client, requests-oauthlib, click, pydantic

---

## Overview

The `notion-tracker` skill synchronizes job application data to a Notion database. It handles:
- Notion OAuth authentication flow
- Database schema mapping for job applications
- File uploads (cover letters, CVs)
- Incremental sync with conflict resolution
- Status tracking and updates

## Installation

```bash
pip install notion-tracker
```

## Configuration

Create `config/notion-config.json`:

```json
{
  "database_id": "your-notion-database-id",
  "oauth_enabled": true,
  "sync_mode": "incremental",
  "default_status": "Not Applied"
}
```

Set environment variables:
```bash
export NOTION_CLIENT_ID="your-client-id"
export NOTION_CLIENT_SECRET="your-client-secret"
export NOTION_REDIRECT_URI="http://localhost:8080/callback"
```

## Usage

### OAuth Authentication
```bash
notion-tracker auth
```
Opens OAuth flow to authorize Notion access.

### Sync All Applications
```bash
notion-tracker sync --applications applications/ --database-id <notion-db-id>
```

### Sync Single Application
```bash
notion-tracker sync-one --app applications/Google_Senior_Engineer/
```

### Update Status
```bash
notion-tracker update --app applications/Google_Senior_Engineer/ --status "Interview Scheduled"
```

### Check Sync Status
```bash
notion-tracker status
```

## Input/Output

### Inputs
- `inputs/applications/index.json` - Application index
- `inputs/applications/{company}_{title}/` - Application files (cover_letter.md, cv.md, metadata.json)

### Outputs
- `tracking/notion-sync.json` - Sync status and Notion page IDs
- Notion database entries (pages with child pages for details)

## Notion Database Schema

### Standard Fields
| Property | Type | Description |
|----------|------|-------------|
| Company | title | Company name |
| Job Title | text | Position title |
| Location | text | Job location |
| Application Date | date | When applied |
| Status | select | Not Applied, Applied, Interview Scheduled, Rejected, Offer |
| Match Score | number | 0-1 float |
| Salary Estimate | text | Salary range |
| Job Link | url | Link to posting |
| Cover Letter | file | Cover letter document |
| CV | file | Customized CV document |

### Custom Fields
| Property | Type | Description |
|----------|------|-------------|
| Match Reasoning | text | Detailed match explanation |
| Category | select | core, adjacent, growth |
| Priority | select | High, Medium, Low |
| Next Action | text | Next step to take |
| Custom Notes | rich_text | Additional notes |
| Key Matches | multi-select | Aligned strengths |
| Missing Skills | multi-select | Skill gaps |
| Strategy ID | text | Strategy that generated this |
| Remote | select | remote, hybrid, on-site |
| Seniority | select | junior, mid-level, senior, lead |

## File Structure

```
notion-tracker/
├── SKILL.md
├── pyproject.toml
├── scripts/
│   └── run.py
├── notion_tracker/
│   ├── __init__.py
│   ├── cli.py
│   ├── sync.py
│   ├── oauth.py
│   └── models.py
├── inputs/
│   └── applications/
│       └── index.json
├── config/
│   └── notion-config.json
├── tracking/
│   └── notion-sync.json
└── tests/
    └── test_sync.py
```

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| NOTION_CLIENT_ID | Yes | OAuth client ID |
| NOTION_CLIENT_SECRET | Yes | OAuth client secret |
| NOTION_REDIRECT_URI | No | OAuth redirect URI (default: http://localhost:8080/callback) |
| NOTION_ACCESS_TOKEN | No | Direct access token (alternative to OAuth) |

## Sync Modes

### Incremental (default)
Only syncs new or modified applications. Skips already-synced entries.

### Full
Forces re-sync of all applications, overwriting existing Notion entries.

## Error Handling

- Rate limiting: Respects Notion API limits (3 requests/second)
- Retry logic: Automatic retry with exponential backoff
- Conflict resolution: Last-write-wins with timestamp comparison

## License

MIT
