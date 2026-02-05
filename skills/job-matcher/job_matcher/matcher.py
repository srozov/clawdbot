"""Core job matching logic."""

import re
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from Levenshtein import distance as levenshtein_distance

from .models import (
    MatchResult,
    MatchReport,
    JobMatch,
    MatchScore,
    MatchReasoning,
)


class JobMatcher:
    """Match jobs to career strategies with scoring and reasoning."""
    
    # Seniority mapping for comparison
    SENIORITY_LEVELS = {
        "junior": 1,
        "mid-level": 2,
        "senior": 3,
        "lead": 4,
        "executive": 5,
    }
    
    # Remote work compatibility
    REMOTE_COMPATIBILITY = {
        ("remote", "remote"): 1.0,
        ("remote", "hybrid"): 0.7,
        ("remote", "onsite"): 0.3,
        ("remote", "on-site"): 0.3,
        ("hybrid", "remote"): 0.7,
        ("hybrid", "hybrid"): 1.0,
        ("hybrid", "onsite"): 0.7,
        ("hybrid", "on-site"): 0.7,
        ("onsite", "remote"): 0.3,
        ("onsite", "hybrid"): 0.7,
        ("onsite", "onsite"): 1.0,
        ("onsite", "on-site"): 1.0,
        ("on-site", "remote"): 0.3,
        ("on-site", "hybrid"): 0.7,
        ("on-site", "onsite"): 0.7,
        ("on-site", "on-site"): 1.0,
        ("unknown", "unknown"): 0.5,
    }
    
    def _get_remote_compatibility(self, job_remote: str, strategy_remote: str) -> float:
        """Get remote work compatibility score with fallback."""
        key = (job_remote, strategy_remote)
        if key in self.REMOTE_COMPATIBILITY:
            return self.REMOTE_COMPATIBILITY[key]
        # Fallback for unknown values
        if "unknown" in key:
            return 0.5
        return 0.3  # Default for mismatched known values
    
    def __init__(
        self,
        keyword_weight: float = 0.35,
        location_weight: float = 0.20,
        seniority_weight: float = 0.20,
        remote_weight: float = 0.10,
        salary_weight: float = 0.15,
        min_score: float = 0.3,
    ):
        """Initialize the job matcher.
        
        Args:
            keyword_weight: Weight for keyword matching (default: 0.35)
            location_weight: Weight for location matching (default: 0.20)
            seniority_weight: Weight for seniority matching (default: 0.20)
            remote_weight: Weight for remote work matching (default: 0.10)
            salary_weight: Weight for salary matching (default: 0.15)
            min_score: Minimum score to include a match (default: 0.3)
        """
        self.weights = {
            "keyword": keyword_weight,
            "location": location_weight,
            "seniority": seniority_weight,
            "remote": remote_weight,
            "salary": salary_weight,
        }
        self.min_score = min_score
    
    def load_strategies(self, strategies_path: str) -> Dict[str, dict]:
        """Load strategies from JSON file or directory.
        
        Args:
            strategies_path: Path to strategy JSON file or directory containing JSON files
            
        Returns:
            Dictionary mapping strategy_id to strategy data
        """
        strategies = {}
        path = Path(strategies_path)
        
        if path.is_file() and path.suffix == ".json":
            with open(path) as f:
                data = json.load(f)
                for strategy in data.get("strategies", []):
                    strategies[strategy["strategy_id"]] = strategy
        elif path.is_dir():
            for json_file in path.glob("*.json"):
                with open(json_file) as f:
                    data = json.load(f)
                    for strategy in data.get("strategies", []):
                        strategies[strategy["strategy_id"]] = strategy
        else:
            raise ValueError(f"Invalid strategies path: {strategies_path}")
        
        return strategies
    
    def load_jobs(self, jobs_path: str) -> List[dict]:
        """Load job postings from JSON file or directory.
        
        Args:
            jobs_path: Path to job JSON file or directory containing JSON files
            
        Returns:
            List of job posting dictionaries
        """
        jobs = []
        path = Path(jobs_path)
        
        if path.is_file() and path.suffix == ".json":
            with open(path) as f:
                data = json.load(f)
                jobs.append(data)
        elif path.is_dir():
            for json_file in path.glob("*.json"):
                with open(json_file) as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        jobs.extend(data)
                    else:
                        jobs.append(data)
        else:
            raise ValueError(f"Invalid jobs path: {jobs_path}")
        
        return jobs
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (lowercase, remove special chars)."""
        return re.sub(r"[^a-z0-9\s]", " ", text.lower())
    
    def _calculate_keyword_score(
        self, 
        job: dict, 
        strategy: dict
    ) -> Tuple[float, List[str], List[str]]:
        """Calculate keyword matching score.
        
        Returns:
            Tuple of (score, matched_keywords, missing_keywords)
        """
        required = strategy.get("required_keywords", strategy.get("keywords", []))
        excluded = strategy.get("excluded_keywords", [])
        
        # Combine all text fields for searching
        job_text = self._normalize_text(job.get("description", ""))
        job_text += " " + self._normalize_text(job.get("title", ""))
        job_text += " " + self._normalize_text(job.get("profile", ""))
        job_text += " " + self._normalize_text(job.get("tasks", ""))
        
        matched = []
        missing = []
        
        for keyword in required:
            normalized_kw = self._normalize_text(keyword)
            # Also check for variations (e.g., "machine learning" vs "ml")
            if normalized_kw in job_text or keyword.lower() in job_text:
                matched.append(keyword)
            else:
                missing.append(keyword)
        
        # Check for excluded keywords
        has_excluded = any(
            self._normalize_text(kw) in job_text or kw.lower() in job_text
            for kw in excluded if kw
        )
        
        if has_excluded:
            return 0.0, [], []
        
        if not required:
            return 1.0, [], []
        
        score = len(matched) / len(required)
        return score, matched, missing
    
    def _calculate_location_score(
        self, 
        job: dict, 
        strategy: dict
    ) -> float:
        """Calculate location matching score.
        
        Returns:
            Location match score (0-1)
        """
        job_location = job.get("location", "").lower().strip()
        strategy_location = strategy.get("location", "").lower().strip()
        
        if not strategy_location:
            return 1.0  # No location preference
        
        if not job_location:
            return 0.5  # Unknown location
        
        # Exact match
        if job_location == strategy_location:
            return 1.0
        
        # Fuzzy match using Levenshtein distance
        max_len = max(len(job_location), len(strategy_location))
        if max_len > 0:
            distance = levenshtein_distance(job_location, strategy_location)
            similarity = 1 - (distance / max_len)
            if similarity >= 0.7:
                return similarity
        
        # Check if strategy location is contained in job location (e.g., "Zürich" in "Zürich, Switzerland")
        if strategy_location in job_location:
            return 0.9
        
        # Check if job location contains key parts of strategy location
        strategy_parts = strategy_location.split()
        if any(part in job_location for part in strategy_parts if len(part) > 3):
            return 0.8
        
        return 0.3  # Different locations
    
    def _calculate_seniority_score(
        self, 
        job: dict, 
        strategy: dict
    ) -> float:
        """Calculate seniority level match score.
        
        Returns:
            Seniority match score (0-1)
        """
        job_seniority = job.get("seniority", "unknown").lower().replace("-", " ")
        strategy_range = strategy.get("seniority_range", [])
        
        if not strategy_range:
            return 0.5  # No seniority preference
        
        # Normalize job seniority
        job_level = self.SENIORITY_LEVELS.get(job_seniority, 2)  # Default to mid-level
        
        # Check if job seniority is within strategy's range
        min_level = min(self.SENIORITY_LEVELS.get(s.lower(), 2) for s in strategy_range)
        max_level = max(self.SENIORITY_LEVELS.get(s.lower(), 2) for s in strategy_range)
        
        if min_level <= job_level <= max_level:
            return 1.0
        elif job_level < min_level:
            # Job is too junior - penalize based on how far off
            return max(0.0, 1.0 - (min_level - job_level) * 0.3)
        else:
            # Job is too senior - less penalty (might be okay)
            return max(0.0, 1.0 - (job_level - max_level) * 0.2)
    
    def _calculate_remote_score(
        self, 
        job: dict, 
        strategy: dict
    ) -> float:
        """Calculate remote work preference match score.
        
        Returns:
            Remote work match score (0-1)
        """
        job_remote = job.get("remote", "unknown").lower().replace("-", "")
        strategy_remote = strategy.get("remote_preference")
        
        if not strategy_remote:
            return 0.5  # No preference
        
        strategy_remote = strategy_remote.lower().replace("-", "")
        
        # Use compatibility helper
        return self._get_remote_compatibility(job_remote, strategy_remote)
    
    def _calculate_salary_score(
        self, 
        job: dict, 
        strategy: dict
    ) -> float:
        """Calculate salary expectation match score.
        
        Returns:
            Salary match score (0-1)
        """
        job_min = job.get("min_salary")
        strategy_min = strategy.get("salary_min")
        
        if not job_min or not strategy_min:
            return 0.5  # Can't compare
        
        if job_min >= strategy_min:
            return 1.0  # Meets or exceeds minimum
        
        # Below minimum - score based on how far below
        ratio = job_min / strategy_min
        return max(0.0, ratio - 0.2)  # Give some buffer
    
    def _generate_keyword_reasoning(
        self,
        matched: List[str],
        missing: List[str],
        score: float
    ) -> str:
        """Generate human-readable keyword matching reasoning."""
        if not matched and not missing:
            return "No keyword preferences specified."
        
        if score == 0 and missing:
            return f"All required keywords missing: {', '.join(missing)}"
        
        if score == 1:
            return f"All {len(matched)} required keywords found: {', '.join(matched)}"
        
        parts = []
        if matched:
            parts.append(f"Matched: {', '.join(matched)}")
        if missing:
            parts.append(f"Missing: {', '.join(missing)}")
        
        return "; ".join(parts)
    
    def _generate_location_reasoning(
        self,
        job_location: str,
        strategy_location: str,
        score: float
    ) -> str:
        """Generate human-readable location matching reasoning."""
        if not strategy_location:
            return "No location preference specified."
        
        if not job_location:
            return "Job location not specified."
        
        if score >= 0.9:
            return f"Location matches: {job_location}"
        elif score >= 0.6:
            return f"Similar location: {job_location} (target: {strategy_location})"
        elif score >= 0.3:
            return f"Different location: {job_location} (target: {strategy_location})"
        else:
            return f"Location mismatch: {job_location} vs {strategy_location}"
    
    def _generate_seniority_reasoning(
        self,
        job_seniority: str,
        strategy_range: List[str],
        score: float
    ) -> str:
        """Generate human-readable seniority matching reasoning."""
        if not strategy_range:
            return "No seniority preference specified."
        
        if score >= 0.9:
            return f"Seniority matches preference ({job_seniority})"
        elif score >= 0.6:
            return f"Seniority partially aligns ({job_seniority})"
        else:
            return f"Seniority may not align ({job_seniority} vs {', '.join(strategy_range)})"
    
    def _generate_remote_reasoning(
        self,
        job_remote: str,
        strategy_remote: Optional[str],
        score: float
    ) -> str:
        """Generate human-readable remote work matching reasoning."""
        if not strategy_remote:
            return "No remote work preference specified."
        
        if score >= 0.9:
            return f"Remote option matches preference ({job_remote})"
        elif score >= 0.6:
            return f"Remote option partially compatible ({job_remote} vs {strategy_remote})"
        else:
            return f"Remote option differs from preference ({job_remote} vs {strategy_remote})"
    
    def _generate_salary_reasoning(
        self,
        job_salary: Optional[str],
        job_min: Optional[float],
        strategy_min: Optional[int],
        score: float
    ) -> str:
        """Generate human-readable salary matching reasoning."""
        if not job_min and not strategy_min:
            return "No salary information available."
        
        if not job_min:
            return "Job salary not specified."
        
        if not strategy_min:
            return f"Job salary: CHF {job_min:,.0f}+"
        
        if score >= 0.9:
            return f"Meets salary expectation (CHF {job_min:,.0f}+ ≥ CHF {strategy_min:,})"
        elif score >= 0.6:
            return f"Below target salary (CHF {job_min:,.0f}+ vs CHF {strategy_min:,})"
        else:
            return f"Significantly below target (CHF {job_min:,.0f}+ vs CHF {strategy_min:,})"
    
    def _score_job_for_strategy(
        self,
        job: dict,
        strategy: dict
    ) -> Optional[JobMatch]:
        """Score a single job against a strategy.
        
        Returns:
            JobMatch if score meets threshold, None otherwise
        """
        # Calculate individual scores
        keyword_score, matched_kw, missing_kw = self._calculate_keyword_score(job, strategy)
        location_score = self._calculate_location_score(job, strategy)
        seniority_score = self._calculate_seniority_score(job, strategy)
        remote_score = self._calculate_remote_score(job, strategy)
        salary_score = self._calculate_salary_score(job, strategy)
        
        # Calculate weighted overall score
        overall_score = (
            keyword_score * self.weights["keyword"] +
            location_score * self.weights["location"] +
            seniority_score * self.weights["seniority"] +
            remote_score * self.weights["remote"] +
            salary_score * self.weights["salary"]
        )
        
        # Skip if below threshold
        if overall_score < self.min_score:
            return None
        
        # Build reasoning
        reasoning = MatchReasoning(
            keyword_match=self._generate_keyword_reasoning(matched_kw, missing_kw, keyword_score),
            location_match=self._generate_location_reasoning(
                job.get("location", ""), strategy.get("location", ""), location_score
            ),
            seniority_match=self._generate_seniority_reasoning(
                job.get("seniority", ""), strategy.get("seniority_range", []), seniority_score
            ),
            remote_match=self._generate_remote_reasoning(
                job.get("remote", ""), strategy.get("remote_preference"), remote_score
            ),
            salary_match=self._generate_salary_reasoning(
                job.get("raw_salary"), job.get("min_salary"), strategy.get("salary_min"), salary_score
            ),
            strengths=self._get_match_strengths(
                keyword_score, location_score, seniority_score, remote_score, salary_score
            ),
            concerns=self._get_match_concerns(
                keyword_score, location_score, seniority_score, remote_score, salary_score, missing_kw
            ),
        )
        
        return JobMatch(
            job_id=job.get("job_id", "unknown"),
            strategy_id=strategy.get("strategy_id", "unknown"),
            job_title=job.get("title", "Unknown"),
            job_link=job.get("link", ""),
            company=job.get("company", "Unknown"),
            job_location=job.get("location", "Unknown"),
            description=job.get("description", "")[:500],  # Truncate for readability
            score=overall_score,
            score_breakdown=MatchScore(
                keyword_score=keyword_score,
                location_score=location_score,
                seniority_score=seniority_score,
                remote_score=remote_score,
                salary_score=salary_score,
                overall_score=overall_score,
            ),
            reasoning=reasoning,
            matched_keywords=matched_kw,
            missing_keywords=missing_kw,
        )
    
    def _get_match_strengths(
        self,
        keyword: float,
        location: float,
        seniority: float,
        remote: float,
        salary: float
    ) -> List[str]:
        """Identify match strengths."""
        strengths = []
        if keyword >= 0.8:
            strengths.append("Strong keyword match")
        elif keyword >= 0.5:
            strengths.append("Partial keyword match")
        if location >= 0.9:
            strengths.append("Perfect location match")
        elif location >= 0.7:
            strengths.append("Good location match")
        if seniority >= 0.8:
            strengths.append("Seniority level aligns well")
        if remote >= 0.9:
            strengths.append("Remote work option matches preference")
        if salary >= 0.8:
            strengths.append("Salary meets expectations")
        return strengths
    
    def _get_match_concerns(
        self,
        keyword: float,
        location: float,
        seniority: float,
        remote: float,
        salary: float,
        missing_kw: List[str]
    ) -> List[str]:
        """Identify match concerns."""
        concerns = []
        if keyword < 0.5:
            concerns.append("Limited keyword overlap")
        if missing_kw:
            concerns.append(f"Missing required keywords: {', '.join(missing_kw[:3])}")
        if location < 0.5:
            concerns.append("Location mismatch")
        if seniority < 0.5:
            concerns.append("Seniority may not align")
        if remote < 0.5:
            concerns.append("Remote work option differs from preference")
        if salary < 0.5:
            concerns.append("Salary below target")
        return concerns
    
    def match_jobs_to_strategy(
        self,
        jobs: List[dict],
        strategy: dict,
        max_matches: int = 20
    ) -> MatchResult:
        """Match all jobs against a single strategy.
        
        Args:
            jobs: List of job posting dictionaries
            strategy: Strategy to match against
            max_matches: Maximum number of matches to return
            
        Returns:
            MatchResult with all matching jobs
        """
        matches = []
        
        for job in jobs:
            match = self._score_job_for_strategy(job, strategy)
            if match:
                matches.append(match)
        
        # Sort by score descending
        matches.sort(key=lambda m: m.score, reverse=True)
        
        # Limit to max_matches
        matches = matches[:max_matches]
        
        return MatchResult(
            strategy_id=strategy.get("strategy_id", "unknown"),
            strategy_title=strategy.get("job_title", "Unknown"),
            strategy_category=strategy.get("category", "unknown"),
            total_jobs_analyzed=len(jobs),
            total_matches=len(matches),
            matches=matches,
        )
    
    def match_all(
        self,
        strategies_path: str,
        jobs_path: str,
        output_path: Optional[str] = None,
        max_matches_per_strategy: int = 20
    ) -> MatchReport:
        """Match all jobs against all strategies.
        
        Args:
            strategies_path: Path to strategy files
            jobs_path: Path to job files
            output_path: Optional path to save results
            max_matches_per_strategy: Maximum matches per strategy
            
        Returns:
            MatchReport with all match results
        """
        # Load data
        strategies = self.load_strategies(strategies_path)
        jobs = self.load_jobs(jobs_path)
        
        # Match each strategy
        results = []
        for strategy_id, strategy in strategies.items():
            result = self.match_jobs_to_strategy(
                jobs=jobs,
                strategy=strategy,
                max_matches=max_matches_per_strategy
            )
            results.append(result)
        
        # Calculate summary statistics
        total_matches = sum(len(r.matches) for r in results)
        score_dist = {"excellent": 0, "good": 0, "moderate": 0, "poor": 0}
        
        for result in results:
            for match in result.matches:
                if match.score >= 0.8:
                    score_dist["excellent"] += 1
                elif match.score >= 0.6:
                    score_dist["good"] += 1
                elif match.score >= 0.4:
                    score_dist["moderate"] += 1
                else:
                    score_dist["poor"] += 1
        
        report = MatchReport(
            strategies_analyzed=len(strategies),
            jobs_analyzed=len(jobs),
            total_matches=total_matches,
            results=results,
            score_distribution=score_dist,
        )
        
        # Save if output path provided
        if output_path:
            self.save_report(report, output_path)
        
        return report
    
    def save_report(self, report: MatchReport, output_path: str) -> None:
        """Save match report to JSON file.
        
        Args:
            report: MatchReport to save
            output_path: Path for output file
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w") as f:
            f.write(report.model_dump_json(indent=2))
        
        print(f"Match report saved to: {output_path}")
