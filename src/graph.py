"""
Main LangGraph definition for the Automaton Auditor swarm.
Orchestrates parallel detective work and dialectical judgment.
"""

from typing import Literal
from datetime import datetime
import json
from pathlib import Path
import logging

from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver

from .state import AgentState, RubricDimension
from .nodes.detectives import DetectiveNodes, EvidenceAggregator
from .nodes.judges import JudgeNodes
from .nodes.justice import ChiefJusticeNode
from .utils.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class AutomatonAuditor:
    """Main orchestrator for the Automaton Auditor swarm."""
    
    def __init__(self, rubric_path: str = "rubric/week2_rubric.json"):
        """
        Initialize the Automaton Auditor with rubric.
        
        Args:
            rubric_path: Path to rubric JSON file
        """
        self.rubric_path = rubric_path
        self.rubric_data = self._load_rubric()
        self.detectives = DetectiveNodes()
        self.evidence_aggregator = EvidenceAggregator()
        self.judges = JudgeNodes()
        self.chief_justice = ChiefJusticeNode()
        self.context_builder = ContextBuilder()
        
        # Build the graph
        self.graph = self._build_graph()
    
    def _load_rubric(self) -> dict:
        """Load rubric from JSON file."""
        try:
            with open(self.rubric_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading rubric: {e}")
            # Fallback to embedded rubric
            return {
                "dimensions": [
                    {
                        "id": "forensic_accuracy_code",
                        "name": "Forensic Accuracy (Codebase)",
                        "target_artifact": "github_repo",
                        "forensic_instruction": "Verify Pydantic state models and sandboxed tools",
                        "judicial_logic": {
                            "prosecutor": "Check for security negligence",
                            "defense": "Highlight creative AST parsing",
                            "tech_lead": "Assess state reducers"
                        }
                    },
                    {
                        "id": "forensic_accuracy_docs",
                        "name": "Forensic Accuracy (Documentation)",
                        "target_artifact": "pdf_report",
                        "forensic_instruction": "Verify theoretical depth and cross-reference claims",
                        "judicial_logic": {
                            "prosecutor": "Charge hallucination if claims mismatch code",
                            "defense": "Identify theoretical alignment",
                            "tech_lead": "Verify architectural notes"
                        }
                    },
                    {
                        "id": "judicial_nuance",
                        "name": "Judicial Nuance & Dialectics",
                        "target_artifact": "github_repo",
                        "forensic_instruction": "Verify distinct judge personas and structured output",
                        "judicial_logic": {
                            "prosecutor": "Check for persona collusion",
                            "defense": "Look for forgiving instructions",
                            "tech_lead": "Evaluate rubric mapping"
                        }
                    },
                    {
                        "id": "langgraph_architecture",
                        "name": "LangGraph Orchestration Rigor",
                        "target_artifact": "github_repo",
                        "forensic_instruction": "Verify parallel branches and conditional edges",
                        "judicial_logic": {
                            "prosecutor": "Charge orchestration fraud if linear",
                            "defense": "Support simple but valid graphs",
                            "tech_lead": "Check fan-in synchronization"
                        }
                    }
                ],
                "synthesis_rules": {
                    "security_override": "Confirmed security flaws cap total score at 3",
                    "fact_supremacy": "Forensic evidence overrules judicial opinion",
                    "dissent_requirement": "Summarize prosecutor-defense disagreement"
                }
            }
    
    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph with parallel execution paths.
        
        Returns:
            Compiled StateGraph
        """
        # Initialize graph with state schema
        builder = StateGraph(AgentState)
        
        # Add nodes
        builder.add_node("repo_investigator", self.detectives.repo_investigator_node)
        builder.add_node("doc_analyst", self.detectives.doc_analyst_node)
        builder.add_node("vision_inspector", self.detectives.vision_inspector_node)
        builder.add_node("evidence_aggregator", self.evidence_aggregator)
        builder.add_node("prosecutor", self.judges.prosecutor_node)
        builder.add_node("defense", self.judges.defense_node)
        builder.add_node("tech_lead", self.judges.tech_lead_node)
        builder.add_node("chief_justice", self.chief_justice)
        
        # Set entry point
        builder.set_entry_point("repo_investigator")
        
        # Add parallel detective edges
        builder.add_edge("repo_investigator", "evidence_aggregator")
        builder.add_edge("doc_analyst", "evidence_aggregator")
        builder.add_edge("vision_inspector", "evidence_aggregator")
        
        # Fan-out to judges after evidence aggregation
        builder.add_edge("evidence_aggregator", "prosecutor")
        builder.add_edge("evidence_aggregator", "defense")
        builder.add_edge("evidence_aggregator", "tech_lead")
        
        # Fan-in to chief justice
        builder.add_edge("prosecutor", "chief_justice")
        builder.add_edge("defense", "chief_justice")
        builder.add_edge("tech_lead", "chief_justice")
        
        # End after chief justice
        builder.add_edge("chief_justice", END)
        
        # Add conditional routing for error handling
        builder.add_conditional_edges(
            "repo_investigator",
            self._check_critical_errors,
            {
                "continue": "evidence_aggregator",
                "abort": END
            }
        )
        
        # Compile with memory saver for checkpointing
        memory = MemorySaver()
        return builder.compile(checkpointer=memory)
    
    def _check_critical_errors(self, state: AgentState) -> Literal["continue", "abort"]:
        """
        Check for critical errors that should abort the audit.
        
        Args:
            state: Current agent state
            
        Returns:
            Routing decision
        """
        errors = state.get("errors", [])
        
        # Check for fatal errors
        fatal_patterns = [
            "clone failed",
            "invalid repository",
            "PDF not found"
        ]
        
        for error in errors:
            for pattern in fatal_patterns:
                if pattern in error.lower():
                    logger.warning(f"Fatal error detected: {error}")
                    return "abort"
        
        return "continue"
    
    def prepare_initial_state(self, repo_url: str, pdf_path: str) -> AgentState:
        """
        Prepare initial state for the audit.
        
        Args:
            repo_url: GitHub repository URL
            pdf_path: Path to PDF report
            
        Returns:
            Initial agent state
        """
        # Convert rubric dimensions to Pydantic models
        dimensions = [
            RubricDimension(**dim) 
            for dim in self.rubric_data.get("dimensions", [])
        ]
        
        return {
            "repo_url": repo_url,
            "pdf_path": pdf_path,
            "rubric_data": self.rubric_data,
            "rubric_dimensions": dimensions,
            "evidences": {},
            "opinions": [],
            "aggregated_evidence": {},
            "final_report": "",
            "synthesis_notes": "",
            "errors": [],
            "warnings": [],
            "processing_started": datetime.now(),
            "processing_completed": None
        }
    
    async def run_audit(self, repo_url: str, pdf_path: str, thread_id: str = "default") -> AgentState:
        """
        Run a complete audit on a repository.
        
        Args:
            repo_url: GitHub repository URL
            pdf_path: Path to PDF report
            thread_id: Thread ID for checkpointing
            
        Returns:
            Final agent state with audit report
        """
        logger.info(f"Starting audit for {repo_url}")
        
        # Prepare initial state
        initial_state = self.prepare_initial_state(repo_url, pdf_path)
        
        # Configure run
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        # Run the graph
        try:
            final_state = await self.graph.ainvoke(initial_state, config)
            logger.info("Audit completed successfully")
            return final_state
        except Exception as e:
            logger.error(f"Audit failed: {e}")
            initial_state["errors"].append(f"Audit failed: {str(e)}")
            initial_state["final_report"] = f"# Audit Failed\n\nError: {str(e)}"
            return initial_state
    
    def save_report(self, state: AgentState, output_path: str):
        """
        Save final report to file.
        
        Args:
            state: Final agent state
            output_path: Path to save report
        """
        try:
            output_dir = Path(output_path).parent
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w') as f:
                f.write(state["final_report"])
            
            logger.info(f"Report saved to {output_path}")
            
        except Exception as e:
            logger.error(f"Error saving report: {e}")