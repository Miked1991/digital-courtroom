#!/usr/bin/env python
"""
Command-line interface for running the Automaton Auditor.
"""

import asyncio
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

from src import AutomatonAuditor

load_dotenv()


async def main():
    parser = argparse.ArgumentParser(description="Run Automaton Auditor on a repository")
    parser.add_argument("repo_url", help="GitHub repository URL to audit")
    parser.add_argument("pdf_path", help="Path to PDF report")
    parser.add_argument("--output", "-o", default="audit/report.md", help="Output report path")
    parser.add_argument("--rubric", default="rubric/week2_rubric.json", help="Rubric JSON path")
    parser.add_argument("--thread", default="default", help="Thread ID for checkpointing")
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.pdf_path):
        print(f"Error: PDF file not found: {args.pdf_path}")
        return 1
    
    if not os.path.exists(args.rubric):
        print(f"Warning: Rubric not found at {args.rubric}, using default")
    
    # Run audit
    print(f"Starting audit for {args.repo_url}")
    auditor = AutomatonAuditor(rubric_path=args.rubric)
    
    final_state = await auditor.run_audit(
        repo_url=args.repo_url,
        pdf_path=args.pdf_path,
        thread_id=args.thread
    )
    
    # Save report
    auditor.save_report(final_state, args.output)
    print(f"Audit complete. Report saved to {args.output}")
    
    # Print summary
    print("\n" + "="*50)
    print("AUDIT SUMMARY")
    print("="*50)
    print(final_state.get("synthesis_notes", "No synthesis notes available"))
    print("="*50)
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))