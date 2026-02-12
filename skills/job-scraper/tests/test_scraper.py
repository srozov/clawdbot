"""Tests for job scraper core functionality."""

import pytest
import tempfile
import asyncio
import json
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from job_scraper.scraper import JobsCHScraper
from job_scraper.models import GlobalConfig, JobSearchStrategy


class TestJobsCHScraper:
    """Tests for JobsCHScraper class."""

    @pytest.fixture
    def scraper(self, tmp_path):
        """Create scraper with temp directories."""
        config = GlobalConfig(
            max_parallel_strategies=3,
            max_jobs_per_strategy=50,
            jobs_dir=str(tmp_path / "output"),
            cache_dir=str(tmp_path / "cache"),
        )
        return JobsCHScraper(config=config)

    def test_initialization(self, scraper):
        """Test scraper initialization."""
        assert scraper.config.max_parallel_strategies == 3
        assert scraper.jobs_dir.exists()
        assert scraper.cache_dir.exists()

    def test_build_jobs_ch_url(self, scraper):
        """Test jobs.ch URL building."""
        strategy = JobSearchStrategy(
            job_title="Python Developer",
            location="Zürich"
        )
        
        url = scraper._build_jobs_ch_url(strategy)
        
        assert "jobs.ch" in url
        assert "Python-Developer" in url or "python-developer" in url.lower()

    def test_build_url_with_location(self, scraper):
        """Test URL building with location."""
        strategy = JobSearchStrategy(
            job_title="ML Engineer",
            location="Bern"
        )
        
        url = scraper._build_jobs_ch_url(strategy)
        
        assert "Bern" in url or "bern" in url.lower()

    def test_parse_salary_chf(self, scraper):
        """Test CHF salary parsing."""
        raw = "CHF 100,000 - 150,000"
        min_s, max_s, currency = scraper._parse_salary(raw)
        
        assert min_s == 100000.0
        assert max_s == 150000.0
        assert currency == "CHF"

    def test_parse_salary_eur(self, scraper):
        """Test EUR salary parsing."""
        raw = "€80,000 - €100,000"
        min_s, max_s, currency = scraper._parse_salary(raw)
        
        assert min_s == 80000.0
        assert max_s == 100000.0
        assert currency == "EUR"

    def test_parse_salary_empty(self, scraper):
        """Test empty salary parsing."""
        min_s, max_s, currency = scraper._parse_salary("")
        
        assert min_s is None
        assert max_s is None
        assert currency is None

    def test_determine_remote_hybrid(self, scraper):
        """Test remote option detection for hybrid."""
        desc = "This is a hybrid role with remote work options"
        remote = scraper._determine_remote_option(desc)
        
        assert remote.value == "hybrid"

    def test_determine_remote_full(self, scraper):
        """Test remote option detection for full remote."""
        desc = "This is a fully remote position"
        remote = scraper._determine_remote_option(desc)
        
        assert remote.value == "remote"

    def test_determine_remote_onsite(self, scraper):
        """Test remote option detection for onsite."""
        desc = "Work on-site at our office"
        remote = scraper._determine_remote_option(desc)
        
        assert remote.value == "on-site"

    def test_determine_seniority_senior(self, scraper):
        """Test seniority detection for senior."""
        title = "Senior Python Developer"
        desc = "looking for an experienced developer"
        seniority = scraper._determine_seniority(title, desc)
        
        assert seniority.value == "senior"

    def test_determine_seniority_junior(self, scraper):
        """Test seniority detection for junior."""
        title = "Junior Developer"
        desc = "entry level position for graduates"
        seniority = scraper._determine_seniority(title, desc)
        
        assert seniority.value == "junior"

    def test_determine_seniority_mid(self, scraper):
        """Test seniority detection for mid-level."""
        title = "Software Engineer"
        desc = "collaborate with the team"
        seniority = scraper._determine_seniority(title, desc)
        
        assert seniority.value == "mid-level"

    @pytest.mark.asyncio
    async def test_get_output_index(self, scraper, tmp_path):
        """Test getting output index."""
        # Create some mock job files
        jobs_dir = scraper.jobs_dir
        jobs_dir.mkdir(parents=True, exist_ok=True)
        
        for i in range(3):
            job_file = jobs_dir / f"job-{i}.json"
            with open(job_file, "w") as f:
                json.dump({
                    "job_id": f"job-{i}",
                    "title": f"Job {i}",
                    "company": f"Company {i}",
                    "location": "Zürich"
                }, f)
        
        index = scraper.get_output_index()
        
        assert index["total_jobs"] == 3
        assert len(index["jobs"]) == 3


class TestScraperParallelExecution:
    """Tests for parallel execution in the scraper."""

    @pytest.fixture
    def scraper(self, tmp_path):
        """Create scraper for parallel testing."""
        config = GlobalConfig(
            max_parallel_strategies=3,
            max_jobs_per_strategy=50,
            jobs_dir=str(tmp_path / "output"),
            cache_dir=str(tmp_path / "cache"),
        )
        return JobsCHScraper(config=config)

    @pytest.mark.asyncio
    async def test_mock_strategy_execution(self, scraper):
        """Test mock strategy execution (no Stagehand)."""
        strategy = JobSearchStrategy(
            job_title="Test Role",
            location="Zürich",
            max_jobs=3,
            strategy_id="test-mock"
        )
        
        import time
        start_time = time.time()
        result = await scraper._mock_strategy_execution(strategy, start_time)
        
        assert result["strategy_id"] == "test-mock"
        assert result["jobs_found"] == 3
        assert result["jobs_extracted"] == 3
        assert result["failed"] == 0
        assert result["mock"] is True

    @pytest.mark.asyncio
    async def test_filter_existing_jobs(self, scraper):
        """Test filtering already scraped jobs."""
        from uuid import uuid4
        from job_scraper.models import JobLink
        
        # Create existing job file with UUID
        existing_id = uuid4()
        job_file = scraper.jobs_dir / f"{existing_id}.json"
        job_file.write_text(f'{{"job_id": "{existing_id}"}}')
        
        # Create new job links
        new_link = JobLink(
            job_id=uuid4(),
            title="New Job",
            link="https://example.com/new"
        )
        existing_link = JobLink(
            job_id=existing_id,
            title="Existing Job",
            link="https://example.com/existing"
        )
        
        links = [new_link, existing_link]
        filtered = await scraper._filter_existing_jobs(links)
        
        assert len(filtered) == 1
        assert filtered[0].job_id == new_link.job_id

    @pytest.mark.asyncio
    async def test_run_single_strategy_mock(self, scraper):
        """Test running a single strategy with mock mode."""
        strategy = JobSearchStrategy(
            job_title="Mock Role",
            location="Zürich",
            max_jobs=2,
            strategy_id="single-mock"
        )
        
        result = await scraper._run_single_strategy(strategy, incremental=False)
        
        assert result["strategy_id"] == "single-mock"
        assert result["jobs_found"] == 2
        assert result["jobs_extracted"] == 2
        assert result["mock"] is True

    @pytest.mark.asyncio
    async def test_run_multiple_strategies_parallel(self, scraper):
        """Test running multiple strategies in parallel."""
        strategies = [
            JobSearchStrategy(
                job_title=f"Role {i}",
                location="Zürich",
                max_jobs=2,
                strategy_id=f"parallel_{i}"
            )
            for i in range(3)
        ]
        
        stats = await scraper.run_strategies(strategies, incremental=False)
        
        assert stats.total_strategies == 3
        assert stats.total_jobs_found == 6  # 2 jobs * 3 strategies
        assert stats.total_jobs_extracted == 6
        assert stats.total_failed == 0


class TestScraperPerformance:
    """Performance-related tests for the scraper."""

    @pytest.fixture
    def scraper(self, tmp_path):
        """Create scraper for performance testing."""
        config = GlobalConfig(
            max_parallel_strategies=3,
            max_jobs_per_strategy=50,
            jobs_dir=str(tmp_path / "output"),
            cache_dir=str(tmp_path / "cache"),
        )
        return JobsCHScraper(config=config)

    @pytest.mark.asyncio
    async def test_concurrent_strategy_execution(self, scraper):
        """Test that strategies execute concurrently."""
        import time
        
        start = time.time()
        
        strategies = [
            JobSearchStrategy(
                job_title=f"Concurrent Role {i}",
                location="Zürich",
                max_jobs=2,
                strategy_id=f"concurrent_{i}"
            )
            for i in range(3)
        ]
        
        stats = await scraper.run_strategies(strategies, incremental=False)
        
        elapsed = time.time() - start
        
        # All strategies should complete in reasonable time
        assert stats.total_jobs_extracted == 6  # 2 jobs * 3 strategies
        assert elapsed < 10.0  # Should complete quickly due to parallelism


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
