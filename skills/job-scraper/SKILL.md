---
name: job-scraper
description: Scrape job postings from job boards (jobs.ch) using browser automation with parallel execution.
homepage: https://github.com/openclaw/job-application-agency
metadata: {"openclaw":{"emoji":"🔍","requires":{"env":["OPENROUTER_API_KEY","ANTHROPIC_API_KEY"]},"primaryEnv":"OPENROUTER_API_KEY"}}
---

# job-scraper

Scrape job postings from job boards using browser automation with parallel execution. Part of the OpenClaw job-application-agency workflow.

## Purpose

- **Input:** `inputs/strategies.json` - Job search strategies (from career-strategy skill)
- **Output:** `jobs/raw/{strategy_id}/{job_id}.json` - Scraped job postings
- **Purpose:** Execute job search strategies in parallel, scrape job listings, and extract detailed job information

## Quick Start

```bash
# Run the skill
python scripts/run.py

# Force re-scrape (bypass cache)
python scripts/run.py --force

# Run without incremental mode (re-scrape everything)
python scripts/run.py --no-incremental
```

## Input Format

### Strategies File (`inputs/strategies.json`)

```json
{
  "strategies": [
    {
      "job_title": "Senior Python Developer",
      "location": "Zürich",
      "keywords": ["Python", "Django", "PostgreSQL"],
      "strategy_id": "python_dev",
      "category": "core",
      "max_jobs": 50
    },
    {
      "job_title": "ML Engineer",
      "location": "Zürich",
      "keywords": ["Machine Learning", "TensorFlow"],
      "strategy_id": "ml_engineer",
      "category": "growth",
      "max_jobs": 30
    }
  ]
}
```

### Strategy Fields

| Field | Required | Description |
|-------|----------|-------------|
| `job_title` | Yes | Job title to search for |
| `location` | Yes | Geographic location |
| `keywords` | No | List of key skills/technologies |
| `strategy_id` | No | Unique identifier (auto-generated if missing) |
| `category` | No | Strategy category (core/adjacent/growth) |
| `max_jobs` | No | Max jobs to collect (default: 50) |

## Output Format

### Job Files (`jobs/raw/{strategy_id}/{job_id}.json`)

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "Senior Python Developer",
  "link": "https://www.jobs.ch/en/job/550e8400",
  "company": "TechCorp AG",
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
  "currency": "CHF",
  "source": "jobs.ch",
  "strategy_id": "python_dev"
}
```

### Index File (`jobs/raw/index.json`)

```json
{
  "total_jobs": 150,
  "total_skipped": 25,
  "duration_seconds": 287.5,
  "strategy_stats": [
    {
      "strategy_id": "python_dev",
      "jobs_found": 75,
      "jobs_extracted": 73,
      "failed": 2,
      "skipped": 10,
      "duration": 95.2
    }
  ]
}
```

## Performance

The scraper is designed for parallel execution:

| Setting | Default | Description |
|---------|---------|-------------|
| `max_parallel_strategies` | 3 | Strategies to run in parallel |
| `max_jobs_per_strategy` | 50 | Max jobs to collect per strategy |
| `max_parallel_extractors` | 5 | Concurrent job extractors |
| Target | 100 jobs / 5 min | With 3 strategies |

## Configuration

### Global Config (`config/global.json`)

```json
{
  "llm_model": "openrouter/google/gemini-2.5-flash-lite",
  "headless": true,
  "max_parallel_strategies": 3,
  "max_jobs_per_strategy": 50,
  "cache_ttl_hours": 24
}
```

### Skill Config (`config/job-scraper-config.json`)

```json
{
  "llm_model": "openrouter/google/gemini-2.5-flash-lite",
  "headless": true,
  "stealth": true,
  "max_parallel_strategies": 3,
  "max_jobs_per_strategy": 50,
  "max_parallel_extractors": 5,
  "request_delay_ms": 1000,
  "jobs_dir": "jobs/raw",
  "cache_dir": ".cache/job-scraper"
}
```

## Environment Variables

- `OPENROUTER_API_KEY` - OpenRouter API key (recommended, supports multiple providers)
- `ANTHROPIC_API_KEY` - Anthropic API key for Claude (fallback)
- `OPENAI_API_KEY` - OpenAI API key for GPT-4 (fallback)

## Caching

Jobs are cached to avoid redundant scraping:
- Cache location: `.cache/job-scraper/{hash}.json`
- Default TTL: 24 hours
- Cache key based on (job_title, location, keywords, link)

Clear cache:
```bash
rm -rf .cache/job-scraper/
```

## Directory Structure

```
job-scraper/
├── scripts/
│   └── run.py              # Skill entry point
├── job_scraper/
│   ├── __init__.py
│   ├── cli.py              # CLI commands
│   ├── scraper.py          # Main scraping logic
│   └── models.py           # Pydantic models
├── inputs/
│   └── strategies.json     # Input from career-strategy
├── jobs/
│   └── raw/                # Scraped job postings
│       ├── {strategy_id}/
│       │   └── {job_id}.json
│       └── index.json
├── .cache/
│   └── job-scraper/        # Cached responses
├── config/
│   └── job-scraper-config.json
├── tests/
├── SKILL.md
└── README.md
```

## Integration

This skill is designed for the OpenClaw job-application-agency workflow:

```python
# In orchestrator.py
from job_scraper.scraper import JobsCHScraper
from job_scraper.models import GlobalConfig, JobSearchStrategy

# Load strategies from career-strategy output
with open("strategies/strategies.json") as f:
    strategies_data = json.load(f)

config = GlobalConfig()
scraper = JobsCHScraper(config=config)

results = await scraper.run_strategies([
    JobSearchStrategy(**s) for s in strategies_data["strategies"]
])
```

**Workflow order:**
1. `career-strategy` → generates `strategies/strategies.json`
2. `job-scraper` → reads strategies, scrapes jobs → `jobs/raw/`
3. `job-matcher` → matches jobs against resume
4. `cover-letter-gen` → generates cover letters
5. `notion-tracker` → syncs to Notion

## CLI Commands

The skill provides a CLI via `job_scraper.cli`:

```bash
# Run with strategy file
job-scraper run strategies.json -o outputs/jobs -p 3

# Scrape single strategy
job-scraper scrape-single "Python Developer" "Zürich" -o outputs/jobs

# From inline JSON
job-scraper from-json '{"job_title": "DevOps", "location": "Berlin"}' -o outputs/jobs

# Check status
job-scraper status outputs/jobs
```

## Development

```bash
# Install dependencies
pip install -e ../job-scraper[dev]

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=job_scraper --cov-report=term-missing

# Lint
ruff check job_scraper/

# Run CLI directly
python -m job_scraper.cli run strategies.json -o jobs/raw
```

## License

MIT
