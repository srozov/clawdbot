"""
Notion sync logic for application tracking.
"""
import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import aiofiles
from notion_client import Client
from notion_client.errors import APIResponseError

from .models import (
    ApplicationInput, NotionPageProperties, SyncResult, SyncSummary,
    SyncStatus, ApplicationStatus, NotionConfig
)
from .oauth import get_access_token


class NotionSyncEngine:
    """Engine for syncing applications to Notion."""

    def __init__(self, config: NotionConfig):
        self.config = config
        self.client: Optional[Client] = None
        self._sync_state_file = Path("tracking/notion-sync.json")

    async def initialize(self) -> bool:
        """Initialize Notion client with authentication."""
        access_token = get_access_token()

        if not access_token:
            raise ValueError("No valid access token found. Run 'notion-tracker auth' first.")

        self.client = Client(auth=access_token)
        return True

    async def load_applications(self, applications_dir: Path) -> List[ApplicationInput]:
        """Load applications from directory."""
        index_file = applications_dir / "index.json"

        if not index_file.exists():
            raise FileNotFoundError(f"Applications index not found: {index_file}")

        async with aiofiles.open(index_file, 'r') as f:
            index_data = json.loads(await f.read())

        applications = []

        for app_entry in index_data.get("applications", []):
            app_dir = applications_dir / app_entry.get("directory", "")
            metadata_file = app_dir / "metadata.json"

            if metadata_file.exists():
                async with aiofiles.open(metadata_file, 'r') as f:
                    metadata = json.loads(await f.read())

                application = ApplicationInput(
                    company=app_entry.get("company", metadata.get("company", "")),
                    title=app_entry.get("title", metadata.get("title", "")),
                    location=metadata.get("location"),
                    link=metadata.get("link"),
                    description=metadata.get("description"),
                    match_score=metadata.get("match_score", 0.0),
                    match_reasoning=metadata.get("match_reasoning"),
                    key_matches=metadata.get("key_matches", []),
                    missing_skills=metadata.get("missing_skills", []),
                    strategy_id=metadata.get("strategy_id"),
                    remote=metadata.get("remote"),
                    seniority=metadata.get("seniority"),
                    salary_estimate=metadata.get("salary_estimate"),
                    category=metadata.get("category"),
                    status=metadata.get("status", "Not Applied")
                )
                applications.append(application)

        return applications

    def _application_to_properties(self, app: ApplicationInput) -> Dict[str, Any]:
        """Convert application to Notion page properties."""
        properties = {
            "Company": {"title": [{"text": {"content": app.company}}]},
            "Job Title": {"rich_text": [{"text": {"content": app.title}}]},
            "Status": {"select": {"name": app.status}},
            "Match Score": {"number": app.match_score},
        }

        if app.location:
            properties["Location"] = {"rich_text": [{"text": {"content": app.location}}]}

        if app.link:
            properties["Job Link"] = {"url": app.link}

        if app.salary_estimate:
            properties["Salary Estimate"] = {"rich_text": [{"text": {"content": app.salary_estimate}}]}

        if app.match_reasoning:
            properties["Match Reasoning"] = {"rich_text": [{"text": {"content": app.match_reasoning[:2000]}}]}

        if app.category:
            properties["Category"] = {"select": {"name": app.category}}

        if app.remote:
            properties["Remote"] = {"select": {"name": app.remote}}

        if app.seniority:
            properties["Seniority"] = {"select": {"name": app.seniority}}

        if app.strategy_id:
            properties["Strategy ID"] = {"rich_text": [{"text": {"content": app.strategy_id}}]}

        if app.key_matches:
            properties["Key Matches"] = {"multi_select": [{"name": km} for km in app.key_matches[:10]]}

        if app.missing_skills:
            properties["Missing Skills"] = {"multi_select": [{"name": ms} for ms in app.missing_skills[:10]]}

        return properties

    async def _create_page(self, properties: Dict[str, Any]) -> Optional[str]:
        """Create a page in Notion database."""
        try:
            response = self.client.pages.create(
                parent={"database_id": self.config.database_id},
                properties=properties
            )
            return response["id"]
        except APIResponseError as e:
            raise ValueError(f"Notion API error: {e}")

    async def _create_child_page(self, parent_id: str, title: str, content: str) -> None:
        """Create a child page with content."""
        try:
            self.client.pages.create(
                parent={"page_id": parent_id},
                properties={"title": {"title": [{"text": {"content": title}}]}},
                children=[
                    {
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": content}}]
                        }
                    }
                ]
            )
        except APIResponseError as e:
            raise ValueError(f"Notion API error creating child page: {e}")

    async def sync_application(self, app: ApplicationInput, existing_pages: Dict[str, str] = None) -> SyncResult:
        """Sync a single application to Notion."""
        result = SyncResult(
            job_id=f"{app.company}_{app.title}".replace(" ", "_"),
            company=app.company,
            title=app.title,
            status=SyncStatus.PENDING
        )

        # Check for existing page
        page_id = None
        if existing_pages:
            page_id = existing_pages.get(result.job_id)

        properties = self._application_to_properties(app)

        try:
            if page_id:
                # Update existing page
                self.client.pages.update(
                    page_id=page_id,
                    properties=properties
                )
                result.status = SyncStatus.UPDATED
                result.notion_page_id = page_id
            else:
                # Create new page
                page_id = await self._create_page(properties)
                result.notion_page_id = page_id
                result.status = SyncStatus.SYNCED

            result.synced_at = datetime.now()

            # Create child pages for additional details
            if app.description:
                await self._create_child_page(
                    page_id,
                    f"Job Description - {app.title}",
                    app.description
                )

            if app.match_reasoning:
                await self._create_child_page(
                    page_id,
                    f"Match Analysis - {app.title}",
                    app.match_reasoning
                )

        except Exception as e:
            result.status = SyncStatus.FAILED
            result.error = str(e)

        return result

    async def sync_all(self, applications: List[ApplicationInput]) -> SyncSummary:
        """Sync all applications to Notion."""
        summary = SyncSummary(total_applications=len(applications))

        # Load existing sync state
        existing_pages = {}
        if self._sync_state_file.exists():
            async with aiofiles.open(self._sync_state_file, 'r') as f:
                sync_state = json.loads(await f.read())
                for app_state in sync_state.get("applications", []):
                    if app_state.get("notion_page_id") and app_state.get("job_id"):
                        existing_pages[app_state["job_id"]] = app_state["notion_page_id"]

        # Sync each application
        for app in applications:
            # Check if already synced (incremental mode)
            job_id = f"{app.company}_{app.title}".replace(" ", "_")

            if self.config.sync_mode == "incremental" and job_id in existing_pages:
                result = SyncResult(
                    job_id=job_id,
                    company=app.company,
                    title=app.title,
                    notion_page_id=existing_pages[job_id],
                    status=SyncStatus.SKIPPED,
                    synced_at=datetime.now()
                )
            else:
                result = await self.sync_application(app, existing_pages)

            # Update summary counts
            if result.status == SyncStatus.SYNCED or result.status == SyncStatus.UPDATED:
                summary.synced += 1
            elif result.status == SyncStatus.FAILED:
                summary.failed += 1
            elif result.status == SyncStatus.SKIPPED:
                summary.skipped += 1

            summary.results.append(result)

            # Respect rate limits
            await asyncio.sleep(self.config.rate_limit_delay)

        # Save sync state
        await self._save_sync_state(summary)

        return summary

    async def _save_sync_state(self, summary: SyncSummary) -> None:
        """Save sync state to file."""
        state = {
            "synced_at": summary.synced_at.isoformat(),
            "total_applications": summary.total_applications,
            "synced": summary.synced,
            "failed": summary.failed,
            "skipped": summary.skipped,
            "applications": [
                {
                    "job_id": r.job_id,
                    "company": r.company,
                    "title": r.title,
                    "notion_page_id": r.notion_page_id,
                    "status": r.status.value,
                    "synced_at": r.synced_at.isoformat() if r.synced_at else None,
                    "error": r.error
                }
                for r in summary.results
            ]
        }

        # Create tracking directory if needed
        self._sync_state_file.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(self._sync_state_file, 'w') as f:
            await f.write(json.dumps(state, indent=2))

    async def update_status(self, job_id: str, new_status: str, page_id: str) -> bool:
        """Update status of an existing Notion entry."""
        try:
            self.client.pages.update(
                page_id=page_id,
                properties={"Status": {"select": {"name": new_status}}}
            )
            return True
        except APIResponseError as e:
            raise ValueError(f"Failed to update status: {e}")

    async def get_sync_status(self) -> Dict[str, Any]:
        """Get current sync status."""
        if not self._sync_state_file.exists():
            return {"status": "no_sync", "message": "No sync has been performed yet"}

        async with aiofiles.open(self._sync_state_file, 'r') as f:
            sync_state = json.loads(await f.read())

        return {
            "status": "synced",
            "last_sync": sync_state.get("synced_at"),
            "total": sync_state.get("total_applications", 0),
            "synced": sync_state.get("synced", 0),
            "failed": sync_state.get("failed", 0),
            "skipped": sync_state.get("skipped", 0)
        }
