"""CLI interface for job matcher skill."""

import argparse
import sys
import json
from pathlib import Path
from datetime import datetime

from .matcher import JobMatcher


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="Job Matcher - Match job postings to career strategies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with default paths
  job-matcher run
  
  # Specify custom paths
  job-matcher run --strategies strategies.json --jobs output/jobs --output matches/
  
  # Adjust scoring weights
  job-matcher run --keyword-weight 0.4 --salary-weight 0.2
  
  # Set minimum match score
  job-matcher run --min-score 0.5 --max-matches 10
  
  # Just validate inputs without matching
  job-matcher validate --strategies strategies.json --jobs output/jobs
        """
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.1.0"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run job matching")
    run_parser.add_argument(
        "--strategies", "-s",
        default="strategies/",
        help="Path to strategy files (file or directory, default: strategies/)"
    )
    run_parser.add_argument(
        "--jobs", "-j",
        default="job-scraper/output/",
        help="Path to job files (file or directory, default: job-scraper/output/)"
    )
    run_parser.add_argument(
        "--output", "-o",
        default="matches/",
        help="Output directory for match results (default: matches/)"
    )
    run_parser.add_argument(
        "--max-matches", "-m",
        type=int,
        default=20,
        help="Maximum matches per strategy (default: 20)"
    )
    run_parser.add_argument(
        "--min-score", "-t",
        type=float,
        default=0.3,
        help="Minimum match score threshold (0-1, default: 0.3)"
    )
    run_parser.add_argument(
        "--keyword-weight",
        type=float,
        default=0.35,
        help="Weight for keyword matching (default: 0.35)"
    )
    run_parser.add_argument(
        "--location-weight",
        type=float,
        default=0.20,
        help="Weight for location matching (default: 0.20)"
    )
    run_parser.add_argument(
        "--seniority-weight",
        type=float,
        default=0.20,
        help="Weight for seniority matching (default: 0.20)"
    )
    run_parser.add_argument(
        "--remote-weight",
        type=float,
        default=0.10,
        help="Weight for remote work matching (default: 0.10)"
    )
    run_parser.add_argument(
        "--salary-weight",
        type=float,
        default=0.15,
        help="Weight for salary matching (default: 0.15)"
    )
    run_parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress detailed output"
    )
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate input files")
    validate_parser.add_argument(
        "--strategies", "-s",
        default="strategies/",
        help="Path to strategy files"
    )
    validate_parser.add_argument(
        "--jobs", "-j",
        default="job-scraper/output/",
        help="Path to job files"
    )
    
    # Stats command
    stats_parser = subparsers.add_parser("stats", help="Show match statistics")
    stats_parser.add_argument(
        "report",
        nargs="?",
        default="matches/latest.json",
        help="Path to match report (default: matches/latest.json)"
    )
    
    return parser


def validate_inputs(strategies_path: str, jobs_path: str) -> bool:
    """Validate that required input files exist and are valid JSON."""
    valid = True
    
    # Check strategies
    strategies_path = Path(strategies_path)
    if not strategies_path.exists():
        print(f"❌ Strategies path not found: {strategies_path}")
        valid = False
    else:
        try:
            strategies = {}
            if strategies_path.is_file() and strategies_path.suffix == ".json":
                with open(strategies_path) as f:
                    data = json.load(f)
                    for s in data.get("strategies", []):
                        strategies[s.get("strategy_id")] = s
            elif strategies_path.is_dir():
                for json_file in strategies_path.glob("*.json"):
                    with open(json_file) as f:
                        data = json.load(f)
                        for s in data.get("strategies", []):
                            strategies[s.get("strategy_id")] = s
            
            if not strategies:
                print(f"⚠️  No strategies found in {strategies_path}")
            else:
                print(f"✅ Found {len(strategies)} strategy(ies)")
                for sid, s in strategies.items():
                    print(f"   - {sid}: {s.get('job_title', 'Unknown')} ({s.get('location', 'N/A')})")
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in strategies: {e}")
            valid = False
    
    # Check jobs
    jobs_path = Path(jobs_path)
    if not jobs_path.exists():
        print(f"❌ Jobs path not found: {jobs_path}")
        valid = False
    else:
        try:
            jobs = []
            if jobs_path.is_file() and jobs_path.suffix == ".json":
                with open(jobs_path) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        jobs = data
                    else:
                        jobs = [data]
            elif jobs_path.is_dir():
                for json_file in jobs_path.glob("*.json"):
                    with open(json_file) as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            jobs.extend(data)
                        else:
                            jobs.append(data)
            
            if not jobs:
                print(f"⚠️  No jobs found in {jobs_path}")
            else:
                print(f"✅ Found {len(jobs)} job posting(s)")
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in jobs: {e}")
            valid = False
    
    return valid


def print_report_summary(report: dict, quiet: bool = False) -> None:
    """Print a summary of the match report."""
    print("\n" + "=" * 60)
    print("JOB MATCHING REPORT")
    print("=" * 60)
    
    print(f"\n📊 Summary:")
    print(f"   Strategies analyzed: {report.get('strategies_analyzed', 0)}")
    print(f"   Jobs analyzed: {report.get('jobs_analyzed', 0)}")
    print(f"   Total matches: {report.get('total_matches', 0)}")
    
    dist = report.get('score_distribution', {})
    print(f"\n📈 Score Distribution:")
    print(f"   Excellent (≥0.8): {dist.get('excellent', 0)}")
    print(f"   Good (0.6-0.79): {dist.get('good', 0)}")
    print(f"   Moderate (0.4-0.59): {dist.get('moderate', 0)}")
    print(f"   Poor (<0.4): {dist.get('poor', 0)}")
    
    print(f"\n📋 Results by Strategy:")
    for result in report.get('results', []):
        print(f"\n   [{result.get('strategy_category', 'unknown')}] {result.get('strategy_title', 'Unknown')}")
        print(f"   Strategy ID: {result.get('strategy_id', 'N/A')}")
        print(f"   Jobs matched: {result.get('total_matches', 0)} / {result.get('total_jobs_analyzed', 0)}")
        
        if not quiet:
            print(f"\n   Top Matches:")
            for i, match in enumerate(result.get('matches', [])[:5], 1):
                print(f"   {i}. {match.get('job_title', 'Unknown')} @ {match.get('company', 'Unknown')}")
                print(f"      Score: {match.get('score', 0):.2f} | {match.get('job_location', 'Unknown')}")
                print(f"      Keywords: {', '.join(match.get('matched_keywords', [])) or 'None'}")
                print(f"      Link: {match.get('job_link', 'N/A')}")
    
    print("\n" + "=" * 60)


def run(args: argparse.Namespace) -> int:
    """Run the job matching process."""
    # Create matcher with custom weights
    matcher = JobMatcher(
        keyword_weight=args.keyword_weight,
        location_weight=args.location_weight,
        seniority_weight=args.seniority_weight,
        remote_weight=args.remote_weight,
        salary_weight=args.salary_weight,
        min_score=args.min_score,
    )
    
    # Validate inputs first
    if not validate_inputs(args.strategies, args.jobs):
        return 1
    
    # Ensure output directory exists
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Generate output filename with timestamp
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_file = output_path / f"matches_{timestamp}.json"
    
    # Also create a "latest" symlink/copy
    latest_file = output_path / "latest.json"
    
    print(f"\n🔍 Matching jobs from {args.jobs} to strategies from {args.strategies}...")
    
    # Run matching
    try:
        report = matcher.match_all(
            strategies_path=args.strategies,
            jobs_path=args.jobs,
            output_path=str(output_file),
            max_matches_per_strategy=args.max_matches,
        )
        
        # Save latest copy
        matcher.save_report(report, str(latest_file))
        
        # Print summary
        report_dict = report.model_dump()
        print_report_summary(report_dict, args.quiet)
        
        print(f"\n✅ Matching complete!")
        print(f"   Report saved to: {output_file}")
        print(f"   Latest copy: {latest_file}")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Error during matching: {e}")
        import traceback
        traceback.print_exc()
        return 1


def validate(args: argparse.Namespace) -> int:
    """Validate input files."""
    if validate_inputs(args.strategies, args.jobs):
        print("\n✅ All inputs valid!")
        return 0
    else:
        print("\n❌ Input validation failed!")
        return 1


def stats(args: argparse.Namespace) -> int:
    """Show statistics from a match report."""
    report_path = Path(args.report)
    
    if not report_path.exists():
        print(f"❌ Report not found: {report_path}")
        return 1
    
    try:
        with open(report_path) as f:
            report = json.load(f)
        print_report_summary(report, quiet=False)
        return 0
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in report: {e}")
        return 1


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 1
    
    if args.command == "run":
        return run(args)
    elif args.command == "validate":
        return validate(args)
    elif args.command == "stats":
        return stats(args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
