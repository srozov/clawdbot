#!/usr/bin/env python3
"""
Cover Letter Generation Skill - Main Entry Point

Generate tailored cover letters and customized CVs for job applications.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from cover_letter_gen.models import (
    CoverLetterConfig,
    MatchInfo,
    JobPosting,
    ApplicationMetadata,
    ApplicationIndex,
)
from cover_letter_gen.generator import CoverLetterGenerator
from cover_letter_gen.cv_customizer import CVCustomizer
from cover_letter_gen.research import CompanyResearcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def setup_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate tailored cover letters and customized CVs for job applications."
    )
    parser.add_argument(
        "--matches", "-m", type=str, required=True, help="Path to viable matches JSON"
    )
    parser.add_argument(
        "--resume", "-r", type=str, required=True, help="Path to resume markdown"
    )
    parser.add_argument(
        "--output", "-o", type=str, default="applications", help="Output directory"
    )
    parser.add_argument(
        "--enable-research", action="store_true", help="Enable company research"
    )
    parser.add_argument(
        "--force", "-f", action="store_true", help="Force regeneration, skip cache"
    )
    parser.add_argument(
        "--config", "-c", type=str, help="Path to config file"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--json", action="store_true", help="Use JSON logging format"
    )
    parser.add_argument(
        "--llm-model", type=str, default="anthropic/claude-sonnet-4",
        help="LLM model to use"
    )
    parser.add_argument(
        "--max-length", type=int, default=350, help="Max cover letter length in words"
    )
    parser.add_argument(
        "--min-score", type=float, default=0.6,
        help="Minimum match score to generate cover letter"
    )
    return parser.parse_args()


def load_config(args) -> CoverLetterConfig:
    """Load configuration from args and files."""
    config = CoverLetterConfig(
        llm_model=args.llm_model,
        max_length_words=args.max_length,
        min_match_score=args.min_score,
        enable_company_research=args.enable_research,
        output_dir=args.output,
    )

    # Load from config file if provided
    if args.config:
        config_path = Path(args.config)
        if config_path.exists():
            try:
                with open(config_path) as f:
                    config_data = json.load(f)
                config = CoverLetterConfig(**config_data)
                logger.info(f"Loaded config from {args.config}")
            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning(f"Invalid config file, using defaults: {e}")

    # Also check for global config
    global_config = Path("config/global.json")
    if global_config.exists():
        try:
            with open(global_config) as f:
                global_data = json.load(f)
            if "llm_model" in global_data:
                config.llm_model = global_data["llm_model"]
            if "cache_ttl_days" in global_data:
                config.company_cache_ttl_days = global_data["cache_ttl_days"]
            logger.info("Loaded settings from global config")
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning(f"Invalid global config, using defaults: {e}")

    return config


def create_llm_client(model_name: str):
    """Create LLM client."""
    try:
        import os
        from langchain_openai import ChatOpenAI

        base_url = None
        api_key = None

        if os.getenv("OPENROUTER_API_KEY"):
            base_url = "https://openrouter.ai/api/v1"
            api_key = os.getenv("OPENROUTER_API_KEY")
        elif os.getenv("OPENAI_API_KEY"):
            api_key = os.getenv("OPENAI_API_KEY")

        if api_key:
            return ChatOpenAI(
                model=model_name,
                openai_api_key=api_key,
                openai_api_base=base_url,
                temperature=0.7,
                max_tokens=2000,
            )
    except ImportError:
        pass

    logger.warning("No LLM client available, using fallback generation")
    return None


def get_resume_hash(resume_content: str) -> str:
    """Get MD5 hash of resume content."""
    return hashlib.md5(resume_content.encode()).hexdigest()[:16]


def emit_progress(json_format: bool, **kwargs):
    """Emit progress event."""
    if json_format:
        print(json.dumps(kwargs))


async def generate_cover_letters(args, config: CoverLetterConfig):
    """Main generation logic."""
    # Load resume
    resume_path = Path(args.resume)
    resume_content = resume_path.read_text(encoding="utf-8")
    resume_hash = get_resume_hash(resume_content)

    if args.verbose:
        logger.info(f"Loaded resume: {resume_path.name} (hash: {resume_hash})")

    emit_progress(
        args.json,
        type="status",
        status="starting",
        matches_file=args.matches,
        resume_file=args.resume,
        output_dir=args.output,
        enable_research=args.enable_research,
    )

    # Load matches
    matches_path = Path(args.matches)
    with open(matches_path, "r", encoding="utf-8") as f:
        matches_data = json.load(f)

    # Parse viable matches
    viable_matches = []
    for match_data in matches_data.get("matches", []):
        try:
            match_info = MatchInfo(**match_data)
            if match_info.match_score >= config.min_match_score:
                viable_matches.append(match_info)
        except ValidationError as e:
            logger.warning(f"Invalid match data: {e}")
            continue

    if not viable_matches:
        logger.info(f"No viable matches found (score >= {config.min_match_score:.0%})")
        emit_progress(args.json, type="complete", total=0, generated=0, cached=0, failed=0)
        return

    if args.verbose:
        logger.info(f"Found {len(viable_matches)} viable matches")

    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Initialize components
    llm_client = create_llm_client(config.llm_model)
    generator = CoverLetterGenerator(
        llm_client=llm_client,
        style=config.style,
        max_length_words=config.max_length_words,
    )
    cv_customizer = CVCustomizer(llm_client=llm_client)
    researcher = CompanyResearcher(
        cache_dir=".cache/cover-letter-gen/company-research",
        ttl_days=config.company_cache_ttl_days,
    )

    # Load job postings for context
    jobs_dir = Path("jobs/raw")
    job_cache = {}
    if jobs_dir.exists():
        for job_file in jobs_dir.glob("*.json"):
            try:
                with open(job_file, "r", encoding="utf-8") as f:
                    job_data = json.load(f)
                job_cache[job_data.get("job_id")] = JobPosting(**job_data)
            except (ValidationError, json.JSONDecodeError) as e:
                logger.warning(f"Invalid job file {job_file.name}: {e}")

    # Initialize cache
    cache_dir = Path(".cache/cover-letter-gen")
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Create application index
    app_index = ApplicationIndex()

    async def generate_for_match(match: MatchInfo) -> dict:
        """Generate cover letter and CV for a single match."""
        cache_key = hashlib.md5(f"{match.job_id}:{resume_hash}".encode()).hexdigest()
        cache_path = cache_dir / f"{cache_key}.json"

        # Check cache
        if not args.force and cache_path.exists():
            try:
                with open(cache_path, "r") as f:
                    cached_data = json.load(f)
                logger.info(f"📋 Using cached cover letter for {match.company} - {match.title}")
                app_index.add_application(
                    match.company,
                    match.title,
                    str(output_dir / f"{match.company}_{match.title}".replace(" ", "_")),
                    match.match_score,
                    cached=True,
                )
                return {"status": "cached", "company": match.company, "title": match.title}
            except Exception:
                pass

        # Get job posting for context
        job = job_cache.get(match.job_id)
        if not job:
            job = JobPosting(
                job_id=match.job_id,
                title=match.title,
                company=match.company,
                location=match.location,
                description="",
            )

        # Research company if enabled
        company_research = None
        if config.enable_company_research:
            company_research = await researcher.research_company(
                match.company,
                enable_search=args.enable_research,
            )

        # Generate cover letter
        cover_letter = await generator.generate(
            job=job,
            match=match,
            resume_content=resume_content,
            company_research=company_research,
        )

        # Generate customized CV
        cv_result = await cv_customizer.customize_cv(
            resume_content=resume_content,
            job=job,
            match=match,
        )

        # Create output directory
        safe_company = match.company.replace(" ", "_").replace("/", "_")
        safe_title = match.title.replace(" ", "_").replace("/", "_")
        app_dir = output_dir / f"{safe_title}_{safe_company}"
        app_dir.mkdir(parents=True, exist_ok=True)

        # Save cover letter
        (app_dir / "cover_letter.md").write_text(cover_letter.content, encoding="utf-8")

        # Save CV
        (app_dir / "cv.md").write_text(cv_result.content, encoding="utf-8")

        # Save metadata
        metadata = ApplicationMetadata.create(
            job_id=match.job_id,
            company=match.company,
            title=match.title,
            match_score=match.match_score,
            resume_content=resume_content,
            company_research=company_research,
            cached=False,
        )
        (app_dir / "metadata.json").write_text(
            metadata.model_dump_json(indent=2), encoding="utf-8"
        )

        # Save to cache
        cache_data = {
            "cover_letter": cover_letter.content,
            "cv": cv_result.content,
            "metadata": metadata.model_dump(),
            "cached_at": datetime.now().isoformat(),
        }
        with open(cache_path, "w") as f:
            json.dump(cache_data, f, indent=2)

        # Update index
        app_index.add_application(
            match.company,
            match.title,
            str(app_dir),
            match.match_score,
            cached=False,
        )

        emit_progress(
            args.json,
            type="progress",
            current=app_index.generated + app_index.cached,
            total=len(viable_matches),
            company=match.company,
            title=match.title,
            status="complete",
        )

        return {"status": "generated", "company": match.company, "title": match.title}

    # Run generation for all matches
    tasks = [generate_for_match(match) for match in viable_matches]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Count results
    generated = sum(1 for r in results if r and r.get("status") == "generated")
    cached = sum(1 for r in results if r and r.get("status") == "cached")
    failed = sum(1 for r in results if isinstance(r, Exception))

    # Save index
    index_path = output_dir / "index.json"
    index_data = app_index.model_dump()
    index_data["generated_at"] = datetime.now().isoformat()
    index_path.write_text(json.dumps(index_data, indent=2), encoding="utf-8")

    # Log completion
    logger.info(f"✅ Generated {generated} cover letters, {cached} from cache, {failed} failed")

    emit_progress(
        args.json,
        type="complete",
        total=len(viable_matches),
        generated=generated,
        cached=cached,
        failed=failed,
    )


def main():
    """Main entry point."""
    args = setup_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.json:
        logging.getLogger().handlers = []

    config = load_config(args)

    try:
        asyncio.run(generate_cover_letters(args, config))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        if args.json:
            print(json.dumps({"type": "error", "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
