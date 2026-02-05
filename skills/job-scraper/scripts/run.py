#!/usr/bin/env python3
"""
Job Scraper Skill - Scrape job postings from job boards using browser automation.

Part of the OpenClaw job-application-agency workflow.
Uses parallel execution patterns (preserving 100 jobs/5min mindset).

Usage:
    python scripts/run.py [--force] [--config CONFIG_PATH]

Input:
    inputs/strategies.json - Job search strategies from career-strategy skill
    inputs/resume.md - Resume for reference (optional, for keyword extraction)

Output:
    jobs/raw/{strategy_id}/{job_id}.json - Scraped job postings
    jobs/index.json - Index file with statistics
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add skill package to path
SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT / "job_scraper"))

from job_scraper.scraper import JobsCHScraper
from job_scraper.models import GlobalConfig, JobSearchStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def eprint(msg: str) -> None:
    """Print to stderr."""
    print(msg, file=sys.stderr)


def load_config(config_path: Optional[Path] = None) -> GlobalConfig:
    """Load configuration from global and skill-specific config files."""
    # Check for skill-specific config first
    skill_config_path = SKILL_ROOT / "config" / "job-scraper-config.json"
    
    # Load from file if it exists, otherwise use defaults
    if skill_config_path.exists():
        try:
            config = GlobalConfig.load(str(skill_config_path))
            logger.info(f"Loaded skill config from: {skill_config_path}")
            return config
        except Exception as e:
            logger.warning(f"Failed to parse skill config: {e}")
    
    # Load from global config path if provided
    if config_path and Path(config_path).exists():
        config = GlobalConfig.load(str(config_path))
        logger.info(f"Loaded config from: {config_path}")
        return config
    
    # Return default config
    logger.info("Using default configuration")
    return GlobalConfig()


def ensure_directories():
    """Ensure required directories exist."""
    (SKILL_ROOT / "inputs").mkdir(exist_ok=True)
    (SKILL_ROOT / "jobs" / "raw").mkdir(parents=True, exist_ok=True)
    (SKILL_ROOT / ".cache" / "job-scraper").mkdir(parents=True, exist_ok=True)


def load_strategies(strategies_path: Path) -> list[dict]:
    """Load job search strategies from JSON file."""
    if not strategies_path.exists():
        raise FileNotFoundError(f"Strategies file not found: {strategies_path}")
    
    with open(strategies_path, "r") as f:
        data = json.load(f)
    
    strategies = data.get("strategies", [])
    if not strategies:
        raise ValueError("No strategies found in strategies file")
    
    logger.info(f"Loaded {len(strategies)} strategies from: {strategies_path}")
    return strategies


def run_scraping(
    strategies: list[dict],
    output_dir: Path,
    config: GlobalConfig,
    force: bool = False,
    incremental: bool = True,
) -> dict:
    """
    Run job scraping with the provided strategies.
    
    Args:
        strategies: List of strategy dictionaries
        output_dir: Directory for output job files
        config: GlobalConfig object
        force: Re-scrape even if cached
        incremental: Skip already-scraped jobs
        
    Returns:
        Dictionary with scraping results
    """
    # Override output directory in config
    config.jobs_dir = str(output_dir)
    
    # Update cache settings
    cache_dir = SKILL_ROOT / ".cache" / "job-scraper"
    config.cache_dir = str(cache_dir)
    
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Cache directory: {cache_dir}")
    logger.info(f"Headless mode: {config.headless}")
    logger.info(f"Max parallel strategies: {config.max_parallel_strategies}")
    logger.info(f"Max jobs per strategy: {config.max_jobs_per_strategy}")
    
    # Create strategy objects
    strategy_objects = []
    for s in strategies:
        strategy_objects.append(JobSearchStrategy(**s))
    
    # Create scraper and run
    scraper = JobsCHScraper(config=config)
    
    import asyncio
    results = asyncio.run(scraper.run_strategies(strategy_objects, incremental=incremental))
    
    return {
        "total_jobs_found": results.total_jobs_found,
        "total_jobs_extracted": results.total_jobs_extracted,
        "total_failed": results.total_failed,
        "duration_seconds": results.duration_seconds,
        "strategy_stats": results.strategy_stats,
        "incremental_skipped": results.incremental_skipped,
    }


def print_summary(results: dict) -> None:
    """Print summary of scraping results."""
    print("\n" + "=" * 60)
    print("📊 JOB SCRAPER SUMMARY")
    print("=" * 60)
    print(f"Total jobs found: {results['total_jobs_found']}")
    print(f"Total jobs extracted: {results['total_jobs_extracted']}")
    print(f"Failed extractions: {results['total_failed']}")
    print(f"Already cached (skipped): {results.get('incremental_skipped', 0)}")
    print(f"Duration: {results['duration_seconds']:.1f}s")
    print()
    
    # Print per-strategy stats
    strategy_stats = results.get("strategy_stats", [])
    if strategy_stats:
        print("📋 Per-Strategy Statistics:")
        print("-" * 50)
        for stat in strategy_stats:
            strategy_id = stat.get("strategy_id", "?")
            found = stat.get("jobs_found", 0)
            extracted = stat.get("jobs_extracted", 0)
            failed = stat.get("failed", 0)
            skipped = stat.get("skipped", 0)
            duration = stat.get("duration", 0)
            print(f"  [{strategy_id}]")
            print(f"    Found: {found} | Extracted: {extracted} | Failed: {failed} | Skipped: {skipped}")
            print(f"    Duration: {duration:.1f}s")
    
    print("\n" + "=" * 60)
    print("✅ Job scraping complete!")
    print(f"📁 Output saved to: jobs/raw/")
    print(f"📋 Index: jobs/raw/index.json")
    print("=" * 60 + "\n")


def validate_output(output_dir: Path) -> bool:
    """Validate output directory and index file."""
    if not output_dir.exists():
        eprint(f"❌ Output directory not found: {output_dir}")
        return False
    
    index_file = output_dir / "index.json"
    if not index_file.exists():
        eprint(f"⚠️ Index file not found: {index_file}")
        return False
    
    try:
        with open(index_file, "r") as f:
            data = json.load(f)
        
        total_jobs = data.get("total_jobs", 0)
        if total_jobs == 0:
            eprint("⚠️ No jobs extracted")
            return False
        
        print(f"✅ Validated {total_jobs} job postings")
        return True
    
    except json.JSONDecodeError as e:
        eprint(f"❌ Invalid JSON in index: {e}")
        return False
    except Exception as e:
        eprint(f"❌ Validation error: {e}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Job Scraper Skill - Scrape job postings from job boards.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--strategies", "-s",
        type=Path,
        default=Path("inputs/strategies.json"),
        help="Path to strategies JSON file",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("jobs/raw"),
        help="Output directory for scraped jobs",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Path to config file",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        default=False,
        help="Re-scrape even if cached",
    )
    parser.add_argument(
        "--no-incremental",
        action="store_true",
        default=False,
        help="Disable incremental mode (scrape all jobs)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        default=False,
        help="Only validate existing output (skip scraping)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help="Reduce output verbosity",
    )
    parser.add_argument(
        "--headless/--no-headless",
        default=None,
        help="Run browser in headless mode",
    )
    
    args = parser.parse_args()
    
    # Ensure directories exist
    ensure_directories()
    
    # Handle validate-only mode
    if args.validate_only:
        if args.output.exists():
            return 0 if validate_output(args.output) else 1
        else:
            eprint(f"❌ No output directory to validate: {args.output}")
            return 1
    
    # Check strategies file exists
    if not args.strategies.exists():
        eprint(f"❌ Strategies file not found: {args.strategies}")
        eprint("Please ensure inputs/strategies.json exists (generated by career-strategy skill).")
        return 1
    
    # Load configuration
    config = load_config(args.config)
    
    # Override headless setting if provided
    if args.headless is not None:
        config.headless = args.headless
    
    # Load strategies
    try:
        strategies = load_strategies(args.strategies)
    except (FileNotFoundError, ValueError) as e:
        eprint(f"❌ Error loading strategies: {e}")
        return 1
    
    try:
        # Run scraping
        results = run_scraping(
            strategies=strategies,
            output_dir=args.output,
            config=config,
            force=args.force,
            incremental=not args.no_incremental,
        )
        
        # Print summary (unless quiet mode)
        if not args.quiet:
            print_summary(results)
        
        # Validate output
        if not validate_output(args.output):
            return 1
        
        return 0
    
    except KeyboardInterrupt:
        eprint("\n⚠️ Operation cancelled by user")
        return 130
    except Exception as e:
        logger.exception("Failed to scrape jobs")
        eprint(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
