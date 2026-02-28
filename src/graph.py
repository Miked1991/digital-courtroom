"""
Main LangGraph definition orchestrating the entire swarm.
Implements parallel detectives, fan-in aggregation, parallel judges, and synthesis.
"""

import os
import json
import uuid
from typing import Dict, List, Any, Optional, Literal
from pathlib import Path
import operator

from langgraph.graph import START, StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
#from langgraph.constants import START

from src.state import AgentState, RubricDimension, SynthesisRule
from src.nodes.detectives import RepoInvestigator, DocAnalyst, VisionInspector
from src.nodes.judges import Prosecutor, Defense, TechLead
from src.nodes.justice import ChiefJustice


class AutomatonAuditor:
    """Main orchestrator for the autonomous auditor swarm"""
    
    def __init__(self, rubric_path: str = "ruberics/week2_ruberic.json"):
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
        with open(self.rubric_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _build_graph(self) -> StateGraph:
        """Construct the hierarchical state graph with proper parallel execution"""
        
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
        
        # Set entry point to START
        builder.add_edge(START, "repo_investigator")
        
        # Define edges
        builder.add_edge("repo_investigator", "doc_analyst")
        builder.add_edge("repo_investigator", "vision_inspector")
        
        builder.add_edge("doc_analyst", "evidence_aggregator")
        builder.add_edge("vision_inspector", "evidence_aggregator")
        
        builder.add_edge("evidence_aggregator", "prosecutor")
        builder.add_edge("evidence_aggregator", "defense")
        builder.add_edge("evidence_aggregator", "tech_lead")
        
        builder.add_edge("prosecutor", "chief_justice")
        builder.add_edge("defense", "chief_justice")
        builder.add_edge("tech_lead", "chief_justice")
        
        builder.add_edge("chief_justice", END)
        
        # Compile with memory for state persistence
        memory = MemorySaver()
        return builder.compile(checkpointer=memory)
    
    def _aggregate_evidence(self, state: AgentState) -> Dict[str, Any]:
        """Synchronization node - aggregates evidence from all detectives."""
        # Count evidence types for metadata
        evidence_counts = {
            key: len(value) for key, value in state['evidences'].items()
        }
        
        # Update execution metadata
        metadata = state.get('execution_metadata', {})
        metadata['evidence_aggregated'] = evidence_counts
        
        return {"execution_metadata": metadata}
    
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
            "execution_metadata": {
                "start_time": str(uuid.uuid4()),
                "evidence_counts": {},
                "opinion_counts": {}
            }
        }
    
    def run(self, repo_url: str, pdf_path: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Execute the full audit pipeline
        
        Args:
            repo_url: GitHub repository URL to audit
            pdf_path: Path to PDF report file
            thread_id: Optional thread ID for checkpointing
        
        Returns:
            Final state with complete audit report
        """
        
        # Prepare initial state
        initial_state = self.prepare_initial_state(repo_url, pdf_path)
        
        # Generate thread_id if not provided
        if thread_id is None:
            thread_id = str(uuid.uuid4())
        
        # Create config with proper structure - ENSURE 'configurable' key exists
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }
        
        try:
            # Run graph with config - use the config dictionary
            final_state = self.graph.invoke(initial_state, config=config)
            
            # Save reports
            self._save_reports(final_state)
            
            return final_state
            
        except Exception as e:
            print(f"Error during graph execution: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Save error state for debugging
            error_state = {
                **initial_state,
                "error_log": [f"Execution error: {str(e)}"],
                "final_report": f"# Audit Failed\n\nError: {str(e)}\n\n```\n{traceback.format_exc()}\n```"
            }
            self._save_reports(error_state)
            raise
    
    def _save_reports(self, state: AgentState):
        """Save audit reports to disk"""
        
        # Create audit directories if they don't exist
        os.makedirs("audits/report_onself_generated", exist_ok=True)
        os.makedirs("audits/langsmith_logs", exist_ok=True)
        
        # Save main report
        report_path = "audits/report_onself_generated/audit_report.md"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(state.get('final_report', '# No report generated'))
        
        # Save execution metadata
        metadata_path = "audits/langsmith_logs/execution_metadata.json"
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(state.get('execution_metadata', {}), f, indent=2, default=str)
        
        # Save evidence summary
        evidence_path = "audits/langsmith_logs/evidence_summary.json"
        evidence_summary = {}
        for key, ev_list in state.get('evidences', {}).items():
            try:
                evidence_summary[key] = [e.model_dump() for e in ev_list]
            except:
                evidence_summary[key] = [str(e) for e in ev_list]
        
        with open(evidence_path, 'w', encoding='utf-8') as f:
            json.dump(evidence_summary, f, indent=2, default=str)