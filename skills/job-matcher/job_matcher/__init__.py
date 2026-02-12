"""Job matcher skill for matching jobs to career strategies."""

__version__ = "0.1.0"

from .matcher import JobMatcher
from .models import JobMatch, MatchResult, MatchReport

__all__ = ["JobMatcher", "JobMatch", "MatchResult", "MatchReport"]
