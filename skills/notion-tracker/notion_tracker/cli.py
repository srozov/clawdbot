"""
Click CLI for notion-tracker skill.
"""
import json
import os
from pathlib import Path
from typing import Optional

import click
import asyncio
from datetime import datetime

from .models import NotionConfig
from .sync import NotionSyncEngine
from .oauth import get_access_token, run_oauth_flow, OAuthHandler


@click.group()
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to config file")
@click.pass_context
def main(ctx, config: Optional[str]):
    """Notion Tracker - Sync job applications to Notion database."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config


@main.command()
@click.pass_context
def auth(ctx):
    """Authenticate with Notion via OAuth."""
    click.echo("Starting Notion OAuth authentication...")

    try:
        access_token = run_oauth_flow()
        click.echo(f"✅ Authentication successful! Token saved.")
    except ValueError as e:
        click.echo(f"❌ Error: {e}")
        raise click.ClickException(str(e))
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e}")
        raise click.ClickException(str(e))


@main.command()
@click.argument("applications_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--database-id", "-d", required=True, help="Notion database ID")
@click.option("--sync-mode", "-m", type=click.Choice(["incremental", "full"]), default="incremental")
@click.pass_context
def sync(ctx, applications_dir: str, database_id: str, sync_mode: str):
    """Sync all applications to Notion database."""
    config_path = ctx.obj.get("config")
    config = _load_config(config_path)

    # Override database_id from args
    config.database_id = database_id
    config.sync_mode = sync_mode

    click.echo(f"🔄 Syncing applications from: {applications_dir}")
    click.echo(f"📊 Database ID: {database_id}")
    click.echo(f"🔄 Sync mode: {sync_mode}")

    async def run_sync():
        engine = NotionSyncEngine(config)
        await engine.initialize()

        applications = await engine.load_applications(Path(applications_dir))
        click.echo(f"📋 Loaded {len(applications)} applications")

        summary = await engine.sync_all(applications)

        click.echo("\n" + "=" * 50)
        click.echo("📊 Sync Summary")
        click.echo("=" * 50)
        click.echo(f"  Total applications: {summary.total_applications}")
        click.echo(f"  ✅ Synced: {summary.synced}")
        click.echo(f"  ⏭️  Skipped: {summary.skipped}")
        click.echo(f"  ❌ Failed: {summary.failed}")
        click.echo(f"  🕐 Last sync: {summary.synced_at.isoformat()}")

        # Show failed items
        if summary.failed > 0:
            click.echo("\n❌ Failed applications:")
            for result in summary.results:
                if result.status.value == "failed":
                    click.echo(f"  - {result.company} - {result.title}: {result.error}")

        return summary

    try:
        asyncio.run(run_sync())
        click.echo("\n✅ Sync complete!")
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.argument("app_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--database-id", "-d", required=True, help="Notion database ID")
@click.pass_context
def sync_one(ctx, app_dir: str, database_id: str):
    """Sync a single application to Notion."""
    config_path = ctx.obj.get("config")
    config = _load_config(config_path)

    config.database_id = database_id

    click.echo(f"🔄 Syncing single application: {app_dir}")

    async def run_sync():
        engine = NotionSyncEngine(config)
        await engine.initialize()

        # Load application from directory
        metadata_file = Path(app_dir) / "metadata.json"
        if not metadata_file.exists():
            raise click.ClickException(f"Metadata file not found: {metadata_file}")

        with open(metadata_file, 'r') as f:
            metadata = json.load(f)

        # Create ApplicationInput
        from .models import ApplicationInput
        app = ApplicationInput(
            company=metadata.get("company", Path(app_dir).name.split("_")[0]),
            title=metadata.get("title", Path(app_dir).name),
            location=metadata.get("location"),
            link=metadata.get("link"),
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

        summary = await engine.sync_all([app])

        if summary.failed > 0:
            for result in summary.results:
                if result.status.value == "failed":
                    click.echo(f"❌ Failed: {result.error}")
            raise click.ClickException("Sync failed")

        click.echo(f"✅ Synced: {app.company} - {app.title}")

    try:
        asyncio.run(run_sync())
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.argument("app_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--status", "-s", required=True, type=click.Choice(["Not Applied", "Applied", "Interview Scheduled", "Rejected", "Offer"]))
@click.pass_context
def update(ctx, app_dir: str, status: str):
    """Update status of an existing Notion entry."""
    click.echo(f"📝 Updating status to: {status}")

    async def run_update():
        # Load sync state to find page ID
        sync_state_file = Path("tracking/notion-sync.json")
        if not sync_state_file.exists():
            raise click.ClickException("No sync state found. Run sync first.")

        with open(sync_state_file, 'r') as f:
            sync_state = json.load(f)

        app_name = Path(app_dir).name
        page_id = None

        for app_state in sync_state.get("applications", []):
            if app_state.get("job_id") == app_name:
                page_id = app_state.get("notion_page_id")
                break

        if not page_id:
            raise click.ClickException(f"No Notion page found for {app_name}")

        # Get config and initialize
        config_path = ctx.obj.get("config")
        config = _load_config(config_path)

        engine = NotionSyncEngine(config)
        await engine.initialize()

        success = await engine.update_status(app_name, status, page_id)

        if success:
            click.echo(f"✅ Updated status for {app_name}")
        else:
            raise click.ClickException("Failed to update status")

    try:
        asyncio.run(run_update())
    except Exception as e:
        raise click.ClickException(str(e))


@main.command()
@click.pass_context
def status(ctx):
    """Check sync status."""
    async def check_status():
        config_path = ctx.obj.get("config")
        config = _load_config(config_path)

        engine = NotionSyncEngine(config)
        await engine.initialize()

        status = await engine.get_sync_status()

        if status.get("status") == "no_sync":
            click.echo("📊 No sync has been performed yet.")
        else:
            click.echo("📊 Sync Status")
            click.echo("=" * 50)
            click.echo(f"  Last sync: {status.get('last_sync', 'Unknown')}")
            click.echo(f"  Total: {status.get('total', 0)}")
            click.echo(f"  ✅ Synced: {status.get('synced', 0)}")
            click.echo(f"  ❌ Failed: {status.get('failed', 0)}")
            click.echo(f"  ⏭️  Skipped: {status.get('skipped', 0)}")

    try:
        asyncio.run(check_status())
    except Exception as e:
        raise click.ClickException(str(e))


def _load_config(config_path: Optional[str]) -> NotionConfig:
    """Load configuration from file."""
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config_data = json.load(f)
        return NotionConfig(**config_data)

    # Default config
    return NotionConfig(
        database_id="",
        oauth_enabled=True,
        sync_mode="incremental",
        default_status="Not Applied"
    )
