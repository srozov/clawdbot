"""Tests for job scraper models."""

import pytest
from datetime import datetime
from uuid import uuid4

from job_scraper.models import (
    JobSearchStrategy,
    GlobalConfig,
    JobPosting,
    ScrapingStats,
    JobLink,
    Workload,
    RemoteOption,
    Seniority,
)


class TestJobSearchStrategy:
    """Tests for JobSearchStrategy model."""

    def test_default_values(self):
        """Test default strategy values."""
        strategy = JobSearchStrategy(
            job_title="Python Developer",
            location="Zürich"
        )
        assert strategy.job_title == "Python Developer"
        assert strategy.location == "Zürich"
        assert strategy.keywords == []
        assert strategy.strategy_id == "default"
        assert strategy.max_jobs == 50

    def test_full_strategy(self):
        """Test strategy with all fields."""
        strategy = JobSearchStrategy(
            job_title="Senior ML Engineer",
            location="Berlin",
            keywords=["Python", "TensorFlow", "AWS"],
            strategy_id="ml_senior",
            category="core_expertise",
            max_jobs=100
        )
        assert strategy.keywords == ["Python", "TensorFlow", "AWS"]
        assert strategy.category == "core_expertise"
        assert strategy.max_jobs == 100

    def test_strategy_with_filters(self):
        """Test strategy with filtering options."""
        strategy = JobSearchStrategy(
            job_title="DevOps Engineer",
            location="Zürich",
            keywords=["Kubernetes", "Docker"],
            required_keywords=["AWS", "Kubernetes"],
            excluded_keywords=["manager", "director"],
            remote_preference="hybrid",
            salary_min=120000
        )
        assert strategy.required_keywords == ["AWS", "Kubernetes"]
        assert strategy.excluded_keywords == ["manager", "director"]
        assert strategy.remote_preference == "hybrid"
        assert strategy.salary_min == 120000


class TestGlobalConfig:
    """Tests for GlobalConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = GlobalConfig()
        assert config.max_parallel_strategies == 3
        assert config.max_jobs_per_strategy == 50
        assert config.headless is True
        assert config.cache_ttl_hours == 24
        assert config.jobs_ch_base_url == "https://www.jobs.ch"

    def test_custom_config(self):
        """Test custom configuration."""
        config = GlobalConfig(
            max_parallel_strategies=5,
            max_jobs_per_strategy=100,
            headless=False,
            jobs_dir="custom/output"
        )
        assert config.max_parallel_strategies == 5
        assert config.headless is False

    def test_config_load_save(self, tmp_path):
        """Test config save and load."""
        config = GlobalConfig(
            max_parallel_strategies=4,
        )
        
        config_path = tmp_path / "config.json"
        config.save(str(config_path))
        
        loaded = GlobalConfig.load(str(config_path))
        # Verify the loaded config has correct values
        assert loaded.max_parallel_strategies == 4


class TestJobPosting:
    """Tests for JobPosting model."""

    def test_job_posting_creation(self):
        """Test creating a job posting."""
        job = JobPosting(
            job_id=uuid4(),
            title="Senior Python Developer",
            link="https://www.jobs.ch/job/123",
            company="TechCorp",
            location="Zürich",
            workload=Workload.FULL_TIME,
            publication_date=datetime.now(),
            description="Looking for a senior Python developer"
        )
        assert job.title == "Senior Python Developer"
        assert job.company == "TechCorp"
        assert job.workload == Workload.FULL_TIME
        assert job.source == "jobs.ch"

    def test_job_posting_defaults(self):
        """Test job posting default values."""
        job = JobPosting(
            title="Developer",
            link="https://example.com/job",
            company="TestCo",
            location="Berlin",
            workload=Workload.FULL_TIME,
            publication_date=datetime.now(),
            description="Test job"
        )
        assert job.seniority == Seniority.UNKNOWN
        assert job.remote == RemoteOption.UNKNOWN
        assert job.min_salary is None
        assert job.source == "jobs.ch"
        assert job.strategy_id is None


class TestScrapingStats:
    """Tests for ScrapingStats model."""

    def test_stats_creation(self):
        """Test creating scraping statistics."""
        stats = ScrapingStats(
            total_strategies=3,
            total_jobs_found=150,
            total_jobs_extracted=145,
            total_failed=5,
            duration_seconds=300.0
        )
        assert stats.total_strategies == 3
        assert stats.total_jobs_extracted == 145
        assert stats.incremental_skipped == 0
        assert len(stats.strategy_stats) == 0

    def test_stats_with_incremental(self):
        """Test stats with incremental processing."""
        stats = ScrapingStats(
            total_strategies=2,
            total_jobs_found=100,
            total_jobs_extracted=85,
            total_failed=5,
            incremental_skipped=10,
            duration_seconds=200.0,
            strategy_stats=[
                {"strategy_id": "python", "jobs_extracted": 50, "skipped": 5},
                {"strategy_id": "ml", "jobs_extracted": 35, "skipped": 5}
            ]
        )
        assert stats.incremental_skipped == 10
        assert len(stats.strategy_stats) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
