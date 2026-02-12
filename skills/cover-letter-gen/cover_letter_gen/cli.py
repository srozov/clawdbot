"""
Click CLI for cover letter generation skill.
"""

import asyncio
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click
from pydantic import ValidationError

from .models import (
    CoverLetterConfig,
    MatchInfo,
    JobPosting,
    ApplicationMetadata,
    ApplicationIndex,
    ViableMatches,
)
from .generator import CoverLetterGenerator
from .cv_customizer import CVCustomizer
from .research import CompanyResearcher

logger = logging.getLogger(__name__)


def setup_logging(level: str = "INFO", json_format: bool = False):
    """Configure logging."""
    log_level = getattr(logging, level.upper(), logging.INFO)

    if json_format:
        # Use JSON logging for structured output
        import json_log_formatter

        handler = logging.StreamHandler(sys.stdout)
        formatter = json_log_formatter.JSONFormatter()
        handler.setFormatter(formatter)
        logging.root.handlers = [handler]

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s" if not json_format else None,
    )


def load_config(config_path: Optional[Path] = None) -> CoverLetterConfig:
    """Load configuration from file or use defaults."""
    if config_path and config_path.exists():
        try:
            with open(config_path) as f:
                config_data = json.load(f)
            return CoverLetterConfig(**config_data)
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning(f"Invalid config file, using defaults: {e}")

    # Also check for global config
    global_config = Path("config/global.json")
    if global_config.exists():
        try:
            with open(global_config) as f:
                global_data = json.load(f)
            # Extract cover-letter-gen specific settings
            return CoverLetterConfig(
                llm_model=global_data.get("llm_model", "anthropic/claude-sonnet-4"),
                style=global_data.get("style", "adaptive"),
                enable_company_research=global_data.get("enable_company_research", True),
                company_cache_ttl_days=global_data.get("cache_ttl_days", 7),
                max_length_words=global_data.get("max_length_words", 350),
            )
        except (ValidationError, json.JSONDecodeError) as e:
            logger.warning(f"Invalid global config, using defaults: {e}")

    return CoverLetterConfig()


def create_llm_client(model_name: str):
    """Create LLM client based on model name."""
    try:
        # Check for API keys
        import os

        if os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY"):
            from langchain_openai import ChatOpenAI

            base_url = None
            api_key = None

            if os.getenv("OPENROUTER_API_KEY"):
                base_url = "https://openrouter.ai/api/v1"
                api_key = os.getenv("OPENROUTER_API_KEY")
            else:
                api_key = os.getenv("OPENAI_API_KEY")

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


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--json", "json_log", is_flag=True, help="Use JSON logging format")
@click.pass_context
def cli(ctx, verbose: bool, json_log: bool):
    """Cover Letter Generator - Generate tailored cover letters for job applications."""
    ctx.ensure_object(dict)

    level = "DEBUG" if verbose else "INFO"
    setup_logging(level, json_log)

    ctx.obj["verbose"] = verbose
    ctx.obj["json_log"] = json_log


@cli.command()
@click.argument("matches_file", type=click.Path(exists=True))
@click.argument("resume_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), default="applications", help="Output directory")
@click.option("--enable-research", is_flag=True, help="Enable company research via web search")
@click.option("--force", "-f", is_flag=True, help="Force regeneration, skip cache")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to config file")
@click.pass_context
def run(
    ctx,
    matches_file: str,
    resume_file: str,
    output: str,
    enable_research: bool,
    force: bool,
    config: str,
):
    """Generate cover letters for all viable job matches."""
    verbose = ctx.obj.get("verbose", False)
    json_log = ctx.obj.get("json_log", False)

    # Load configuration
    config_path = Path(config) if config else None
    config_data = load_config(config_path)
    config_data.output_dir = output
    config_data.enable_company_research = enable_research

    # Log progress in JSON format
    if json_log:
        click.echo(json.dumps({
            "type": "status",
            "status": "starting",
            "matches_file": matches_file,
            "resume_file": resume_file,
            "output_dir": output,
            "enable_research": enable_research,
        }))

    try:
        # Load resume
        resume_path = Path(resume_file)
        resume_content = resume_path.read_text(encoding="utf-8")
        resume_hash = get_resume_hash(resume_content)

        if verbose:
            logger.info(f"Loaded resume: {resume_path.name} (hash: {resume_hash})")

        # Load matches
        matches_path = Path(matches_file)
        with open(matches_path, "r", encoding="utf-8") as f:
            matches_data = json.load(f)

        # Parse viable matches
        viable_matches = []
        for match_data in matches_data.get("matches", []):
            try:
                match_info = MatchInfo(**match_data)
                if match_info.match_score >= config_data.min_match_score:
                    viable_matches.append(match_info)
            except ValidationError as e:
                logger.warning(f"Invalid match data: {e}")
                continue

        if not viable_matches:
            logger.info("No viable matches found (score >= {:.0%})".format(config_data.min_match_score))
            if json_log:
                click.echo(json.dumps({"type": "complete", "total": 0, "generated": 0, "cached": 0, "failed": 0}))
            return

        if verbose:
            logger.info(f"Found {len(viable_matches)} viable matches")

        # Create output directory
        output_dir = Path(output)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        llm_client = create_llm_client(config_data.llm_model)
        generator = CoverLetterGenerator(
            llm_client=llm_client,
            style=config_data.style,
            max_length_words=config_data.max_length_words,
        )
        cv_customizer = CVCustomizer(llm_client=llm_client)
        researcher = CompanyResearcher(
            cache_dir=".cache/cover-letter-gen/company-research",
            ttl_days=config_data.company_cache_ttl_days,
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

        # Generate cover letters
        async def generate_for_match(match: MatchInfo) -> dict:
            """Generate cover letter and CV for a single match."""
            cache_key = hashlib.md5(f"{match.job_id}:{resume_hash}".encode()).hexdigest()
            cache_path = cache_dir / f"{cache_key}.json"

            # Check cache
            if not force and cache_path.exists():
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
                # Create minimal job posting from match info
                job = JobPosting(
                    job_id=match.job_id,
                    title=match.title,
                    company=match.company,
                    location=match.location,
                    description="",
                )

            # Research company if enabled
            company_research = None
            if config_data.enable_company_research:
                company_research = await researcher.research_company(
                    match.company,
                    enable_search=enable_research,
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

            # Create output directory for this application
            safe_company = match.company.replace(" ", "_").replace("/", "_")
            safe_title = match.title.replace(" ", "_").replace("/", "_")
            app_dir = output_dir / f"{safe_title}_{safe_company}"
            app_dir.mkdir(parents=True, exist_ok=True)

            # Save cover letter
            cover_letter_path = app_dir / "cover_letter.md"
            cover_letter_path.write_text(cover_letter.content, encoding="utf-8")

            # Save CV
            cv_path = app_dir / "cv.md"
            cv_path.write_text(cv_result.content, encoding="utf-8")

            # Create and save metadata
            metadata = ApplicationMetadata.create(
                job_id=match.job_id,
                company=match.company,
                title=match.title,
                match_score=match.match_score,
                resume_content=resume_content,
                company_research=company_research,
                cached=False,
            )
            metadata_path = app_dir / "metadata.json"
            metadata_path.write_text(metadata.model_dump_json(indent=2), encoding="utf-8")

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

            if json_log:
                click.echo(json.dumps({
                    "type": "progress",
                    "current": app_index.generated + app_index.cached,
                    "total": len(viable_matches),
                    "company": match.company,
                    "title": match.title,
                    "status": "complete",
                }))

            return {"status": "generated", "company": match.company, "title": match.title}

        # Run generation for all matches
        async def run_all():
            tasks = [generate_for_match(match) for match in viable_matches]
            return await asyncio.gather(*tasks, return_exceptions=True)

        results = asyncio.run(run_all())

        # Count results
        generated = sum(1 for r in results if r.get("status") == "generated")
        cached = sum(1 for r in results if r.get("status") == "cached")
        failed = sum(1 for r in results if isinstance(r, Exception))

        # Save index
        index_path = output_dir / "index.json"
        index_data = app_index.model_dump()
        index_data["generated_at"] = datetime.now().isoformat()
        index_path.write_text(json.dumps(index_data, indent=2), encoding="utf-8")

        # Log completion
        logger.info(f"✅ Generated {generated} cover letters, {cached} from cache, {failed} failed")

        if json_log:
            click.echo(json.dumps({
                "type": "complete",
                "total": len(viable_matches),
                "generated": generated,
                "cached": cached,
                "failed": failed,
            }))

    except Exception as e:
        logger.error(f"Error generating cover letters: {e}")
        if json_log:
            click.echo(json.dumps({"type": "error", "error": str(e)}))
        raise click.ClickException(str(e))


@cli.command()
@click.argument("job_file", type=click.Path(exists=True))
@click.argument("match_file", type=click.Path(exists=True))
@click.argument("resume_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output directory for single application")
@click.option("--enable-research", is_flag=True, help="Enable company research")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to config file")
@click.pass_context
def generate(
    ctx,
    job_file: str,
    match_file: str,
    resume_file: str,
    output: str,
    enable_research: bool,
    config: str,
):
    """Generate a single cover letter."""
    verbose = ctx.obj.get("verbose", False)
    json_log = ctx.obj.get("json_log", False)

    # Load configuration
    config_path = Path(config) if config else None
    config_data = load_config(config_path)
    config_data.enable_company_research = enable_research

    try:
        # Load job posting
        with open(job_file, "r", encoding="utf-8") as f:
            job_data = json.load(f)
        job = JobPosting(**job_data)

        # Load match info
        with open(match_file, "r", encoding="utf-8") as f:
            match_data = json.load(f)
        match = MatchInfo(**match_data)

        # Load resume
        resume_content = Path(resume_file).read_text(encoding="utf-8")

        # Initialize components
        llm_client = create_llm_client(config_data.llm_model)
        generator = CoverLetterGenerator(
            llm_client=llm_client,
            style=config_data.style,
            max_length_words=config_data.max_length_words,
        )
        cv_customizer = CVCustomizer(llm_client=llm_client)
        researcher = CompanyResearcher(
            cache_dir=".cache/cover-letter-gen/company-research",
            ttl_days=config_data.company_cache_ttl_days,
        )

        async def generate_one():
            # Research company
            company_research = None
            if config_data.enable_company_research:
                company_research = await researcher.research_company(
                    match.company,
                    enable_search=enable_research,
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

            return cover_letter, cv_result, company_research

        cover_letter, cv_result, company_research = asyncio.run(generate_one())

        # Save output
        if output:
            output_dir = Path(output)
        else:
            output_dir = Path(f"applications/{match.company}_{match.title}".replace(" ", "_"))

        output_dir.mkdir(parents=True, exist_ok=True)

        # Save cover letter
        (output_dir / "cover_letter.md").write_text(cover_letter.content, encoding="utf-8")

        # Save CV
        (output_dir / "cv.md").write_text(cv_result.content, encoding="utf-8")

        # Save metadata
        metadata = ApplicationMetadata.create(
            job_id=match.job_id,
            company=match.company,
            title=match.title,
            match_score=match.match_score,
            resume_content=resume_content,
            company_research=company_research,
        )
        (output_dir / "metadata.json").write_text(
            metadata.model_dump_json(indent=2), encoding="utf-8"
        )

        logger.info(f"✅ Generated cover letter for {match.company} - {match.title}")
        logger.info(f"📁 Output: {output_dir}")

    except ValidationError as e:
        logger.error(f"Invalid input data: {e}")
        raise click.ClickException(f"Invalid input data: {e}")
    except Exception as e:
        logger.error(f"Error generating cover letter: {e}")
        raise click.ClickException(str(e))


if __name__ == "__main__":
    cli()
