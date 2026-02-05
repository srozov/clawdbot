"""
Notion Tracker models for data validation.
"""
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class ApplicationStatus(str, Enum):
    """Application status enumeration."""
    NOT_APPLIED = "Not Applied"
    APPLIED = "Applied"
    INTERVIEW_SCHEDULED = "Interview Scheduled"
    REJECTED = "Rejected"
    OFFER = "Offer"


class RemotePreference(str, Enum):
    """Remote work preference."""
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    ANY = "any"


class SeniorityLevel(str, Enum):
    """Seniority level enumeration."""
    INTERN = "intern"
    JUNIOR = "junior"
    MID_LEVEL = "mid-level"
    SENIOR = "senior"
    LEAD = "lead"
    STAFF = "staff"
    PRINCIPAL = "principal"
    DIRECTOR = "director"
    EXECUTIVE = "executive"


class StrategyCategory(str, Enum):
    """Strategy category for job search."""
    CORE = "core"
    ADJACENT = "adjacent"
    GROWTH = "growth"


class ApplicationMetadata(BaseModel):
    """Metadata for a job application."""
    job_id: str = Field(..., description="Unique job identifier")
    company: str = Field(..., description="Company name")
    title: str = Field(..., description="Job title")
    match_score: float = Field(..., ge=0, le=1, description="Match score 0-1")
    generated_at: datetime = Field(default_factory=datetime.now)
    company_research: Optional[str] = None


class ApplicationInput(BaseModel):
    """Input model for application data from file system."""
    company: str
    title: str
    location: Optional[str] = None
    link: Optional[str] = None
    description: Optional[str] = None
    match_score: float = 0.0
    match_reasoning: Optional[str] = None
    key_matches: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    strategy_id: Optional[str] = None
    remote: Optional[str] = None
    seniority: Optional[str] = None
    salary_estimate: Optional[str] = None
    category: Optional[str] = None
    status: str = "Not Applied"


class NotionPageProperties(BaseModel):
    """Properties for creating Notion page."""
    company: str = Field(..., description="Company name")
    job_title: str = Field(..., description="Job title")
    location: Optional[str] = None
    application_date: Optional[datetime] = None
    status: ApplicationStatus = ApplicationStatus.NOT_APPLIED
    match_score: float = 0.0
    salary_estimate: Optional[str] = None
    job_link: Optional[str] = None
    workload: Optional[str] = None
    remote: Optional[str] = None
    match_reasoning: Optional[str] = None
    category: Optional[str] = None
    priority: str = "Medium"
    next_action: Optional[str] = None
    custom_notes: Optional[str] = None
    key_matches: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    strategy_id: Optional[str] = None
    seniority: Optional[str] = None
    output_path: Optional[str] = None


class SyncStatus(str, Enum):
    """Sync operation status."""
    PENDING = "pending"
    SYNCED = "synced"
    FAILED = "failed"
    SKIPPED = "skipped"
    UPDATED = "updated"


class SyncResult(BaseModel):
    """Result of syncing a single application."""
    job_id: str
    company: str
    title: str
    notion_page_id: Optional[str] = None
    status: SyncStatus = SyncStatus.PENDING
    synced_at: Optional[datetime] = None
    error: Optional[str] = None


class SyncSummary(BaseModel):
    """Summary of sync operation."""
    synced_at: datetime = Field(default_factory=datetime.now)
    total_applications: int = 0
    synced: int = 0
    failed: int = 0
    skipped: int = 0
    results: List[SyncResult] = Field(default_factory=list)


class NotionConfig(BaseModel):
    """Configuration for Notion integration."""
    database_id: str = Field(..., description="Notion database ID")
    oauth_enabled: bool = True
    sync_mode: str = "incremental"
    default_status: str = "Not Applied"
    rate_limit_delay: float = 0.35  # Notion allows ~3 requests/second
    max_retries: int = 3


class OAuthTokenData(BaseModel):
    """OAuth token data storage model."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_in: int = 3600
    issued_at: Optional[int] = None
    token_type: str = "bearer"
