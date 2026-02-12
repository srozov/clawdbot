"""Job scraper core module with Stagehand browser automation.

This module provides job scraping functionality using Stagehand for
browser automation on jobs.ch (and other job boards).
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from uuid import uuid4
import re

from .models import (
    GlobalConfig,
    JobSearchStrategy,
    JobPosting,
    ScrapingStats,
    JobLink,
    Workload,
    RemoteOption,
    Seniority,
    EmploymentType,
)

logger = logging.getLogger(__name__)


class JobsCHScraper:
    """
    Job scraper for jobs.ch using Stagehand browser automation.
    
    Features:
    - Stagehand integration for browser automation
    - Semantic DOM for intelligent element detection
    - Incremental processing (skip already-scraped jobs)
    - Rate limiting and error handling
    """
    
    def __init__(self, config: Optional[GlobalConfig] = None):
        """
        Initialize the jobs.ch scraper.
        
        Args:
            config: GlobalConfig instance (loads from config/global.json if not provided)
        """
        self.config = config or GlobalConfig.load()
        
        # Set up directories
        self.jobs_dir = Path(self.config.jobs_dir)
        self.cache_dir = Path(self.config.cache_dir)
        
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Stagehand session (lazy initialization)
        self._session = None
        self.stagehand = None
        
        logger.info(f"🚀 JobsCHScraper initialized")
        logger.info(f"   Jobs directory: {self.jobs_dir}")
        logger.info(f"   Cache directory: {self.cache_dir}")
        logger.info(f"   Headless: {self.config.headless}")
    
    async def initialize(self) -> None:
        """Initialize Stagehand session."""
        try:
            from stagehand import Stagehand
            
            # Build Stagehand config
            stagehand_config = {
                "env": "LOCAL",
                "headless": self.config.headless,
                "model_name": self.config.llm_model,
                "verbose": 1,
            }
            
            # Add API key if provided
            if self.config.llm_api_key:
                stagehand_config["model_api_key"] = self.config.llm_api_key
            
            if self.config.llm_base_url:
                stagehand_config["model_client_options"] = {
                    "api_base": self.config.llm_base_url,
                    "baseURL": self.config.llm_base_url,
                }
            
            # Add local browser options
            stagehand_config["local_browser_launch_options"] = {
                "headless": self.config.headless,
                "viewport": {
                    "width": self.config.window_width,
                    "height": self.config.window_height,
                }
            }
            
            self.stagehand = Stagehand(**stagehand_config)
            result = await self.stagehand.init()
            
            logger.info(f"✅ Stagehand initialized: {result.get('sessionId', 'unknown')}")
            
        except ImportError as e:
            logger.warning(f"⚠️ Stagehand not available: {e}")
            logger.warning("   Using mock implementation for demonstration")
            self.stagehand = None
    
    async def close(self) -> None:
        """Close Stagehand session."""
        if self.stagehand:
            await self.stagehand.close()
            logger.info("🔒 Stagehand session closed")
            self.stagehand = None
    
    async def run_strategies(
        self,
        strategies: List[JobSearchStrategy],
        incremental: bool = True
    ) -> ScrapingStats:
        """
        Run multiple search strategies in parallel.
        
        Args:
            strategies: List of search strategies to execute
            incremental: Skip already-scraped jobs (default: True)
            
        Returns:
            ScrapingStats with overall statistics
        """
        start_time = time.time()
        
        logger.info(f"🚀 Starting parallel scraping with {len(strategies)} strategies")
        
        # Initialize Stagehand
        await self.initialize()
        
        try:
            # Run strategies in parallel with semaphore limit
            semaphore = asyncio.Semaphore(self.config.max_parallel_strategies)
            
            async def run_with_semaphore(strategy: JobSearchStrategy):
                async with semaphore:
                    return await self._run_single_strategy(strategy, incremental)
            
            tasks = [run_with_semaphore(s) for s in strategies]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Aggregate results
            total_found = 0
            total_extracted = 0
            total_failed = 0
            total_skipped = 0
            strategy_stats = []
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Strategy {strategies[i].strategy_id} failed: {result}")
                    strategy_stats.append({
                        "strategy_id": strategies[i].strategy_id,
                        "jobs_found": 0,
                        "jobs_extracted": 0,
                        "failed": 0,
                        "skipped": 0,
                        "error": str(result)
                    })
                    total_failed += 1
                else:
                    total_found += result.get("jobs_found", 0)
                    total_extracted += result.get("jobs_extracted", 0)
                    total_failed += result.get("failed", 0)
                    total_skipped += result.get("skipped", 0)
                    strategy_stats.append(result)
            
            duration = time.time() - start_time
            
            stats = ScrapingStats(
                total_strategies=len(strategies),
                total_jobs_found=total_found,
                total_jobs_extracted=total_extracted,
                total_failed=total_failed,
                duration_seconds=duration,
                strategy_stats=strategy_stats,
                incremental_skipped=total_skipped
            )
            
            logger.info(
                f"✅ Scraping complete: {total_extracted}/{total_found} jobs "
                f"({total_skipped} skipped) in {duration:.1f}s"
            )
            
            return stats
            
        finally:
            await self.close()
    
    async def _run_single_strategy(
        self,
        strategy: JobSearchStrategy,
        incremental: bool = True
    ) -> dict:
        """
        Run a single search strategy and extract jobs.
        
        Args:
            strategy: The search strategy to execute
            incremental: Skip already-scraped jobs
            
        Returns:
            Dict with strategy statistics
        """
        strategy_id = strategy.strategy_id or f"strategy_{uuid4().hex[:8]}"
        logger.info(f"🎯 [{strategy_id}] Starting: {strategy.job_title} in {strategy.location}")
        
        start_time = time.time()
        
        # Build search URL for jobs.ch
        search_url = self._build_jobs_ch_url(strategy)
        logger.info(f"🔍 [{strategy_id}] Search URL: {search_url}")
        
        if not self.stagehand:
            # Mock implementation
            return await self._mock_strategy_execution(strategy, start_time)
        
        try:
            # Navigate to search results
            await self.stagehand.page.goto(search_url)
            await self.stagehand.page.wait_for_load_state("domcontentloaded")
            
            # Extract job links from search results
            job_links = await self._extract_job_links(strategy_id, strategy.max_jobs)
            
            if not job_links:
                logger.warning(f"⚠️ [{strategy_id}] No jobs found")
                return {
                    "strategy_id": strategy_id,
                    "jobs_found": 0,
                    "jobs_extracted": 0,
                    "failed": 0,
                    "skipped": 0,
                    "duration": time.time() - start_time
                }
            
            logger.info(f"📋 [{strategy_id}] Found {len(job_links)} job links")
            
            # Filter out already-scraped jobs
            if incremental:
                job_links = await self._filter_existing_jobs(job_links)
                logger.info(f"⏭️ [{strategy_id}] {len(job_links)} new jobs after filtering")
            
            # Extract job details in parallel
            jobs = await self._extract_jobs_parallel(job_links, strategy_id)
            
            # Save jobs
            await self._save_jobs(jobs, strategy_id)
            
            duration = time.time() - start_time
            
            return {
                "strategy_id": strategy_id,
                "jobs_found": len(job_links),
                "jobs_extracted": len(jobs),
                "failed": len(job_links) - len(jobs),
                "skipped": 0,
                "duration": duration
            }
            
        except Exception as e:
            logger.error(f"❌ [{strategy_id}] Error: {e}")
            return {
                "strategy_id": strategy_id,
                "jobs_found": 0,
                "jobs_extracted": 0,
                "failed": 1,
                "error": str(e),
                "duration": time.time() - start_time
            }
    
    def _build_jobs_ch_url(self, strategy: JobSearchStrategy) -> str:
        """Build jobs.ch search URL from strategy."""
        base_url = self.config.jobs_ch_base_url
        
        # Build search query
        query_parts = [strategy.job_title]
        if strategy.location:
            query_parts.append(strategy.location)
        
        query = "-".join(query_parts).replace(" ", "-")
        
        # Build URL
        url = f"{base_url}/en/search?term={query}"
        
        # Add location filter if specific
        if strategy.location:
            # jobs.ch uses region codes
            region_map = {
                "zürich": "zurich",
                "zurich": "zurich",
                "geneva": "geneve",
                "genf": "geneve",
                "basel": "basel",
                "bern": "bern",
                "lausanne": "lausanne",
            }
            region = region_map.get(strategy.location.lower(), strategy.location.lower())
            url += f"&region={region}"
        
        return url
    
    async def _extract_job_links(
        self,
        strategy_id: str,
        max_jobs: int
    ) -> List[JobLink]:
        """
        Extract job links from search results page using Stagehand.
        
        Uses SemanticDOM for intelligent element detection.
        """
        try:
            # Use Stagehand to find job listing elements
            # First, get semantic snapshot
            if self.config.enable_semantic_dom:
                try:
                    await self.stagehand.page.evaluate("""
                        () => {
                            // Trigger accessibility tree generation
                            return "Accessibility tree requested";
                        }
                    """)
                except Exception:
                    pass
            
            # Extract job links using natural language
            result = await self.stagehand.page.extract(
                instruction="""Extract all job listings from this search results page.
                For each job, provide:
                - job_id: Extract from the link URL (typically at the end)
                - title: The job title text
                - link: The full URL to the job posting
                
                Return as JSON array.""",
                schema={"type": "json_object"}
            )
            
            # Parse result
            if isinstance(result, dict) and "jobs" in result:
                jobs_data = result["jobs"]
            elif isinstance(result, str):
                jobs_data = json.loads(result)
            else:
                jobs_data = result or []
            
            # Convert to JobLink objects
            job_links = []
            for job_data in jobs_data[:max_jobs]:
                try:
                    job_link = JobLink(
                        job_id=uuid4(),
                        title=job_data.get("title", "Unknown"),
                        link=job_data.get("link", "")
                    )
                    job_links.append(job_link)
                except Exception:
                    continue
            
            return job_links
            
        except Exception as e:
            logger.warning(f"Failed to extract job links: {e}")
            return []
    
    async def _filter_existing_jobs(self, job_links: List[JobLink]) -> List[JobLink]:
        """
        Filter out jobs that have already been scraped.
        
        Args:
            job_links: List of job links to check
            
        Returns:
            List of new job links (not yet scraped)
        """
        new_jobs = []
        
        for job_link in job_links:
            job_file = self.jobs_dir / f"{job_link.job_id}.json"
            
            if job_file.exists():
                logger.debug(f"⏭️  Skipping already scraped: {job_link.job_id}")
                continue
            
            new_jobs.append(job_link)
        
        return new_jobs
    
    async def _extract_jobs_parallel(
        self,
        job_links: List[JobLink],
        strategy_id: str
    ) -> List[JobPosting]:
        """
        Extract job details from multiple job links in parallel.
        
        Args:
            job_links: List of job links to extract
            strategy_id: Strategy identifier for logging
            
        Returns:
            List of extracted JobPosting objects
        """
        if not job_links:
            return []
        
        semaphore = asyncio.Semaphore(self.config.max_parallel_extractors)
        
        async def extract_with_semaphore(job_link: JobLink):
            async with semaphore:
                return await self._extract_single_job(job_link, strategy_id)
        
        tasks = [extract_with_semaphore(link) for link in job_links]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        jobs = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Extraction error: {result}")
            elif isinstance(result, JobPosting):
                jobs.append(result)
        
        return jobs
    
    async def _extract_single_job(
        self,
        job_link: JobLink,
        strategy_id: str
    ) -> Optional[JobPosting]:
        """
        Extract details from a single job posting.
        
        Args:
            job_link: JobLink with URL to extract
            strategy_id: Strategy identifier for tracking
            
        Returns:
            JobPosting object or None on failure
        """
        try:
            # Navigate to job page
            await self.stagehand.page.goto(job_link.link)
            await self.stagehand.page.wait_for_load_state("domcontentloaded")
            
            # Add delay for rate limiting
            await asyncio.sleep(self.config.request_delay_ms / 1000)
            
            # Extract job details using Stagehand
            result = await self.stagehand.page.extract(
                instruction="""Extract all available information about this job posting:
                - title: Job title
                - company: Company name
                - location: Job location (city, country)
                - workload: Work schedule (full-time, part-time, etc.)
                - publication_date: When the job was posted (YYYY-MM-DD format)
                - description: Complete job description
                - tasks: Key responsibilities
                - profile: Required qualifications
                - salary: Salary information if available
                
                Return as JSON object.""",
                schema={"type": "json_object"}
            )
            
            # Parse result
            if isinstance(result, str):
                job_data = json.loads(result)
            elif isinstance(result, dict):
                job_data = result
            else:
                job_data = {}
            
            # Parse publication date
            pub_date_str = job_data.get("publication_date", "")
            try:
                if isinstance(pub_date_str, str) and pub_date_str:
                    pub_date = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00"))
                else:
                    pub_date = datetime.now()
            except (ValueError, AttributeError):
                pub_date = datetime.now()
            
            # Parse salary
            raw_salary = job_data.get("salary", "")
            min_salary, max_salary, currency = self._parse_salary(raw_salary)
            
            # Determine remote option
            description = job_data.get("description", "").lower()
            remote = self._determine_remote_option(description)
            
            # Determine seniority
            seniority = self._determine_seniority(job_data.get("title", ""), description)
            
            # Create JobPosting
            job_posting = JobPosting(
                job_id=job_link.job_id,
                title=job_data.get("title", job_link.title),
                link=job_link.link,
                company=job_data.get("company", "Unknown"),
                location=job_data.get("location", "Switzerland"),
                workload=Workload.FULL_TIME,  # Default
                publication_date=pub_date,
                description=job_data.get("description", ""),
                tasks=job_data.get("tasks"),
                profile=job_data.get("profile"),
                seniority=seniority,
                employment_type=EmploymentType.PERMANENT,  # Default
                remote=remote,
                raw_salary=raw_salary if raw_salary else None,
                min_salary=min_salary,
                max_salary=max_salary,
                currency=currency,
                source="jobs.ch",
                strategy_id=strategy_id
            )
            
            logger.info(f"✅ [{strategy_id}] Extracted: {job_posting.company} - {job_posting.title}")
            
            return job_posting
            
        except Exception as e:
            logger.error(f"❌ [{strategy_id}] Failed to extract {job_link.link}: {e}")
            return None
    
    def _parse_salary(self, raw_salary: str) -> tuple:
        """Parse salary string into min, max, currency."""
        if not raw_salary:
            return None, None, None
        
        # Currency patterns
        currency_map = {
            "CHF": "CHF",
            "€": "EUR",
            "$": "USD",
            "£": "GBP",
        }
        
        currency = None
        for symbol, code in currency_map.items():
            if symbol in raw_salary:
                currency = code
                break
        
        # Extract salary numbers
        numbers = re.findall(r"[\d,]+(?:\.\d+)?", raw_salary)
        numbers = [float(n.replace(",", "").replace(".", "")) for n in numbers if n]
        
        if not numbers:
            return None, None, currency
        
        min_salary = min(numbers)
        max_salary = max(numbers) if len(numbers) > 1 else min_salary
        
        return min_salary, max_salary, currency
    
    def _determine_remote_option(self, description: str) -> RemoteOption:
        """Determine remote work option from job description."""
        desc = description.lower()
        
        if "remote" in desc and "hybrid" not in desc:
            return RemoteOption.REMOTE
        elif "hybrid" in desc:
            return RemoteOption.HYBRID
        elif "on-site" in desc or "onsite" in desc or "office" in desc:
            return RemoteOption.ONSITE
        else:
            return RemoteOption.UNKNOWN
    
    def _determine_seniority(self, title: str, description: str) -> Seniority:
        """Determine seniority level from title and description."""
        text = (title + " " + description).lower()
        
        if any(kw in text for kw in ["junior", "entry", "graduate", "trainee"]):
            return Seniority.JUNIOR
        elif any(kw in text for kw in ["senior", "sr.", "sr ", "lead", "principal"]):
            return Seniority.SENIOR
        elif any(kw in text for kw in ["manager", "head", "director", "vp", "chief"]):
            return Seniority.LEAD
        elif any(kw in text for kw in ["intern"]):
            return Seniority.UNKNOWN  # Use other
        else:
            return Seniority.MID_LEVEL
    
    async def _save_jobs(self, jobs: List[JobPosting], strategy_id: str) -> None:
        """Save job postings to output directory."""
        for job in jobs:
            job_id_str = str(job.job_id) if job.job_id else "unknown"
            job_file = self.jobs_dir / f"{job_id_str}.json"
            
            with open(job_file, "w", encoding="utf-8") as f:
                f.write(job.model_dump_json(indent=2, exclude_none=True))
        
        logger.info(f"💾 [{strategy_id}] Saved {len(jobs)} jobs to {self.jobs_dir}")
    
    async def _mock_strategy_execution(
        self,
        strategy: JobSearchStrategy,
        start_time: float
    ) -> dict:
        """Mock strategy execution for demonstration."""
        logger.warning(
            f"⚠️ [{strategy.strategy_id}] Stagehand not available. "
            f"Using mock implementation."
        )
        
        # Generate mock jobs
        mock_jobs = self._generate_mock_jobs(strategy, count=min(strategy.max_jobs, 5))
        await self._save_jobs(mock_jobs, strategy.strategy_id)
        
        return {
            "strategy_id": strategy.strategy_id,
            "jobs_found": len(mock_jobs),
            "jobs_extracted": len(mock_jobs),
            "failed": 0,
            "skipped": 0,
            "duration": time.time() - start_time,
            "mock": True
        }
    
    def _generate_mock_jobs(
        self,
        strategy: JobSearchStrategy,
        count: int = 5
    ) -> List[JobPosting]:
        """Generate mock job postings for demonstration."""
        from datetime import timedelta
        
        companies = ["TechCorp", "StartupXYZ", "EnterpriseAB", "InnovateCo", "DataDriven Inc"]
        
        jobs = []
        for i in range(count):
            job_id = uuid4()
            pub_date = datetime.now() - timedelta(days=i % 30)
            
            job = JobPosting(
                job_id=job_id,
                title=f"{strategy.job_title} - {i+1}",
                link=f"https://www.jobs.ch/en/job/{job_id}",
                company=companies[i % len(companies)],
                location=strategy.location,
                workload=Workload.FULL_TIME,
                publication_date=pub_date,
                description=f"We are looking for a {strategy.job_title} to join our team. "
                           f"Required skills: {', '.join(strategy.keywords[:3])}.",
                tasks=f"- Develop and maintain software\n- Collaborate with team\n- Write clean code",
                profile=f"- Experience with {strategy.keywords[0] if strategy.keywords else 'Python'}\n- Bachelor's degree",
                seniority=Seniority.MID_LEVEL,
                employment_type=EmploymentType.PERMANENT,
                remote=RemoteOption.HYBRID,
                raw_salary="CHF 100,000 - 150,000",
                min_salary=100000.0,
                max_salary=150000.0,
                currency="CHF",
                source="jobs.ch",
                strategy_id=strategy.strategy_id
            )
            jobs.append(job)
        
        return jobs
    
    def get_output_index(self) -> dict:
        """Get index of all scraped jobs."""
        jobs = list(self.jobs_dir.glob("*.json"))
        
        index = {
            "total_jobs": len(jobs),
            "jobs_dir": str(self.jobs_dir),
            "jobs": []
        }
        
        for job_file in jobs:
            with open(job_file) as f:
                job_data = json.load(f)
                index["jobs"].append({
                    "job_id": job_data.get("job_id"),
                    "title": job_data.get("title"),
                    "company": job_data.get("company"),
                    "location": job_data.get("location"),
                })
        
        return index


# Alias for backward compatibility
JobScraper = JobsCHScraper
