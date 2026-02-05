#!/usr/bin/env python3
"""
Run job-application-agency workflow with pre-defined strategies from OpenClaw career-coach.

This bypasses the interactive LangGraph career coaching and uses strategies
provided by the OpenClaw career-coach agent.
"""
import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import List, Dict

# Add job-application-agency to path
REPO_PATH = Path("/home/agi01/job-application-agency")
sys.path.insert(0, str(REPO_PATH))

from dotenv import load_dotenv
load_dotenv(REPO_PATH / ".env")

from langgraph_agents.state import ApplicationWorkflowState, Strategy
from langgraph_agents.graph import create_application_workflow
from models import Resume

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


async def run_with_strategies(
    strategies: List[Dict[str, any]],
    resume_path: Path,
    max_jobs: int = 100,
    max_retries: int = 3
):
    """
    Run job application workflow with provided search strategies.
    
    Args:
        strategies: List of strategy dicts with keys: job_title, location, keywords, strategy_id
        resume_path: Path to resume markdown file
        max_jobs: Maximum jobs per strategy
        max_retries: Max retry attempts
        
    Returns:
        Final workflow state
    """
    logger.info(f"🚀 Starting job application workflow with {len(strategies)} strategies")
    logger.info(f"📄 Resume: {resume_path}")
    logger.info(f"📊 Max jobs per strategy: {max_jobs}")
    
    # Load resume
    logger.info(f"\n📄 Loading resume...")
    with open(resume_path, 'r') as f:
        resume_content = f.read()
    
    resume_data = Resume(content=resume_content)
    
    # Convert strategy dicts to Strategy objects
    strategy_objects = [
        Strategy(
            job_title=s["job_title"],
            location=s["location"],
            keywords=s.get("keywords", []),
            strategy_id=s.get("strategy_id", f"strategy_{i}")
        )
        for i, s in enumerate(strategies)
    ]
    
    logger.info(f"\n🎯 Search strategies:")
    for strategy in strategy_objects:
        logger.info(f"   - {strategy.job_title} in {strategy.location} (keywords: {strategy.keywords})")
    
    # Create initial state with pre-defined strategies
    from langgraph_agents.graph import create_initial_state
    initial_state = create_initial_state(
        max_jobs=max_jobs,
        max_retries=max_retries
    )
    
    # Inject resume and strategies into state
    initial_state["resume_data"] = resume_data
    initial_state["suggested_search_terms"] = strategy_objects
    initial_state["user_approved_strategies"] = True  # Skip career coaching
    initial_state["career_coaching_complete"] = True  # Mark coaching as done
    
    # Build workflow graph
    logger.info(f"\n🔧 Building workflow graph...")
    workflow = create_application_workflow(checkpointer=True)
    
    # Generate unique thread_id for this run
    from langgraph_agents.session_manager import generate_session_id
    thread_id = generate_session_id("openclaw")
    
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }
    
    logger.info(f"📋 Thread ID: {thread_id}")
    logger.info(f"\n🚀 Starting workflow execution...\n")
    
    # Run workflow
    final_state = None
    async for event in workflow.astream(initial_state, config, stream_mode="values"):
        final_state = event
        
        # Log progress
        extracted = len(event.get("extracted_job_ids", []))
        processed = len(event.get("processed_jobs", []))
        cover_letters = len(event.get("cover_letters", []))
        
        if extracted > 0 or processed > 0 or cover_letters > 0:
            logger.info(f"Progress: {extracted} extracted | {processed} matched | {cover_letters} cover letters")
    
    logger.info(f"\n🎉 Workflow complete!")
    
    # Display results
    extracted_jobs = len(final_state.get("extracted_job_ids", []))
    processed_jobs = len(final_state.get("processed_jobs", []))
    cover_letters_count = len(final_state.get("cover_letters", []))
    application_records = len(final_state.get("application_records", []))
    
    logger.info(f"\n📊 Final Results:")
    logger.info(f"   ✅ Jobs extracted: {extracted_jobs}")
    logger.info(f"   ✅ Jobs matched: {processed_jobs}")
    logger.info(f"   ✅ Cover letters generated: {cover_letters_count}")
    logger.info(f"   ✅ Application records: {application_records}")
    
    logger.info(f"\n📁 Output Locations:")
    logger.info(f"   - Job postings: {REPO_PATH}/outputs/job_postings/")
    logger.info(f"   - Applications: {REPO_PATH}/outputs/applications/")
    
    return final_state


async def main():
    """CLI entry point."""
    if len(sys.argv) < 2:
        print("Usage: run_with_strategies.py <strategies_json_file> [resume_path] [max_jobs]")
        print()
        print("Example:")
        print('  run_with_strategies.py strategies.json')
        print('  run_with_strategies.py strategies.json /path/to/resume.md 150')
        print()
        print("strategies.json format:")
        print('[')
        print('  {"job_title": "Senior Python Developer", "location": "Zürich", "keywords": ["AI", "ML"], "strategy_id": "core_0"},')
        print('  {"job_title": "ML Engineer", "location": "Zürich", "keywords": ["LLM"], "strategy_id": "adjacent_1"}')
        print(']')
        sys.exit(1)
    
    strategies_file = Path(sys.argv[1])
    resume_path = Path(sys.argv[2]) if len(sys.argv) > 2 else REPO_PATH / "inputs" / "base_cv.md"
    max_jobs = int(sys.argv[3]) if len(sys.argv) > 3 else 100
    
    # Load strategies from JSON
    with open(strategies_file, 'r') as f:
        strategies = json.load(f)
    
    if not isinstance(strategies, list):
        print(f"❌ Error: strategies.json must contain a JSON array")
        sys.exit(1)
    
    # Run workflow
    try:
        await run_with_strategies(
            strategies=strategies,
            resume_path=resume_path,
            max_jobs=max_jobs
        )
    except Exception as e:
        logger.error(f"❌ Workflow failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
