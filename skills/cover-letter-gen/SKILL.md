# Cover Letter Generation Skill

## Overview

The **cover-letter-gen** skill generates tailored cover letters and customized CVs for high-scoring job matches from the resume-matcher skill.

## Skill Metadata

| Property | Value |
|----------|-------|
| **Name** | `cover-letter-gen` |
| **Version** | `1.0.0` |
| **Category** | job-application |
| **Author** | OpenClaw |
| **Dependencies** | click, pydantic, openai, aiofiles, httpx |
| **Output Type** | File-based (Markdown, JSON) |

## Description

This skill takes high-scoring job matches (score >= 0.6) and generates:
- **Personalized cover letters** tailored to each job
- **Customized CVs** highlighting relevant experience
- **Application metadata** with generation context

### Features

- **LLM-powered generation**: Uses advanced language models for compelling, personalized content
- **Company research integration**: Optional web search for company context and insights
- **Adaptive templates**: Single adaptive template that adjusts tone and emphasis based on job context
- **MD5 caching**: Avoids redundant work by caching results by (job_id, resume_hash)
- **Parallel processing**: Generate multiple applications concurrently

## Usage

### CLI Commands

#### `run`

Generate cover letters for all viable matches.

```bash
cover-letter-gen run --matches <path> --resume <path> --output <path>
```

**Options:**
- `--matches, -m`: Path to viable matches JSON (required)
- `--resume, -r`: Path to resume markdown (required)
- `--output, -o`: Output directory for applications (default: `applications/`)
- `--enable-research`: Enable company research via web search
- `--force, -f`: Force regeneration, skip cache
- `--config, -c`: Path to skill config file

**Example:**
```bash
cover-letter-gen run -m matches/viable.json -r inputs/resume.md -o applications/ --enable-research
```

#### `generate`

Generate a single cover letter.

```bash
cover-letter-gen generate --job <path> --match <path> --resume <path>
```

**Options:**
- `--job, -j`: Path to job posting JSON (required)
- `--match, -M`: Path to match result JSON (required)
- `--resume, -r`: Path to resume markdown (required)
- `--output, -o`: Output directory for single application
- `--enable-research`: Enable company research
- `--config, -c`: Path to skill config file

**Example:**
```bash
cover-letter-gen generate -j jobs/raw/job-123.json -M matches/match-123.json -r inputs/resume.md
```

## Input Schema

### Matches File (`matches/viable.json`)

```json
{
  "matches": [
    {
      "job_id": "550e8400-e29b-41d4-a716-446655440000",
      "company": "Google",
      "title": "Senior Python Developer",
      "location": "Zürich",
      "match_score": 0.85,
      "match_reasoning": "...",
      "matched_keywords": ["Python", "backend", "API"],
      "missing_keywords": ["Kubernetes", "GraphQL"],
      "salary_estimate": {"min": 120000, "max": 150000, "currency": "CHF"}
    }
  ]
}
```

### Resume File (`inputs/resume.md`)

Markdown with semantic headers:
```markdown
## Summary
...
## Experience
...
## Skills
...
## Education
...
```

## Output Schema

### Application Directory Structure

```
applications/
├── {company}_{title}/
│   ├── cover_letter.md
│   ├── cv.md
│   └── metadata.json
└── index.json
```

### Cover Letter (`cover_letter.md`)

```markdown
# Cover Letter

Dear Hiring Manager,

[Personalized content based on job and company research]

Best regards,
[Your Name]
```

### Metadata (`metadata.json`)

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "company": "Google",
  "title": "Senior Python Developer",
  "match_score": 0.85,
  "generated_at": "2025-05-10T16:00:00Z",
  "company_research": "...",
  "resume_hash": "abc123...",
  "cached": false
}
```

### Index (`index.json`)

```json
{
  "applications": [
    {
      "company": "Google",
      "title": "Senior Python Developer",
      "output_dir": "applications/Google_Senior_Python_Developer",
      "match_score": 0.85,
      "generated_at": "2025-05-10T16:00:00Z"
    }
  ],
  "total": 1,
  "generated": 1,
  "cached": 0,
  "failed": 0
}
```

## Configuration

### Global Config (`config/global.json`)

```json
{
  "llm_model": "anthropic/claude-sonnet-4",
  "logging": {
    "level": "INFO",
    "format": "json"
  },
  "cache_ttl_days": 7,
  "parallel_limit": 10
}
```

### Skill Config (`config/cover-letter-config.json`)

```json
{
  "llm_model": "anthropic/claude-sonnet-4",
  "style": "adaptive",
  "enable_company_research": true,
  "company_cache_ttl_days": 7,
  "max_length_words": 350,
  "min_match_score": 0.6
}
```

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    cover-letter-gen CLI                          │
│                    (cli.py / run.py)                            │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        ┌──────────┐  ┌───────────┐  ┌─────────────┐
        │Generator │  │CV_Customizer│ │ Researcher │
        │(generator)│  │(cv_customizer)│ │(research)│
        └────┬─────┘  └─────┬─────┘  └──────┬──────┘
             │              │               │
             └──────────────┼───────────────┘
                            ▼
                  ┌───────────────────┐
                  │  LLM API          │
                  │(OpenAI/Anthropic) │
                  └───────────────────┘
                            │
                            ▼
                  ┌───────────────────┐
                  │  Output Writer    │
                  │  (Markdown/JSON)  │
                  └───────────────────┘
```

### Data Flow

1. **Load Inputs**: Read viable matches, resume, and job postings
2. **Check Cache**: MD5 hash of (job_id, resume_hash) for each match
3. **Parallel Generation**: For uncached matches:
   - Optionally research company via web search
   - Generate cover letter via LLM
   - Customize CV via LLM
4. **Write Outputs**: Save files to application directory
5. **Update Index**: Write applications/index.json

## Caching

### Cache Key

```python
cache_key = hashlib.md5(
    f"{job_id}:{resume_hash}".encode()
).hexdigest()
```

### Cache Location

```
.cache/cover-letter-gen/
└── {job_id}_{resume_hash}.json
```

### Cache Contents

```json
{
  "cover_letter": "...",
  "cv": "...",
  "metadata": {...},
  "cached_at": "2025-05-10T16:00:00Z"
}
```

### Cache Invalidation

- **Manual**: `rm -rf .cache/cover-letter-gen/`
- **Automatic**: TTL-based (default: 7 days)

## Dependencies

### Runtime

- `click` - CLI framework
- `pydantic` - Data validation
- `openai` - LLM API client
- `aiofiles` - Async file I/O
- `httpx` - HTTP client for web search
- `markdown` - Markdown processing

### Development

- `pytest` - Testing framework
- `black` - Code formatting
- `ruff` - Linting

## Error Handling

### Validation Errors

```json
{
  "error": "VALIDATION_ERROR",
  "message": "Missing required field: job_id",
  "details": {...}
}
```

### LLM Errors

```json
{
  "error": "LLM_ERROR",
  "message": "API request failed",
  "retryable": true
}
```

### File Errors

```json
{
  "error": "FILE_ERROR",
  "message": "Could not write to output directory",
  "path": "applications/..."
}
```

## Progress Tracking

The skill emits JSON progress events to stdout:

```json
{"type": "progress", "current": 1, "total": 5, "company": "Google", "title": "Senior Python Developer"}
{"type": "complete", "total": 5, "generated": 4, "cached": 1, "failed": 0}
```

## Integration

### With resume-matcher

```bash
# Step 1: Match jobs
resume-matcher run --jobs jobs/raw/ --resume inputs/resume.md --output matches/

# Step 2: Generate cover letters (only for viable matches)
cover-letter-gen run --matches matches/viable.json --resume inputs/resume.md --output applications/
```

### With notion-tracker

```bash
# Step 3: Sync to Notion
notion-tracker sync --applications applications/ --database-id <notion-db-id>
```

## Testing

```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=cover_letter_gen tests/

# Run specific test
pytest tests/test_generator.py -v
```

## License

MIT
