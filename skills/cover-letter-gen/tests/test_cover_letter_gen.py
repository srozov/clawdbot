"""
Test cover letter generator skill.
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from cover_letter_gen.models import (
    CoverLetterConfig,
    CoverLetterResult,
    ApplicationMetadata,
    ApplicationIndex,
    MatchInfo,
    JobPosting,
    CompanyResearch,
    ViableMatches,
)
from cover_letter_gen.generator import CoverLetterGenerator
from cover_letter_gen.cv_customizer import CVCustomizer
from cover_letter_gen.research import CompanyResearcher


class TestModels:
    """Test Pydantic models."""

    def test_cover_letter_config_defaults(self):
        """Test default configuration values."""
        config = CoverLetterConfig()
        assert config.llm_model == "anthropic/claude-sonnet-4"
        assert config.style == "adaptive"
        assert config.enable_company_research is True
        assert config.max_length_words == 350
        assert config.min_match_score == 0.6

    def test_match_info(self):
        """Test MatchInfo model."""
        match = MatchInfo(
            job_id="test-123",
            company="TestCorp",
            title="Software Engineer",
            location="Zürich",
            match_score=0.85,
            match_reasoning="Strong Python skills",
            matched_keywords=["Python", "Django"],
            missing_keywords=["Kubernetes"],
        )
        assert match.job_id == "test-123"
        assert match.match_score == 0.85

    def test_job_posting(self):
        """Test JobPosting model."""
        job = JobPosting(
            job_id="job-456",
            title="Senior Developer",
            company="TechCo",
            location="Zürich",
            description="Looking for a senior developer...",
            min_salary=120000,
            max_salary=150000,
            currency="CHF",
        )
        assert job.title == "Senior Developer"
        assert job.min_salary == 120000

    def test_company_research(self):
        """Test CompanyResearch model."""
        research = CompanyResearch(
            name="TestCorp",
            industry="Technology",
            mission="Building the future",
            values=["innovation", "customer-first"],
            recent_news=["Launched new product"],
        )
        assert research.name == "TestCorp"
        assert len(research.values) == 2

    def test_application_metadata_create(self):
        """Test ApplicationMetadata.create() method."""
        metadata = ApplicationMetadata.create(
            job_id="test-123",
            company="TestCorp",
            title="Developer",
            match_score=0.85,
            resume_content="My resume content",
        )
        assert metadata.job_id == "test-123"
        assert metadata.company == "TestCorp"
        assert len(metadata.resume_hash) == 16
        assert metadata.cached is False

    def test_application_index(self):
        """Test ApplicationIndex model."""
        index = ApplicationIndex()
        index.add_application(
            company="TestCorp",
            title="Developer",
            output_dir="applications/TestCorp_Developer",
            match_score=0.85,
            cached=False,
        )
        assert index.total == 1
        assert index.generated == 1
        assert len(index.applications) == 1


class TestGenerator:
    """Test cover letter generator."""

    def test_generator_defaults(self):
        """Test generator default values."""
        generator = CoverLetterGenerator()
        assert generator.style == "adaptive"
        assert generator.max_length_words == 350

    def test_generator_custom_config(self):
        """Test generator with custom config."""
        generator = CoverLetterGenerator(
            style="formal",
            max_length_words=500,
        )
        assert generator.style == "formal"
        assert generator.max_length_words == 500

    @pytest.mark.asyncio
    async def test_generate_fallback(self):
        """Test fallback cover letter generation."""
        generator = CoverLetterGenerator(llm_client=None)

        job = JobPosting(
            job_id="test-123",
            title="Software Engineer",
            company="TestCorp",
            location="Zürich",
            description="Looking for a Python developer...",
        )

        match = MatchInfo(
            job_id="test-123",
            company="TestCorp",
            title="Software Engineer",
            location="Zürich",
            match_score=0.85,
            match_reasoning="Strong Python skills",
            matched_keywords=["Python", "Django"],
            missing_keywords=["Kubernetes"],
        )

        result = await generator.generate(
            job=job,
            match=match,
            resume_content="My resume content",
        )

        assert isinstance(result, CoverLetterResult)
        assert "Software Engineer" in result.content
        assert "TestCorp" in result.content


class TestCVCustomizer:
    """Test CV customizer."""

    def test_cv_customizer_defaults(self):
        """Test customizer default values."""
        customizer = CVCustomizer()
        assert customizer.llm is None

    def test_extract_sections(self):
        """Test resume section extraction."""
        customizer = CVCustomizer()

        resume = """## Summary
Experienced developer

## Skills
Python, Django

## Experience
Senior Developer at Tech Corp
"""

        sections = customizer._extract_resume_sections(resume)

        assert "Summary" in sections
        assert "Skills" in sections
        assert "Experience" in sections
        assert "Experienced developer" in sections["Summary"]

    def test_highlight_matching_skills(self):
        """Test highlighting matching skills."""
        customizer = CVCustomizer()

        skills = """- Python
- Django
- React
- JavaScript"""

        highlighted = customizer._highlight_matching_skills(
            skills, ["Python", "Django"]
        )

        assert "**- Python**" in highlighted
        assert "**- Django**" in highlighted
        assert "- React" in highlighted

    @pytest.mark.asyncio
    async def test_customize_cv(self):
        """Test CV customization."""
        customizer = CVCustomizer(llm_client=None)

        resume = """## Summary
Experienced developer

## Skills
Python, Django, Kubernetes

## Experience
Senior Developer at Tech Corp
Built Python APIs using Django
"""

        job = JobPosting(
            job_id="test-123",
            title="Python Developer",
            company="TestCorp",
            location="Zürich",
            description="Looking for Python developer...",
        )

        match = MatchInfo(
            job_id="test-123",
            company="TestCorp",
            title="Python Developer",
            location="Zürich",
            match_score=0.85,
            match_reasoning="Strong Python skills",
            matched_keywords=["Python", "Django"],
            missing_keywords=["Kubernetes"],
        )

        result = await customizer.customize_cv(
            resume_content=resume,
            job=job,
            match=match,
        )

        assert result.content is not None
        assert len(result.highlighted_experience) > 0


class TestResearcher:
    """Test company researcher."""

    def test_researcher_defaults(self):
        """Test researcher default values."""
        researcher = CompanyResearcher()
        assert researcher.ttl_days == 7

    def test_get_cache_path(self):
        """Test cache path generation."""
        researcher = CompanyResearcher()
        path = researcher._get_cache_path("Test Corp")
        assert "Test_Corp" in str(path)

    def test_get_cache_key(self):
        """Test cache key generation."""
        researcher = CompanyResearcher()
        key1 = researcher._get_cache_key("Test Corp")
        key2 = researcher._get_cache_key("test corp")
        assert key1 == key2
        assert len(key1) == 16

    def test_is_cache_valid(self):
        """Test cache validation."""
        import tempfile
        import time

        researcher = CompanyResearcher(
            cache_dir=tempfile.mkdtemp(),
            ttl_days=7,
        )

        # Non-existent file
        assert researcher._is_cache_valid(Path("/nonexistent/file.json")) is False

        # Create a temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"test": "data"}, f)
            temp_path = Path(f.name)

        # File should be valid
        assert researcher._is_cache_valid(temp_path) is True

        # Cleanup
        temp_path.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
