"""
Cover Letter Generator Skill

Generate tailored cover letters and customized CVs for job applications.
"""

__version__ = "1.0.0"

from .models import (
    CoverLetterConfig,
    CoverLetterResult,
    ApplicationMetadata,
    ApplicationIndex,
    MatchInfo,
    CompanyResearch,
)
from .generator import CoverLetterGenerator
from .cv_customizer import CVCustomizer
from .research import CompanyResearcher

__all__ = [
    "CoverLetterGenerator",
    "CVCustomizer",
    "CompanyResearcher",
    "CoverLetterConfig",
    "CoverLetterResult",
    "ApplicationMetadata",
    "ApplicationIndex",
    "MatchInfo",
    "CompanyResearch",
]
