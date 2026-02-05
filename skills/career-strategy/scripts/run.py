#!/usr/bin/env python3
"""
Career Strategy Skill - Analyze resumes and generate job search strategies.

Part of the OpenClaw job-application-agency workflow.
Uses parallel execution patterns (preserving 100 jobs/5min mindset).

Usage:
    python scripts/run.py [--force] [--config CONFIG_PATH]

Input:
    inputs/resume.md - Resume in markdown format

Output:
    strategies/strategies.json - Generated search strategies
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
sys.path.insert(0, str(SKILL_ROOT / "career_strategy"))

from career_strategy.analyzer import ResumeAnalyzer
from career_strategy.models import StrategyList, SearchStrategy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def eprint(msg: str) -> None:
    """Print to stderr."""
    print(msg, file=sys.stderr)


def load_config(config_path: Optional[Path] = None) -> dict:
    """Load configuration from global and skill-specific config files."""
    config = {}
    
    # Load global config
    global_config_path = config_path or Path("config/global.json")
    if global_config_path.exists():
        try:
            config.update(json.loads(global_config_path.read_text()))
            logger.info(f"Loaded global config from: {global_config_path}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse global config: {e}")
    
    # Load skill-specific config
    skill_config_path = config_path or Path("config/career-strategy-config.json")
    if skill_config_path.exists():
        try:
            config.update(json.loads(skill_config_path.read_text()))
            logger.info(f"Loaded skill config from: {skill_config_path}")
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse skill config: {e}")
    
    return config


def ensure_directories():
    """Ensure required directories exist."""
    (Path("inputs")).mkdir(exist_ok=True)
    (Path("strategies")).mkdir(exist_ok=True)
    (Path(".cache/career-strategy")).mkdir(parents=True, exist_ok=True)


def run_analysis(
    resume_path: Path,
    output_path: Path,
    config: dict,
    force: bool = False,
) -> StrategyList:
    """
    Run resume analysis and generate strategies.
    
    Args:
        resume_path: Path to resume markdown file
        output_path: Path to save strategies JSON
        config: Configuration dictionary
        force: Re-generate even if cached
        
    Returns:
        StrategyList with generated strategies
    """
    # Get settings with overrides
    llm_model = config.get("llm_model", "anthropic/claude-sonnet-4-5")
    api_key = config.get("api_key") or None
    cache_dir = config.get("cache_dir", ".cache/career-strategy")
    
    logger.info(f"Using LLM model: {llm_model}")
    logger.info(f"Resume: {resume_path}")
    logger.info(f"Output: {output_path}")
    
    # Create analyzer
    analyzer = ResumeAnalyzer(
        llm_model=llm_model,
        api_key=api_key,
        cache_dir=cache_dir,
    )
    
    # Analyze and generate strategies
    strategies = analyzer.analyze(
        resume_path=resume_path,
        output_path=output_path,
        force=force,
    )
    
    return strategies


def print_summary(strategies: StrategyList) -> None:
    """Print summary of generated strategies."""
    print("\n" + "=" * 60)
    print("📊 CAREER STRATEGY SUMMARY")
    print("=" * 60)
    print(f"Total strategies: {len(strategies.strategies)}")
    print(f"Generated at: {strategies.generated_at}")
    print(f"Resume hash: {strategies.resume_hash}")
    print()
    
    # Group by category
    by_category: dict[str, list[SearchStrategy]] = {}
    for s in strategies.strategies:
        cat = s.category or "unknown"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(s)
    
    for category, items in sorted(by_category.items()):
        print(f"\n🎯 [{category.upper()}] ({len(items)} strategies)")
        print("-" * 40)
        for i, s in enumerate(items, 1):
            print(f"  {i}. {s.job_title}")
            print(f"     📍 {s.location}")
            print(f"     🔑 Keywords: {', '.join(s.keywords[:5])}")
            print(f"     💰 Min salary: {s.salary_min or 'N/A'}")
    
    print("\n" + "=" * 60)
    print("✅ Strategy generation complete!")
    print(f"📁 Output saved to: strategies/strategies.json")
    print("=" * 60 + "\n")


def validate_output(output_path: Path) -> bool:
    """Validate output file exists and is valid JSON."""
    if not output_path.exists():
        eprint(f"❌ Output file not found: {output_path}")
        return False
    
    try:
        data = json.loads(output_path.read_text())
        strategies = StrategyList(**data)
        
        # Check required fields
        if not strategies.strategies:
            eprint("❌ No strategies generated")
            return False
        
        for i, s in enumerate(strategies.strategies):
            if not s.strategy_id:
                eprint(f"⚠️ Strategy {i}: Missing strategy_id")
            if not s.job_title:
                eprint(f"⚠️ Strategy {i}: Missing job_title")
        
        print(f"✅ Validated {len(strategies.strategies)} strategies")
        return True
    
    except json.JSONDecodeError as e:
        eprint(f"❌ Invalid JSON in output: {e}")
        return False
    except Exception as e:
        eprint(f"❌ Validation error: {e}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Career Strategy Skill - Analyze resumes and generate job search strategies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--resume", "-r",
        type=Path,
        default=Path("inputs/resume.md"),
        help="Path to resume markdown file",
    )
    parser.add_argument(
        "--output", "-o",
        type=Path,
        default=Path("strategies/strategies.json"),
        help="Path for output strategies JSON",
    )
    parser.add_argument(
        "--config", "-c",
        type=Path,
        help="Path to config directory or file",
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        default=False,
        help="Re-generate strategies even if cached",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        default=False,
        help="Only validate existing output (skip generation)",
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        default=False,
        help="Reduce output verbosity",
    )
    
    args = parser.parse_args()
    
    # Ensure directories exist
    ensure_directories()
    
    # Handle validate-only mode
    if args.validate_only:
        if args.output.exists():
            return 0 if validate_output(args.output) else 1
        else:
            eprint(f"❌ No output file to validate: {args.output}")
            return 1
    
    # Check resume exists
    if not args.resume.exists():
        eprint(f"❌ Resume not found: {args.resume}")
        eprint("Please ensure inputs/resume.md exists with proper markdown format.")
        return 1
    
    # Load configuration
    config = load_config(args.config)
    
    try:
        # Run analysis
        strategies = run_analysis(
            resume_path=args.resume,
            output_path=args.output,
            config=config,
            force=args.force,
        )
        
        # Print summary (unless quiet mode)
        if not args.quiet:
            print_summary(strategies)
        
        # Validate output
        if not validate_output(args.output):
            return 1
        
        return 0
    
    except KeyboardInterrupt:
        eprint("\n⚠️ Operation cancelled by user")
        return 130
    except Exception as e:
        logger.exception("Failed to generate strategies")
        eprint(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
