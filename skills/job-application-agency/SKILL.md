# Job Application Agency Skill

Automated job search, matching, and application generation using the proven LangGraph workflow.

## Overview

This skill wraps the existing high-performance job-application-agency workflow that can process 100 jobs across 3 search strategies in ~5 minutes with parallel scraping.

**Key Features:**
- ⚡ Parallel job scraping from jobs.ch (100 jobs in ~5 min)
- 🎯 LLM-powered resume matching (threshold: 0.6)
- ✍️ Cover letter + CV generation with company research
- 📊 Notion database tracking
- 🔄 OpenClaw career-coach integration

## Usage (OpenClaw Integration)

### Step 1: Career-Coach Generates Strategies

Career-coach agent should:
1. Read resume from `/home/agi01/job-application-agency/inputs/base_cv.md`
2. Analyze and generate 3-6 diverse search strategies
3. Save to JSON file (e.g., `/tmp/strategies.json`)

**Strategy JSON format:**
```json
[
  {
    "job_title": "Senior Python Developer",
    "location": "Zürich",
    "keywords": ["AI", "ML", "LLM"],
    "strategy_id": "core_0"
  },
  {
    "job_title": "ML Engineer",
    "location": "Zürich",
    "keywords": ["machine learning", "deep learning"],
    "strategy_id": "adjacent_1"
  },
  {
    "job_title": "Technical Lead",
    "location": "Zürich",
    "keywords": ["team", "architecture"],
    "strategy_id": "growth_2"
  }
]
```

### Step 2: Run Workflow with Strategies

```bash
python /home/agi01/clawdbot/skills/job-application-agency/scripts/run_with_strategies.py \
  /tmp/strategies.json \
  /home/agi01/job-application-agency/inputs/base_cv.md \
  100
```

**Arguments:**
- `strategies.json` - Path to JSON file with search strategies
- `resume.md` - Path to resume (optional, defaults to `inputs/base_cv.md`)
- `max_jobs` - Maximum jobs per strategy (optional, defaults to 100)

### Environment Setup

Required env vars in `/home/agi01/job-application-agency/.env`:
```
ANTHROPIC_API_KEY=<key>
NOTION_TOKEN=<token>
NOTION_DATABASE_ID=<id>
```

## Workflow Phases

The workflow executes in sequence:

1. **Job Scraping (Parallel)**
   - Launches browser automation per strategy
   - Scrapes jobs.ch in parallel
   - Extracts structured job data
   - Saves to `outputs/job_postings/<job_id>.json`

2. **Resume Matching (Parallel)**
   - LLM analyzes each job vs resume
   - Scores relevance (0.0 - 1.0)
   - Highlights matches and missing skills
   - Filters jobs with score ≥ 0.6

3. **Cover Letter Generation (Parallel)**
   - Web search for company context
   - Generates tailored cover letter
   - Creates customized CV
   - Saves to `outputs/applications/<job>_<company>/`

4. **Notion Tracking**
   - Syncs all applications to Notion
   - Uses existing database schema
   - Links cover letters and CVs

## Output Structure

```
/home/agi01/job-application-agency/outputs/
├── job_postings/
│   ├── <job_id_0>.json           # Raw job data
│   ├── <job_id_1>.json
│   └── ...
└── applications/
    ├── Senior_Python_Engineer_Company_A/
    │   ├── cover_letter.md        # Tailored letter
    │   ├── cv.md                  # Customized CV
    │   └── matching_results.json  # Match analysis
    ├── ML_Engineer_Company_B/
    │   └── ...
    └── ...
```

## Performance Metrics

- **Scraping:** 100 jobs in ~5 min (3 parallel strategies)
- **Matching:** Parallel LLM processing, 0.6 threshold
- **Generation:** Parallel cover letter + CV creation
- **Company research:** Web search per job (adds ~5-10s per letter)

## Technical Details

- **Browser automation:** Stagehand (Playwright-based)
- **State management:** LangGraph with SQLite checkpointing
- **Parallelization:** AsyncIO + LangGraph Send API
- **Caching:** SQLite cache for job data (reduces re-scraping)
- **Job board:** jobs.ch (proven, optimized)
- **Notion:** Existing schema unchanged

## Integration Flow

```
User → Career-Coach Agent
         ↓
       Analyzes resume
         ↓
       Generates 3-6 strategies
         ↓
       Saves strategies.json
         ↓
Conductor Agent → Runs workflow script
                    ↓
                  Parallel job scraping
                    ↓
                  Parallel matching
                    ↓
                  Parallel cover letter gen
                    ↓
                  Notion sync
                    ↓
                  Results reported
```
