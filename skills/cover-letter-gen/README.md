# Cover Letter Generator Skill

Generate tailored cover letters and customized CVs for job applications.

## Installation

```bash
pip install -e .
```

## Usage

### Generate all cover letters for viable matches

```bash
cover-letter-gen run --matches matches/viable.json --resume inputs/resume.md --output applications/
```

### Generate a single cover letter

```bash
cover-letter-gen generate --job jobs/raw/job-123.json --match matches/match-123.json --resume inputs/resume.md
```

### With company research

```bash
cover-letter-gen run --matches matches/viable.json --resume inputs/resume.md --enable-research
```

### Force re-generation (skip cache)

```bash
cover-letter-gen run --matches matches/viable.json --resume inputs/resume.md --force
```

## Configuration

Create `config/cover-letter-config.json`:

```json
{
    "llm_model": "anthropic/claude-sonnet-4",
    "style": "adaptive",
    "enable_company_research": true,
    "company_cache_ttl_days": 7,
    "max_length_words": 350
}
```

Or use global config `config/global.json`:

```json
{
    "llm_model": "anthropic/claude-sonnet-4",
    "logging": {
        "level": "INFO",
        "format": "json"
    },
    "cache_ttl_days": 7
}
```

## Input Files

- `matches/viable.json` - High-scoring matches from resume-matcher
- `inputs/resume.md` - Base resume in markdown format
- `jobs/raw/*.json` - Job postings (for context)

## Output Files

- `applications/{company}_{title}/cover_letter.md`
- `applications/{company}_{title}/cv.md`
- `applications/{company}_{title}/metadata.json`
- `applications/index.json`

## Architecture

```
cover_letter_gen/
├── __init__.py       # Package exports
├── cli.py            # Click CLI interface
├── generator.py      # Cover letter generation logic
├── cv_customizer.py  # CV customization
├── research.py       # Company research
└── models.py         # Pydantic models
```

## License

MIT
