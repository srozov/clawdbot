#!/usr/bin/env python3
"""
Main entry point for notion-tracker skill.
"""
import sys
from pathlib import Path

# Add skill package to path
skill_dir = Path(__file__).parent.parent
sys.path.insert(0, str(skill_dir))

from notion_tracker.cli import main

if __name__ == "__main__":
    main()
