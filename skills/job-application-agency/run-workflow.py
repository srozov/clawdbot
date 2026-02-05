#!/usr/bin/env python3
"""
OpenClaw wrapper for job-application-agency workflow.

Runs the proven LangGraph workflow with strategy parameters from OpenClaw career-coach agent.
"""
import json
import sys
import subprocess
from pathlib import Path

REPO_PATH = Path("/home/agi01/job-application-agency")

def run_workflow(strategies: list[dict], max_jobs: int = 100):
    """
    Run job application workflow with provided search strategies.
    
    Args:
        strategies: List of strategy dicts with keys: job_title, location, keywords
        max_jobs: Maximum jobs to process per strategy
        
    Example strategies:
        [
            {"job_title": "Senior Python Developer", "location": "Zürich", "keywords": ["AI", "ML"]},
            {"job_title": "ML Engineer", "location": "Zürich", "keywords": ["LLM", "NLP"]},
            {"job_title": "Technical Lead", "location": "Zürich", "keywords": ["team", "architecture"]}
        ]
    """
    print(f"🚀 Running job application workflow with {len(strategies)} search strategies")
    print(f"📊 Max jobs per strategy: {max_jobs}")
    
    # Save strategies to temp file for workflow to read
    strategies_file = REPO_PATH / "outputs" / "strategies.json"
    strategies_file.parent.mkdir(exist_ok=True)
    
    with open(strategies_file, 'w') as f:
        json.dump({
            "strategies": strategies,
            "max_jobs": max_jobs
        }, f, indent=2)
    
    print(f"\n💾 Strategies saved to: {strategies_file}")
    
    # Run the main workflow
    # The workflow will detect strategies.json and use those instead of CLI args
    cmd = [
        sys.executable,
        str(REPO_PATH / "main.py"),
    ]
    
    print(f"\n🔄 Executing workflow...")
    print(f"   Command: {' '.join(cmd)}")
    print(f"   Working dir: {REPO_PATH}")
    print()
    
    result = subprocess.run(
        cmd,
        cwd=REPO_PATH,
        capture_output=False,  # Stream output in real-time
        text=True
    )
    
    if result.returncode == 0:
        print(f"\n✅ Workflow completed successfully!")
        print(f"\n📁 Check outputs:")
        print(f"   - Job postings: {REPO_PATH}/outputs/job_postings/")
        print(f"   - Applications: {REPO_PATH}/outputs/applications/")
        return True
    else:
        print(f"\n❌ Workflow failed with return code: {result.returncode}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: run-workflow.py <strategies_json>")
        print()
        print("Example:")
        print('  run-workflow.py \'[{"job_title": "Python Developer", "location": "Zürich", "keywords": []}]\'')
        sys.exit(1)
    
    strategies_json = sys.argv[1]
    max_jobs = int(sys.argv[2]) if len(sys.argv) > 2 else 100
    
    try:
        strategies = json.loads(strategies_json)
        success = run_workflow(strategies, max_jobs)
        sys.exit(0 if success else 1)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
