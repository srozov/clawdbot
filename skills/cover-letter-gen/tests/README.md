# Cover Letter Generator Skill

This skill generates tailored cover letters and customized CVs for job applications.

## Installation

```bash
cd skills/cover-letter-gen
pip install -e .
```

## Usage

### Using the run script

```bash
python scripts/run.py -m matches/viable.json -r inputs/resume.md -o applications/
```

### Using the CLI

```bash
cover-letter-gen run -m matches/viable.json -r inputs/resume.md -o applications/
```

### With company research

```bash
cover-letter-gen run -m matches/viable.json -r inputs/resume.md --enable-research
```

### Force regeneration

```bash
cover-letter-gen run -m matches/viable.json -r inputs/resume.md --force
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

## Configuration

Edit `config/cover-letter-config.json`:

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

## Testing

```bash
pytest tests/ -v
```

## Architecture

```
cover-letter-gen/
├── scripts/
│   └── run.py              # Main entry point
├── cover_letter_gen/
│   ├── __init__.py         # Package exports
│   ├── cli.py              # Click CLI interface
│   ├── generator.py        # Cover letter generation
│   ├── cv_customizer.py    # CV customization
│   ├── research.py         # Company research
│   └── models.py           # Pydantic models
├── config/
│   └── cover-letter-config.json
├── inputs/
│   ├── matches/
│   │   └── viable.json
│   └── resume.md
├── .cache/
│   └── cover-letter-gen/   # Cache directory
└── tests/
    └── test_*.py
```
