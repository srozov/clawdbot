# Job Matcher Skill

Match job postings to career strategies with intelligent scoring and ranking.

## Overview

The Job Matcher skill analyzes job postings against your career strategies and generates ranked matches with detailed scoring and reasoning. It evaluates multiple factors including keyword matching, location compatibility, seniority alignment, remote work preferences, and salary expectations.

## Installation

```bash
cd skills/job-matcher
pip install -e ".[dev]"
```

## Quick Start

```bash
# Run matching with default paths
job-matcher run

# Or with custom paths
job-matcher run --strategies career-strategy/strategies/ --jobs job-scraper/output/ --output matches/
```

## Usage

### Command Line Interface

```bash
job-matcher [command] [options]
```

#### Commands

- `run` - Run job matching process
- `validate` - Validate input files without matching
- `stats` - Show statistics from a previous match report

#### Run Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--strategies` | `-s` | `strategies/` | Path to strategy JSON files |
| `--jobs` | `-j` | `job-scraper/output/` | Path to job JSON files |
| `--output` | `-o` | `matches/` | Output directory for results |
| `--max-matches` | `-m` | `20` | Max matches per strategy |
| `--min-score` | `-t` | `0.3` | Minimum score threshold (0-1) |
| `--keyword-weight` | - | `0.35` | Keyword matching weight |
| `--location-weight` | - | `0.20` | Location matching weight |
| `--seniority-weight` | - | `0.20` | Seniority matching weight |
| `--remote-weight` | - | `0.10` | Remote work matching weight |
| `--salary-weight` | - | `0.15` | Salary matching weight |
| `--quiet` | `-q` | False | Suppress detailed output |

#### Examples

```bash
# Basic usage
job-matcher run

# High keyword emphasis
job-matcher run --keyword-weight 0.5 --salary-weight 0.1

# Only show good matches
job-matcher run --min-score 0.6 --max-matches 10

# Validate inputs first
job-matcher validate --strategies strategies.json --jobs output/jobs
```

### Python API

```python
from job_matcher import JobMatcher

# Create matcher with custom weights
matcher = JobMatcher(
    keyword_weight=0.40,
    location_weight=0.20,
    seniority_weight=0.20,
    remote_weight=0.10,
    salary_weight=0.10,
    min_score=0.3,
)

# Run matching
report = matcher.match_all(
    strategies_path="strategies/",
    jobs_path="job-scraper/output/",
    output_path="matches/latest.json",
    max_matches_per_strategy=20,
)

# Access results
for result in report.results:
    print(f"\n### {result.strategy_title} ({result.strategy_category})")
    print(f"Found {result.total_matches} matches out of {result.total_jobs_analyzed} jobs")
    
    for match in result.matches[:5]:  # Top 5
        print(f"\n  Score: {match.score:.2f}")
        print(f"  Title: {match.job_title}")
        print(f"  Company: {match.company}")
        print(f"  Matched keywords: {', '.join(match.matched_keywords)}")
        print(f"  Reasoning: {match.reasoning.keyword_match}")
```

## Input Format

### Strategy Files

Load from `strategies/*.json` or a single file:

```json
{
  "strategies": [
    {
      "strategy_id": "python_senior",
      "job_title": "Senior Python Developer",
      "location": "Zürich",
      "keywords": ["Python", "Django", "PostgreSQL"],
      "category": "core_expertise",
      "required_keywords": ["Python", "Django"],
      "excluded_keywords": ["React", "Frontend"],
      "seniority_range": ["mid-level", "senior"],
      "remote_preference": "hybrid",
      "salary_min": 120000,
      "match_threshold": 0.6
    }
  ]
}
```

### Job Files

Jobs are loaded from `job-scraper/output/` (typically `strategy_id/job_id.json`):

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Senior Python Developer",
  "link": "https://jobs.ch/company/job/123",
  "company": "TechCorp",
  "location": "Zürich",
  "workload": "full-time",
  "publication_date": "2025-05-10T00:00:00Z",
  "description": "We are looking for a senior Python developer...",
  "tasks": "- Develop backend services\n- Mentor junior developers",
  "profile": "- 5+ years Python experience\n- AWS expertise",
  "seniority": "senior",
  "employment_type": "permanent",
  "remote": "hybrid",
  "raw_salary": "CHF 120,000 - 150,000",
  "min_salary": 120000,
  "max_salary": 150000,
  "currency": "CHF"
}
```

## Output Format

### Match Report (`matches/*.json`)

```json
{
  "report_id": "20250510_143022",
  "generated_at": "2025-05-10T14:30:22Z",
  "strategies_analyzed": 3,
  "jobs_analyzed": 150,
  "total_matches": 45,
  "score_distribution": {
    "excellent": 8,
    "good": 15,
    "moderate": 18,
    "poor": 4
  },
  "results": [
    {
      "strategy_id": "python_senior",
      "strategy_title": "Senior Python Developer",
      "strategy_category": "core_expertise",
      "total_jobs_analyzed": 150,
      "total_matches": 20,
      "matches": [
        {
          "job_id": "550e8400-e29b-41d4-a716-446655440000",
          "strategy_id": "python_senior",
          "job_title": "Senior Python Developer",
          "job_link": "https://jobs.ch/company/job/123",
          "company": "TechCorp",
          "job_location": "Zürich",
          "description": "We are looking for a senior Python developer...",
          "score": 0.85,
          "score_breakdown": {
            "keyword_score": 0.90,
            "location_score": 1.0,
            "seniority_score": 0.80,
            "remote_score": 1.0,
            "salary_score": 0.75,
            "overall_score": 0.85
          },
          "reasoning": {
            "keyword_match": "Matched: Python, Django, PostgreSQL",
            "location_match": "Location matches: Zürich",
            "seniority_match": "Seniority aligns (senior)",
            "remote_match": "Remote option matches (hybrid)",
            "salary_match": "Meets salary expectation",
            "strengths": ["Strong keyword match", "Perfect location match"],
            "concerns": []
          },
          "matched_keywords": ["Python", "Django", "PostgreSQL"],
          "missing_keywords": []
        }
      ]
    }
  ]
}
```

## Scoring Algorithm

The matcher evaluates jobs across 5 dimensions:

| Dimension | Default Weight | Description |
|-----------|---------------|-------------|
| **Keywords** | 35% | Match required keywords in job description |
| **Location** | 20% | Geographic compatibility (exact → fuzzy) |
| **Seniority** | 20% | Level alignment (junior → executive) |
| **Remote** | 10% | Remote work option compatibility |
| **Salary** | 15% | Salary range vs. expectations |

### Score Ranges

- **Excellent (≥0.8)**: Strong match across most dimensions
- **Good (0.6-0.79)**: Solid match with minor gaps
- **Moderate (0.4-0.59)**: Partial match, may need review
- **Poor (<0.4)**: Weak match, unlikely to be relevant

## Integration with Career Coach

```python
# Complete workflow
from career_strategy import ResumeAnalyzer
from job_scraper import JobScraper
from job_matcher import JobMatcher

# 1. Generate strategies from resume
analyzer = ResumeAnalyzer()
strategies = analyzer.analyze("resume.md", "strategies/")

# 2. Scrape jobs for each strategy
scraper = JobScraper()
scraper.run_strategies("strategies/strategies.json", "job-scraper/output/")

# 3. Match jobs to strategies
matcher = JobMatcher()
report = matcher.match_all(
    "strategies/",
    "job-scraper/output/",
    "matches/",
    max_matches_per_strategy=10
)

# 4. Review top matches
for result in report.results:
    print(f"\n=== {result.strategy_title} ===")
    for match in result.matches[:3]:
        print(f"{match.company}: {match.job_title} (Score: {match.score:.2f})")
```

## Configuration

No external configuration required. All settings can be passed via CLI arguments or Python API.

## Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=job_matcher --cov-report=term-missing

# Lint
ruff check job_matcher/
```

## Dependencies

- **pydantic** - Data validation and settings
- **levenshtein** - Fuzzy string matching
- **python-Levenshtein** (optional, for faster matching)

## License

MIT
