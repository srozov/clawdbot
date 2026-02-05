"""Pydantic models for job matcher skill."""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class MatchScore(BaseModel):
    """Breakdown of match scoring."""
    keyword_score: float = Field(0.0, ge=0, le=1, description="Keyword match score (0-1)")
    location_score: float = Field(0.0, ge=0, le=1, description="Location match score (0-1)")
    seniority_score: float = Field(0.0, ge=0, le=1, description="Seniority match score (0-1)")
    remote_score: float = Field(0.0, ge=0, le=1, description="Remote preference match (0-1)")
    salary_score: float = Field(0.0, ge=0, le=1, description="Salary expectation match (0-1)")
    overall_score: float = Field(0.0, ge=0, le=1, description="Weighted overall score")


class MatchReasoning(BaseModel):
    """Detailed reasoning for a job-strategy match."""
    keyword_match: str = Field("", description="Which keywords matched/missed")
    location_match: str = Field("", description="Location compatibility notes")
    seniority_match: str = Field("", description="Seniority level alignment notes")
    remote_match: str = Field("", description="Remote work compatibility notes")
    salary_match: str = Field("", description="Salary range compatibility notes")
    strengths: List[str] = Field(default_factory=list, description="Match strengths")
    concerns: List[str] = Field(default_factory=list, description="Potential concerns")


class JobMatch(BaseModel):
    """A single job matched against a strategy."""
    job_id: str = Field(..., description="Unique job identifier")
    strategy_id: str = Field(..., description="Strategy this job was matched against")
    
    # Job details (denormalized for convenience)
    job_title: str = Field(..., description="Job title")
    job_link: str = Field(..., description="URL to job posting")
    company: str = Field(..., description="Company name")
    job_location: str = Field(..., description="Job location")
    description: str = Field(..., description="Job description snippet")
    
    # Match results
    score: float = Field(..., ge=0, le=1, description="Overall match score (0-1)")
    score_breakdown: MatchScore = Field(..., description="Score breakdown")
    reasoning: MatchReasoning = Field(..., description="Match reasoning")
    matched_keywords: List[str] = Field(default_factory=list, description="Keywords that matched")
    missing_keywords: List[str] = Field(default_factory=list, description="Required keywords not found")


class MatchResult(BaseModel):
    """Container for all matches for a strategy."""
    strategy_id: str = Field(..., description="Strategy identifier")
    strategy_title: str = Field(..., description="Target job title from strategy")
    strategy_category: str = Field(..., description="Strategy category")
    
    total_jobs_analyzed: int = Field(..., description="Total jobs considered")
    total_matches: int = Field(..., description="Number of matching jobs")
    
    matches: List[JobMatch] = Field(default_factory=list, description="List of matches, sorted by score")
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class MatchReport(BaseModel):
    """Complete match report for all strategies."""
    report_id: str = Field(default_factory=lambda: datetime.utcnow().strftime("%Y%m%d_%H%M%S"))
    generated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    strategies_analyzed: int = Field(0, description="Number of strategies processed")
    jobs_analyzed: int = Field(0, description="Total jobs considered")
    total_matches: int = Field(0, description="Total matches across all strategies")
    
    results: List[MatchResult] = Field(default_factory=list, description="Match results per strategy")
    
    # Summary statistics
    score_distribution: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of matches by score range (excellent, good, moderate, poor)"
    )
