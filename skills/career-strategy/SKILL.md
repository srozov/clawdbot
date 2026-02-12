---
name: career-strategy
description: Analyze resumes and generate diverse job search strategies using AI.
homepage: https://github.com/openclaw/job-application-agency
metadata: {"openclaw":{"emoji":"🎯","requires":{"env":["ANTHROPIC_API_KEY","OPENAI_API_KEY"]},"primaryEnv":"ANTHROPIC_API_KEY"}}
---

# career-strategy

Analyze resumes and generate 3-6 diverse job search strategies using AI. Part of the OpenClaw job-application-agency workflow.

## Purpose

- **Input:** `inputs/resume.md` - Resume in markdown format
- **Output:** `strategies/strategies.json` - Job search strategies
- **Purpose:** Analyze resume skills/experience and generate diverse search strategies across core, adjacent, and growth categories

## Quick Start

```bash
# Run the skill
python scripts/run.py

# Force re-generation (bypass cache)
python scripts/run.py --force
```

## Input Format

Resume in markdown format with semantic headers:

```markdown
## Summary
Senior Python Developer with 5+ years experience...

## Experience
- Senior Developer at TechCorp (2020-Present)
  - Built scalable APIs using Python and Django
  ...

## Skills
- Python, Django, PostgreSQL, AWS, Docker

## Education
- M.Sc. Computer Science, ETH Zürich
```

## Output Format

```json
{
  "strategies": [
    {
      "strategy_id": "strategy_0",
      "job_title": "Senior Python Developer",
      "location": "Zürich",
      "keywords": ["Python", "Django", "PostgreSQL"],
      "category": "core",
      "rationale": "Your Python experience aligns with senior backend roles...",
      "required_keywords": ["Python", "backend"],
      "excluded_keywords": ["frontend", "React"],
      "seniority_range": ["mid-level", "senior"],
      "remote_preference": "hybrid",
      "salary_min": 120000,
      "match_threshold": 0.7
    }
  ],
  "generated_at": "2025-05-10T15:30:00Z",
  "resume_hash": "abc123..."
}
```

## Strategy Categories

| Category | Description | Match Threshold |
|----------|-------------|-----------------|
| **core** | Direct match to current skills | 0.7 |
| **adjacent** | Related roles leveraging transferable skills | 0.6 |
| **growth** | Stretch opportunities for skill expansion | 0.5 |

## Configuration

### Global Config (`config/global.json`)

```json
{
  "llm_model": "anthropic/claude-sonnet-4-5",
  "cache_ttl_days": 7,
  "logging": {
    "level": "INFO"
  }
}
```

### Skill Config (`config/career-strategy-config.json`)

```json
{
  "llm_model": "anthropic/claude-sonnet-4-5",
  "max_strategies": 5,
  "enable_interactive": false,
  "base_location": "Zürich"
}
```

## Environment Variables

- `ANTHROPIC_API_KEY` - Anthropic API key for Claude (recommended)
- `OPENAI_API_KEY` - OpenAI API key for GPT-4 (fallback)
- `OPENROUTER_API_KEY` - OpenRouter API key (fallback)

## Caching

Strategies are cached by resume hash (MD5). Cache location: `.cache/career-strategy/{resume_hash}.json`

Clear cache:
```bash
rm -rf .cache/career-strategy/
```

## Integration

This skill is designed for the OpenClaw job-application-agency workflow:

```python
# In orchestrator.py
from career_strategy import ResumeAnalyzer

analyzer = ResumeAnalyzer()
strategies = analyzer.analyze(
    resume_path="inputs/resume.md",
    output_path="strategies/strategies.json",
)
```

**Workflow order:**
1. `career-strategy` → generates `strategies/strategies.json`
2. `job-scraper` → reads strategies, scrapes jobs
3. `resume-matcher` → matches jobs against resume
4. `cover-letter-gen` → generates cover letters
5. `notion-tracker` → syncs to Notion

## Development

```bash
# Install dependencies
pip install -e ../career-strategy[dev]

# Run tests
pytest tests/ -v

# Run CLI directly
career-strategy generate inputs/resume.md -o strategies/strategies.json
```

## License

MIT
