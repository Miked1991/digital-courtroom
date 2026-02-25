"""
Main LangGraph definition for the Automaton Auditor
Hierarchical state graph with parallel execution
"""

import os
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver
from langchain_core.runnables import RunnableConfig

from .state import AgentState
from .nodes.detectives import DetectiveNodes
from .nodes.judges import JudgeNodes
from .nodes.justice import ChiefJusticeNode
from .utils.context_builder import ContextBuilder

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AutomatonAuditor:
    """Main orchestrator for the Automaton Auditor swarm"""
    
    def __init__(self, 
                 openai_api_key: Optional[str] = None,
                 anthropic_api_key: Optional[str] = None,
                 langsmith_api_key: Optional[str] = None,
                 model: str = "gpt-4-turbo-preview"):
        
        # API keys
        self.api_keys = {
            "openai": openai_api_key or os.getenv("OPENAI_API_KEY"),
            "anthropic": anthropic_api_key or os.getenv("ANTHROPIC_API_KEY"),
            "langsmith": langsmith_api_key or os.getenv("LANGSMITH_API_KEY")
        }
        
        # Configure LangSmith
        if self.api_keys["langsmith"]:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = self.api_keys["langsmith"]
            os.environ["LANGCHAIN_PROJECT"] = os.getenv("LANGCHAIN_PROJECT", "automaton-auditor")
        
        self.model = model
        self.graph = None
        self.app = None
        
        # Initialize nodes
        self.detectives = DetectiveNodes(self.api_keys)
        self.judges = JudgeNodes(self.api_keys, model)
        self.chief_justice = ChiefJusticeNode(self.api_keys, model)
        
        # Build graph
        self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph state graph"""
        
        # Initialize graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        
        # Detective layer nodes (parallel)
        workflow.add_node("initialize_investigators", self.detectives.initialize_investigators)
        workflow.add_node("repo_investigator", self.detectives.repo_investigator_node)
        workflow.add_node("doc_analyst", self.detectives.doc_analyst_node)
        workflow.add_node("vision_inspector", self.detectives.vision_inspector_node)
        workflow.add_node("evidence_aggregator", self.detectives.evidence_aggregator_node)
        
        # Judicial layer nodes (parallel)
        workflow.add_node("prosecutor", self.judges.prosecutor_node)
        workflow.add_node("defense", self.judges.defense_node)
        workflow.add_node("tech_lead", self.judges.tech_lead_node)
        
        # Supreme court node
        workflow.add_node("chief_justice", self.chief_justice.synthesize_verdict)
        
        # Define edges
        
        # Start -> Initialize
        workflow.set_entry_point("initialize_investigators")
        
        # Initialize -> Parallel detectives
        workflow.add_edge("initialize_investigators", "repo_investigator")
        workflow.add_edge("initialize_investigators", "doc_analyst")
        workflow.add_edge("initialize_investigators", "vision_inspector")
        
        # Detectives -> Aggregator (fan-in)
        workflow.add_edge("repo_investigator", "evidence_aggregator")
        workflow.add_edge("doc_analyst", "evidence_aggregator")
        workflow.add_edge("vision_inspector", "evidence_aggregator")
        
        # Aggregator -> Parallel judges (fan-out)
        workflow.add_edge("evidence_aggregator", "prosecutor")
        workflow.add_edge("evidence_aggregator", "defense")
        workflow.add_edge("evidence_aggregator", "tech_lead")
        
        # Judges -> Chief Justice (fan-in)
        workflow.add_edge("prosecutor", "chief_justice")
        workflow.add_edge("defense", "chief_justice")
        workflow.add_edge("tech_lead", "chief_justice")
        
        # Chief Justice -> End
        workflow.add_edge("chief_justice", END)
        
        # Add conditional edges for error handling
        workflow.add_conditional_edges(
            "repo_investigator",
            self._check_errors,
            {
                "continue": "evidence_aggregator",
                "error": END
            }
        )
        
        # Compile graph
        self.graph = workflow.compile(checkpointer=MemorySaver())
        self.app = workflow.compile()
        
        logger.info("Graph built successfully")
    
    def _check_errors(self, state: AgentState) -> str:
        """Check for errors in detective nodes"""
        if state.get("warnings") and len(state["warnings"]) > 5:
            logger.error("Too many errors, aborting")
            return "error"
        return "continue"
    
    async def audit(self, 
                   repo_url: str, 
                   pdf_path: str, 
                   rubric_path: str,
                   config: Optional[RunnableConfig] = None) -> AgentState:
        """
        Run complete audit on a repository
        
        Args:
            repo_url: GitHub repository URL
            pdf_path: Path to PDF report
            rubric_path: Path to rubric JSON
            config: Optional LangGraph config
        
        Returns:
            Final state with audit report
        """
        
        # Initial state
        initial_state = {
            "repo_url": repo_url,
            "pdf_path": pdf_path,
            "rubric_path": rubric_path,
            "evidences": {},
            "opinions": [],
            "aggregated_evidence": {},
            "criterion_scores": {},
            "final_report": "",
            "remediation_plan": [],
            "warnings": [],
            "errors": [],
            "execution_time": None
        }
        
        start_time = datetime.now()
        
        try:
            # Run graph
            final_state = await self.app.ainvoke(initial_state, config=config)
            
            # Add execution time
            execution_time = (datetime.now() - start_time).total_seconds()
            final_state["execution_time"] = execution_time
            
            # Add trace URL if LangSmith enabled
            if self.api_keys["langsmith"]:
                # In production, you'd get the actual run URL
                final_state["trace_url"] = "https://smith.langchain.com/public/example"
            
            return final_state
            
        except Exception as e:
            logger.error(f"Audit failed: {e}")
            return {
                **initial_state,
                "errors": [str(e)],
                "final_report": f"# Audit Failed\n\nError: {str(e)}"
            }
        finally:
            # Cleanup
            self.detectives.cleanup()
    
    def get_graph_diagram(self) -> str:
        """Get Mermaid diagram of the graph"""
        if self.graph:
            return self.graph.get_graph().draw_mermaid()
        return "Graph not built"


# CLI entry point
async def main():
    """Command line interface"""
    import argparse
    import asyncio
    
    parser = argparse.ArgumentParser(description="Automaton Auditor")
    parser.add_argument("--repo", required=True, help="GitHub repository URL")
    parser.add_argument("--pdf", required=True, help="Path to PDF report")
    parser.add_argument("--rubric", default="rubric/week2_rubric.json", help="Path to rubric JSON")
    parser.add_argument("--output", default="audit/report_onself_generated", help="Output directory")
    
    args = parser.parse_args()
    
    # Initialize auditor
    auditor = AutomatonAuditor()
    
    # Run audit
    result = await auditor.audit(args.repo, args.pdf, args.rubric)
    
    # Save report
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)
    
    report_file = output_path / f"audit_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    with open(report_file, 'w') as f:
        f.write(result["final_report"])
    
    print(f"Audit complete. Report saved to {report_file}")
    print(f"Overall score: {result.get('criterion_scores', {}).get('final_score', 'N/A')}")


if __name__ == "__main__":
    asyncio.run(main())