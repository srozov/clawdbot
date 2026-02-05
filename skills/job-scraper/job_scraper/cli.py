"""Job scraper CLI commands."""

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

import click

from .scraper import JobsCHScraper
from .models import GlobalConfig, JobSearchStrategy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_global_config(config_path: Optional[str] = None) -> GlobalConfig:
    """Load global configuration."""
    if config_path:
        return GlobalConfig.load(config_path)
    return GlobalConfig.load()


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file path")
@click.option("--headless/--no-headless", default=None, help="Run browser headless")
def cli(verbose: bool, config: str, headless: bool):
    """Job Scraper CLI - Scrape job postings from jobs.ch."""
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Store config path in context for commands
    cli.config_path = config
    cli.headless = headless


@cli.command()
@click.argument("strategy_file", type=click.Path(exists=True))
@click.option("--output-dir", "-o", default=None, help="Output directory for raw jobs")
@click.option("--parallel", "-p", default=None, help="Number of parallel strategies")
@click.option("--max-per-strategy", default=None, help="Max jobs per strategy")
@click.option("--incremental/--no-incremental", default=True, help="Skip already-scraped jobs")
@click.option("--headless/--no-headless", default=None, help="Run browser headless")
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file path")
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def run(
    strategy_file: str,
    output_dir: str,
    parallel: int,
    max_per_strategy: int,
    incremental: bool,
    headless: bool,
    config: str,
    verbose: bool
):
    """Run job scraping with strategies from a JSON file.
    
    STRATEGY_FILE is a JSON file containing search strategies.
    """
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load configuration
    config_path = config or getattr(cli, 'config_path', None)
    global_config = load_global_config(config_path)
    
    # Override with CLI options
    if output_dir:
        global_config.jobs_dir = output_dir
    if parallel:
        global_config.max_parallel_strategies = parallel
    if max_per_strategy:
        global_config.max_jobs_per_strategy = max_per_strategy
    if headless is not None:
        global_config.headless = headless
    
    # Load strategies
    with open(strategy_file, "r") as f:
        strategies_data = json.load(f)
    
    strategies = [
        JobSearchStrategy(**s) for s in strategies_data.get("strategies", [])
    ]
    
    if not strategies:
        raise click.ClickException("No strategies found in strategy file")
    
    click.echo(f"🚀 Starting job scraping with {len(strategies)} strategies")
    click.echo(f"📁 Output directory: {global_config.jobs_dir}")
    click.echo(f"🔄 Incremental mode: {'enabled' if incremental else 'disabled'}")
    
    scraper = JobsCHScraper(config=global_config)
    
    async def run_scraping():
        return await scraper.run_strategies(strategies, incremental=incremental)
    
    try:
        results = asyncio.run(run_scraping())
        
        click.echo(f"\n✅ Scraping complete!")
        click.echo(f"📊 Total jobs found: {results.total_jobs_found}")
        click.echo(f"📊 Total jobs extracted: {results.total_jobs_extracted}")
        click.echo(f"📊 Already scraped (skipped): {results.incremental_skipped}")
        click.echo(f"📊 Failed: {results.total_failed}")
        click.echo(f"⏱️ Duration: {results.duration_seconds:.1f}s")
        
        # Save index
        index = scraper.get_output_index()
        index_path = Path(global_config.jobs_dir) / "index.json"
        
        with open(index_path, "w") as f:
            f.write(json.dumps({
                "total_jobs": results.total_jobs_extracted,
                "total_skipped": results.incremental_skipped,
                "duration_seconds": results.duration_seconds,
                "strategy_stats": results.strategy_stats
            }, indent=2))
        
        click.echo(f"\n📁 Output saved to: {global_config.jobs_dir}")
        click.echo(f"📋 Index: {index_path}")
        
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise click.ClickException(str(e))


@cli.command()
@click.argument("job_title")
@click.argument("location")
@click.option("--output-dir", "-o", default=None, help="Output directory")
@click.option("--max-jobs", default=None, help="Maximum jobs to collect")
@click.option("--headless/--no-headless", default=None, help="Run browser headless")
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file path")
def scrape_single(
    job_title: str,
    location: str,
    output_dir: str,
    max_jobs: int,
    headless: bool,
    config: str
):
    """Scrape jobs for a single search strategy.
    
    JOB_TITLE is the job title to search for.
    LOCATION is the geographic location.
    """
    # Load configuration
    global_config = load_global_config(config)
    
    if output_dir:
        global_config.jobs_dir = output_dir
    if max_jobs:
        global_config.max_jobs_per_strategy = max_jobs
    if headless is not None:
        global_config.headless = headless
    
    strategy = JobSearchStrategy(
        job_title=job_title,
        location=location,
        max_jobs=max_jobs or 50,
        strategy_id="single"
    )
    
    scraper = JobsCHScraper(config=global_config)
    
    async def run_single():
        return await scraper.run_strategies([strategy])
    
    try:
        results = asyncio.run(run_single())
        click.echo(f"✅ Found {results.total_jobs_extracted} jobs")
        click.echo(f"📁 Output: {global_config.jobs_dir}")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise click.ClickException(str(e))


@cli.command()
@click.argument("strategy_json")
@click.option("--output-dir", "-o", default=None, help="Output directory")
@click.option("--headless/--no-headless", default=None, help="Run browser headless")
@click.option("--config", "-c", type=click.Path(exists=True), help="Config file path")
def from_json(
    strategy_json: str,
    output_dir: str,
    headless: bool,
    config: str
):
    """Run scraping from inline JSON strategy.
    
    STRATEGY_JSON is a JSON string with job_title and location.
    Example: '{"job_title": "Python Developer", "location": "Zürich"}'
    """
    try:
        strategy_data = json.loads(strategy_json)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON: {e}")
    
    # Load configuration
    global_config = load_global_config(config)
    
    if output_dir:
        global_config.jobs_dir = output_dir
    if headless is not None:
        global_config.headless = headless
    
    strategy = JobSearchStrategy(
        job_title=strategy_data["job_title"],
        location=strategy_data["location"],
        max_jobs=strategy_data.get("max_jobs", 50),
        strategy_id=strategy_data.get("strategy_id", "inline")
    )
    
    scraper = JobsCHScraper(config=global_config)
    
    async def run_inline():
        return await scraper.run_strategies([strategy])
    
    try:
        results = asyncio.run(run_inline())
        click.echo(f"✅ Extracted {results.total_jobs_extracted} jobs")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        raise click.ClickException(str(e))


@cli.command()
@click.argument("output_dir", type=click.Path(exists=True))
def status(output_dir: str):
    """Show scraping status and statistics."""
    output_path = Path(output_dir)
    index_file = output_path / "index.json"
    
    # Count job files
    job_files = list(output_path.glob("*.json"))
    
    # Exclude index.json
    job_files = [f for f in job_files if f.name != "index.json"]
    
    click.echo(f"📊 Job Scraper Status")
    click.echo(f"   Jobs directory: {output_dir}")
    click.echo(f"   Total jobs: {len(job_files)}")
    
    if index_file.exists():
        with open(index_file, "r") as f:
            data = json.load(f)
        
        click.echo(f"   Duration: {data.get('duration_seconds', 0):.1f}s")
        
        strategy_stats = data.get("strategy_stats", [])
        if strategy_stats:
            click.echo(f"\n📋 Strategy Statistics:")
            for stat in strategy_stats:
                strategy_id = stat.get("strategy_id", "?")
                found = stat.get("jobs_found", 0)
                extracted = stat.get("jobs_extracted", 0)
                skipped = stat.get("skipped", 0)
                click.echo(f"   [{strategy_id}] {found} found, {extracted} extracted, {skipped} skipped")


@cli.command()
@click.option("--config", "-c", default="config/global.json", help="Config file path")
def init_config(config: str):
    """Initialize global configuration file."""
    global_config = GlobalConfig()
    global_config.save(config)
    click.echo(f"✅ Configuration saved to: {config}")
    click.echo("\nYou can now edit the config file to customize settings.")


if __name__ == "__main__":
    cli()
