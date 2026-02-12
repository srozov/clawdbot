"""
Pydantic models for cover letter generation.
"""

import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

from pydantic import BaseModel, Field


class CoverLetterConfig(BaseModel):
    """Configuration for cover letter generation."""

    llm_model: str = "anthropic/claude-sonnet-4"
    style: str = "adaptive"
    enable_company_research: bool = True
    company_cache_ttl_days: int = 7
    max_length_words: int = 350
    min_match_score: float = 0.6
    output_dir: str = "applications"


class MatchInfo(BaseModel):
    """Information about a job match."""

    job_id: str
    company: str
    title: str
    location: str
    match_score: float
    match_reasoning: str
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    salary_estimate: Optional[Dict[str, Any]] = None


class JobPosting(BaseModel):
    """Job posting data."""

    job_id: str
    title: str
    company: str
    location: str
    link: Optional[str] = None
    description: str
    workload: Optional[str] = None
    employment_type: Optional[str] = None
    remote: Optional[str] = None
    salary: Optional[str] = None
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    currency: Optional[str] = None


class CompanyResearch(BaseModel):
    """Company research results."""

    name: str
    industry: Optional[str] = None
    size: Optional[str] = None
    mission: Optional[str] = None
    values: List[str] = Field(default_factory=list)
    recent_news: List[str] = Field(default_factory=list)
    culture: Optional[str] = None
    products: List[str] = Field(default_factory=list)
    competitors: List[str] = Field(default_factory=list)
    funding: Optional[str] = None
    headquarters: Optional[str] = None
    founded: Optional[str] = None


class CoverLetterResult(BaseModel):
    """Generated cover letter result."""

    content: str
    company_context: Optional[str] = None
    key_selling_points: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


class CVResult(BaseModel):
    """Generated CV result."""

    content: str
    highlighted_experience: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


class ApplicationMetadata(BaseModel):
    """Application metadata."""

    job_id: str
    company: str
    title: str
    match_score: float
    generated_at: datetime = Field(default_factory=datetime.now)
    resume_hash: str
    company_research: Optional[Dict[str, Any]] = None
    cached: bool = False
    style_used: str = "adaptive"

    @classmethod
    def create(
        cls,
        job_id: str,
        company: str,
        title: str,
        match_score: float,
        resume_content: str,
        company_research: Optional[CompanyResearch] = None,
        cached: bool = False,
    ) -> "ApplicationMetadata":
        """Create metadata with computed resume hash."""
        resume_hash = hashlib.md5(resume_content.encode()).hexdigest()[:16]
        return cls(
            job_id=job_id,
            company=company,
            title=title,
            match_score=match_score,
            resume_hash=resume_hash,
            company_research=company_research.model_dump() if company_research else None,
            cached=cached,
        )


class ApplicationIndex(BaseModel):
    """Index of all generated applications."""

    applications: List[Dict[str, Any]] = Field(default_factory=list)
    total: int = 0
    generated: int = 0
    cached: int = 0
    failed: int = 0
    generated_at: datetime = Field(default_factory=datetime.now)

    def add_application(
        self,
        company: str,
        title: str,
        output_dir: str,
        match_score: float,
        cached: bool = False,
    ) -> None:
        """Add an application to the index."""
        self.applications.append({
            "company": company,
            "title": title,
            "output_dir": output_dir,
            "match_score": match_score,
            "generated_at": datetime.now().isoformat(),
            "cached": cached,
        })
        self.total += 1
        if cached:
            self.cached += 1
        else:
            self.generated += 1


class ViableMatches(BaseModel):
    """Container for viable job matches."""

    matches: List[MatchInfo] = Field(default_factory=list)
    resume_hash: Optional[str] = None
    generated_at: Optional[str] = None
