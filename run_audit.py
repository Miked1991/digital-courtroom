#!/usr/bin/env python3
"""
Automaton Auditor - Main entry point
Orchestrates the entire swarm for autonomous code governance
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.graph import AutomatonAuditor


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Automaton Auditor - Autonomous Code Governance Swarm"
    )
    
    parser.add_argument(
        "--repo",
        type=str,
        required=True,
        help="GitHub repository URL to audit"
    )
    
    parser.add_argument(
        "--pdf",
        type=str,
        required=True,
        help="Path to PDF report file"
    )
    
    parser.add_argument(
        "--rubric",
        type=str,
        default="rubric/week2_rubric.json",
        help="Path to rubric JSON file"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        default="audits",
        help="Output directory for audit reports"
    )
    
    args = parser.parse_args()
    
    # Validate inputs
    if not os.path.exists(args.pdf):
        logger.error(f"PDF file not found: {args.pdf}")
        sys.exit(1)
    
    if not os.path.exists(args.rubric):
        logger.error(f"Rubric file not found: {args.rubric}")
        sys.exit(1)
    
    # Initialize auditor
    logger.info("Initializing Automaton Auditor swarm...")
    auditor = AutomatonAuditor(rubric_path=args.rubric)
    
    # Run audit
    logger.info(f"Starting audit of {args.repo}")
    logger.info("This may take a few minutes...")
    
    try:
        result = auditor.run(args.repo, args.pdf)
        
        # Print summary
        logger.info("=" * 50)
        logger.info("AUDIT COMPLETE")
        logger.info("=" * 50)
        logger.info(f"Final report saved to: audits/report_onself_generated/audit_report.md")
        logger.info(f"Evidence summary saved to: audits/langsmith_logs/evidence_summary.json")
        logger.info(f"Execution metadata saved to: audits/langsmith_logs/execution_metadata.json")
        
        # Print key metrics
        metadata = result['execution_metadata']
        logger.info(f"Evidence collected: {metadata.get('evidence_count', 0)}")
        logger.info(f"Opinions rendered: {metadata.get('total_opinions', 0)}")
        logger.info(f"Criteria resolved: {metadata.get('criteria_resolved', 0)}")
        
    except Exception as e:
        logger.error(f"Audit failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()