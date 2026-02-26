#!/usr/bin/env python3
"""
Quick test version with hardcoded paths
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))
from src.graph import AutomatonAuditor


def quick_test():
    """Quick test with hardcoded values"""
    
    # 🔴 CHANGE THESE VALUES TO YOUR ACTUAL PATHS 🔴
    REPO_URL = "https://github.com/mussewold/the_vibe_code_auditor"  # Your GitHub repo
    PDF_PATH = "reports/intrem_report.pdf"  # Your PDF path
    RUBRIC_PATH = "ruberics/week2_ruberic.json"
    
    # Validate paths
    if not os.path.exists(PDF_PATH):
        print(f"❌ PDF not found: {PDF_PATH}")
        print("Please update the PDF_PATH variable with the correct path")
        return
    
    if not os.path.exists(RUBRIC_PATH):
        print(f"❌ Rubric not found: {RUBRIC_PATH}")
        return
    
    print("=" * 60)
    print("AUTOMATON AUDITOR - QUICK TEST")
    print("=" * 60)
    print(f"Repository: {REPO_URL}")
    print(f"PDF Report: {PDF_PATH}")
    print(f"Rubric: {RUBRIC_PATH}")
    print("=" * 60)
    
    # Initialize auditor
    print("\n🔄 Initializing auditor swarm...")
    auditor = AutomatonAuditor(rubric_path=RUBRIC_PATH)
    
    # Run audit
    print("🔄 Running forensic analysis...")
    print("   (This may take a few minutes)\n")
    
    try:
        result = auditor.run(REPO_URL, PDF_PATH)
        
        print("\n✅ AUDIT COMPLETE")
        print("=" * 60)
        print("📊 Results saved to:")
        print("   - audits/report_onself_generated/audit_report.md")
        print("   - audits/langsmith_logs/evidence_summary.json")
        
        # Print first few lines of report
        if result.get('final_report'):
            preview = result['final_report'].split('\n')[:10]
            print("\n📄 Report Preview:")
            for line in preview:
                print(f"   {line}")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    quick_test()