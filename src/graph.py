"""
Main LangGraph definition orchestrating the entire swarm.
Implements parallel detectives, fan-in aggregation, parallel judges, and synthesis.
"""

import os
import json
from typing import Dict, List, Any
from pathlib import Path

from langgraph.graph import StateGraph, END
from langgraph.checkpoint import MemorySaver

from src.state import AgentState, RubricDimension, SynthesisRule
from src.nodes.detectives import RepoInvestigator, DocAnalyst, VisionInspector
from src.nodes.judges import Prosecutor, Defense, TechLead
from src.nodes.justice import ChiefJustice


class AutomatonAuditor:
    """Main orchestrator for the autonomous auditor swarm"""
    
    def __init__(self, rubric_path: str = "rubric/week2_rubric.json"):
        self.rubric_path = rubric_path
        self.rubric = self._load_rubric()
        
        # Initialize agents
        self.repo_investigator = RepoInvestigator()
        self.doc_analyst = DocAnalyst()
        self.vision_inspector = VisionInspector()
        
        self.prosecutor = Prosecutor()
        self.defense = Defense()
        self.tech_lead = TechLead()
        
        self.chief_justice = ChiefJustice()
        
        # Build graph
        self.graph = self._build_graph()
    
    def _load_rubric(self) -> Dict:
        """Load machine-readable rubric"""
        with open(self.rubric_path, 'r') as f:
            return json.load(f)
    
    def _build_graph(self) -> StateGraph:
        """Construct the hierarchical state graph"""
        
        # Initialize graph with our state
        builder = StateGraph(AgentState)
        
        # Add nodes for each agent
        builder.add_node("repo_investigator", self.repo_investigator)
        builder.add_node("doc_analyst", self.doc_analyst)
        builder.add_node("vision_inspector", self.vision_inspector)
        builder.add_node("evidence_aggregator", self._aggregate_evidence)
        builder.add_node("prosecutor", self.prosecutor)
        builder.add_node("defense", self.defense)
        builder.add_node("tech_lead", self.tech_lead)
        builder.add_node("chief_justice", self.chief_justice)
        
        # Set entry point
        builder.set_entry_point("repo_investigator")
        
        # Parallel detectives - fan-out from entry
        builder.add_edge("repo_investigator", "doc_analyst")
        builder.add_edge("repo_investigator", "vision_inspector")
        
        # Fan-in to aggregator
        builder.add_edge("doc_analyst", "evidence_aggregator")
        builder.add_edge("vision_inspector", "evidence_aggregator")
        
        # Aggregator to parallel judges
        builder.add_edge("evidence_aggregator", "prosecutor")
        builder.add_edge("evidence_aggregator", "defense")
        builder.add_edge("evidence_aggregator", "tech_lead")
        
        # Judges to chief justice (fan-in)
        builder.add_edge("prosecutor", "chief_justice")
        builder.add_edge("defense", "chief_justice")
        builder.add_edge("tech_lead", "chief_justice")
        
        # End after chief justice
        builder.add_edge("chief_justice", END)
        
        # Add conditional edges for error handling
        builder.add_conditional_edges(
            "repo_investigator",
            self._check_clone_success,
            {
                "continue": "doc_analyst",
                "error": END
            }
        )
        
        # Compile with memory for state persistence
        memory = MemorySaver()
        return builder.compile(checkpointer=memory)
    
    def _aggregate_evidence(self, state: AgentState) -> Dict[str, Any]:
        """Synchronization node - aggregates evidence from all detectives"""
        # Just pass through - state already merged via reducers
        # This node exists for graph clarity and potential validation
        return {}
    
    def _check_clone_success(self, state: AgentState) -> str:
        """Check if repo clone was successful"""
        if 'git_clone' in state['evidences']:
            for evidence in state['evidences']['git_clone']:
                if not evidence.found:
                    return "error"
        return "continue"
    
    def prepare_initial_state(self, repo_url: str, pdf_path: str) -> AgentState:
        """Prepare initial state with rubric and rules"""
        
        # Parse rubric dimensions
        dimensions = [
            RubricDimension(**dim) 
            for dim in self.rubric['dimensions']
        ]
        
        # Parse synthesis rules
        rules = SynthesisRule(**self.rubric['synthesis_rules'])
        
        return {
            "repo_url": repo_url,
            "pdf_path": pdf_path,
            "rubric_path": self.rubric_path,
            "rubric_dimensions": dimensions,
            "synthesis_rules": rules,
            "evidences": {},
            "opinions": [],
            "final_report": "",
            "error_log": [],
            "execution_metadata": {}
        }
    
    def run(self, repo_url: str, pdf_path: str) -> Dict[str, Any]:
        """
        Execute the full audit pipeline
        
        Args:
            repo_url: GitHub repository URL to audit
            pdf_path: Path to PDF report file
        
        Returns:
            Final state with complete audit report
        """
        
        # Prepare initial state
        initial_state = self.prepare_initial_state(repo_url, pdf_path)
        
        # Run graph
        final_state = self.graph.invoke(initial_state)
        
        # Save reports
        self._save_reports(final_state)
        
        return final_state
    
    def _save_reports(self, state: AgentState):
        """Save audit reports to disk"""
        
        # Create audit directories if they don't exist
        os.makedirs("audits/report_onself_generated", exist_ok=True)
        os.makedirs("audits/langsmith_logs", exist_ok=True)
        
        # Save main report
        report_path = "audits/report_onself_generated/audit_report.md"
        with open(report_path, 'w') as f:
            f.write(state['final_report'])
        
        # Save execution metadata
        metadata_path = "audits/langsmith_logs/execution_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(state['execution_metadata'], f, indent=2, default=str)
        
        # Save evidence summary
        evidence_path = "audits/langsmith_logs/evidence_summary.json"
        evidence_summary = {
            key: [e.model_dump() for e in ev_list]
            for key, ev_list in state['evidences'].items()
        }
        with open(evidence_path, 'w') as f:
            json.dump(evidence_summary, f, indent=2, default=str)