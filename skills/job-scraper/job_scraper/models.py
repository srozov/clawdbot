"""Pydantic models for job scraper skill."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from uuid import UUID
from pathlib import Path
import json


class Workload(str, Enum):
    """Workload options for job postings."""
    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    OTHER = "other"


class RemoteOption(str, Enum):
    """Remote work options."""
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "on-site"
    UNKNOWN = "unknown"


class Seniority(str, Enum):
    """Seniority levels."""
    JUNIOR = "junior"
    MID_LEVEL = "mid-level"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"
    UNKNOWN = "unknown"


class EmploymentType(str, Enum):
    """Employment type options."""
    PERMANENT = "permanent"
    TEMPORARY = "temporary"
    INTERNSHIP = "internship"
    FREELANCE = "freelance"
    UNKNOWN = "unknown"


class JobLink(BaseModel):
    """A model to store the title, link, and ID of a job posting link."""
    job_id: UUID = Field(description="UUID for the job posting")
    title: str = Field(description="Job title")
    link: str = Field(description="Full URL to the job posting")


class JobPosting(BaseModel):
    """Complete job posting data extracted from job sites."""
    job_id: Optional[UUID] = Field(default=None, description="UUID for the job")
    title: str = Field(description="Job title")
    link: str = Field(description="Full URL to the job posting")
    company: str = Field(description="Company name")
    location: str = Field(description="Job location")
    
    workload: Workload = Field(description="Work schedule")
    publication_date: datetime = Field(description="Date posted")
    description: str = Field(description="Job description")
    
    tasks: Optional[str] = Field(None, description="Job responsibilities")
    profile: Optional[str] = Field(None, description="Required qualifications")
    
    seniority: Seniority = Seniority.UNKNOWN
    employment_type: EmploymentType = EmploymentType.UNKNOWN
    remote: RemoteOption = RemoteOption.UNKNOWN
    
    raw_salary: Optional[str] = Field(None, description="Salary text from posting")
    min_salary: Optional[float] = Field(None, description="Minimum salary")
    max_salary: Optional[float] = Field(None, description="Maximum salary")
    currency: Optional[str] = Field(None, description="Currency code")
    
    # Source tracking
    source: str = Field(default="jobs.ch", description="Job board source")
    strategy_id: Optional[str] = Field(None, description="Source strategy ID")
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            UUID: lambda v: str(v)
        }


class JobSearchStrategy(BaseModel):
    """A single job search strategy."""
    job_title: str = Field(description="Job title to search for")
    location: str = Field(description="Geographic location")
    keywords: List[str] = Field(default_factory=list, description="Key skills/technologies")
    strategy_id: str = Field(default="default", description="Unique strategy identifier")
    category: Optional[str] = Field(None, description="Strategy category")
    max_jobs: int = Field(default=50, description="Maximum jobs to collect")
    
    # Filtering options
    required_keywords: List[str] = Field(default_factory=list)
    excluded_keywords: List[str] = Field(default_factory=list)
    seniority_range: Optional[tuple] = Field(None)
    remote_preference: Optional[str] = Field(None)
    salary_min: Optional[int] = Field(None)


class GlobalConfig(BaseModel):
    """Global configuration for job scraper."""
    
    # Output directories
    jobs_dir: str = Field(default="jobs/raw", description="Raw job postings directory")
    cache_dir: str = Field(default=".cache/job-scraper", description="Cache directory")
    strategies_dir: str = Field(default="strategies", description="Strategies directory")
    
    # Browser settings
    headless: bool = Field(default=True, description="Run browser headless")
    stealth: bool = Field(default=True, description="Use stealth mode")
    window_width: int = Field(default=600, description="Browser window width")
    window_height: int = Field(default=900, description="Browser window height")
    
    # Model settings
    llm_model: str = Field(
        default="openrouter/google/gemini-2.5-flash-lite",
        description="LLM model for extraction"
    )
    llm_api_key: Optional[str] = Field(None, description="LLM API key")
    llm_base_url: Optional[str] = Field(None, description="LLM base URL")
    
    # Performance settings
    max_parallel_strategies: int = Field(default=3, description="Parallel strategy execution")
    max_jobs_per_strategy: int = Field(default=50, description="Max jobs per strategy")
    max_parallel_extractors: int = Field(default=5, description="Parallel job extractors")
    request_delay_ms: int = Field(default=1000, description="Delay between requests")
    
    # Semantic DOM
    enable_semantic_dom: bool = Field(default=True, description="Use semantic DOM for extraction")
    semantic_model: str = Field(default="all-mpnet-base-v2", description="Embedding model")
    
    # Caching
    cache_ttl_hours: int = Field(default=24, description="Cache TTL in hours")
    
    # Job board settings
    target_sites: List[str] = Field(default=["jobs.ch"], description="Target job boards")
    jobs_ch_base_url: str = Field(default="https://www.jobs.ch", description="jobs.ch base URL")
    
    # Login credentials (optional)
    jobs_user: Optional[str] = Field(None, description="jobs.ch username")
    jobs_password: Optional[str] = Field(None, description="jobs.ch password")
    
    @classmethod
    def load(cls, config_path: str = "config/global.json") -> "GlobalConfig":
        """Load config from JSON file or return defaults."""
        path = Path(config_path)
        if path.exists():
            with open(path) as f:
                data = json.load(f)
            return cls(**data)
        return cls()
    
    def save(self, config_path: str = "config/global.json") -> None:
        """Save config to JSON file."""
        path = Path(config_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(self.model_dump_json(indent=2))


class ScrapingStats(BaseModel):
    """Statistics from a scraping run."""
    total_strategies: int = 0
    total_jobs_found: int = 0
    total_jobs_extracted: int = 0
    total_failed: int = 0
    duration_seconds: float = 0.0
    strategy_stats: List[dict] = Field(default_factory=list)
    incremental_skipped: int = 0


class ExtractionResult(BaseModel):
    """Result from a single job extraction."""
    job_id: str
    success: bool
    title: Optional[str] = None
    company: Optional[str] = None
    error: Optional[str] = None
