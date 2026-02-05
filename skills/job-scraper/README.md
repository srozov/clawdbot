# Job Scraper Skill

Scrape job postings from job boards using browser automation with parallel execution.

## Installation

```bash
cd skills/job-scraper
pip install -e ".[dev]"
```

## Configuration

Create a config file or use defaults:

```json
{
    "max_parallel_strategies": 3,
    "max_jobs_per_strategy": 50,
    "max_parallel_extractors": 5,
    "headless": true,
    "output_dir": "outputs/job_postings",
    "cache_dir": ".cache/job-scraper",
    "cache_ttl_hours": 24
}
```

## Usage

### Run with Strategy File

```bash
# Create a strategy file
cat > strategies.json
{
  "strategies": [
    {
      "job_title": "Senior Python Developer",
      "location": "Zürich",
      "keywords": ["Python", "Django"],
      "strategy_id": "python_dev",
      "max_jobs": 50
    },
    {
      "job_title": "ML Engineer",
      "location": "Zürich",
      "keywords": ["Machine Learning", "TensorFlow"],
      "strategy_id": "ml_engineer",
      "max_jobs": 30
    }
  ]
}

# Run scraping
job-scraper run strategies.json -o outputs/jobs -p 3
```

### Single Strategy

```bash
# Search for specific job title and location
job-scraper scrape-single "Python Developer" "Zürich" -o outputs/jobs --max-jobs 50
```

### Inline JSON

```bash
# Pass strategy as JSON string
job-scraper from-json '{"job_title": "DevOps Engineer", "location": "Berlin"}' -o outputs/jobs
```

### Check Status

```bash
# View scraping status and statistics
job-scraper status outputs/jobs
```

## Input Format

### Strategy File (JSON)

```json
{
  "strategies": [
    {
      "job_title": "Senior Software Engineer",
      "location": "Zürich",
      "keywords": ["Python", "AWS", "Docker"],
      "strategy_id": "se_senior",
      "category": "core_expertise",
      "max_jobs": 50
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
| `category` | No | Strategy category for tracking |
| `max_jobs` | No | Max jobs to collect (default: 50) |

## Output Format

### Job Files (`outputs/jobs/{strategy_id}/{job_id}.json`)

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

### Index File (`outputs/jobs/index.json`)

```json
{
  "total_jobs": 150,
  "duration_seconds": 287.5,
  "strategy_stats": [
    {
      "strategy_id": "python_dev",
      "jobs_found": 75,
      "jobs_extracted": 73,
      "failed": 2,
      "duration": 95.2
    }
  ]
}
```

## Performance

The scraper is designed for parallel execution:

- **Multiple strategies**: Run 3+ strategies in parallel
- **Parallel extraction**: Extract jobs concurrently per strategy
- **Target**: 100 jobs in ~5 minutes with 3 strategies

## Caching

Jobs are cached to avoid redundant API calls:
- Cache location: `.cache/job-scraper/{hash}.json`
- Default TTL: 24 hours
- Cache key based on (job_title, location, keywords)

## Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=job_scraper --cov-report=term-missing

# Lint
ruff check job_scraper/
```

## Integration with Other Skills

```python
# Use with career-strategy output
from job_scraper import JobScraper
from job_scraper.models import JobSearchConfig

# Load strategies from career-strategy output
with open("strategies/strategies.json") as f:
    strategies_data = json.load(f)

scraper = JobScraper()
results = await scraper.run_strategies(strategies_data["strategies"])
```
