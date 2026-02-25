"""
Detective layer nodes for evidence collection
Parallel execution of forensic investigators
"""

import logging
from typing import Dict, List, Any
from pathlib import Path

from langchain_core.runnables import RunnableConfig

from ..state import AgentState, Evidence
from ..tools.repo_tools import RepoInvestigator
from ..tools.doc_tools import DocAnalyst
from ..tools.vision_tools import VisionInspector
from ..utils.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class DetectiveNodes:
    """Nodes for detective layer evidence collection"""
    
    def __init__(self, api_keys: Dict[str, str]):
        self.api_keys = api_keys
        self.context_builder = None
        self.repo_investigator = None
        self.doc_analyst = None
        self.vision_inspector = None
        
        # Initialize vision if API key available
        if "geminai" in api_keys:
            self.vision_inspector = VisionInspector(
                api_key=api_keys["geminai"],
                model=api_keys.get("vision_model", "gemini-2.5-flash-image")
            )
    
    def initialize_investigators(self, state: AgentState) -> Dict:
        """Initialize investigators with context"""
        # Load context builder if not already loaded
        if not self.context_builder:
            self.context_builder = ContextBuilder(state["rubric_path"])
        
        # Initialize repo investigator
        self.repo_investigator = RepoInvestigator()
        
        # Initialize doc analyst
        self.doc_analyst = DocAnalyst()
        
        return {"warnings": state.get("warnings", [])}
    
    async def repo_investigator_node(self, state: AgentState, config: RunnableConfig) -> Dict:
        """
        Repository investigation node - collects code evidence
        Runs forensic protocols A, B, C
        """
        logger.info("Running RepoInvestigator node")
        warnings = state.get("warnings", [])
        
        try:
            # Clone repository
            success, message = self.repo_investigator.clone_repository(state["repo_url"])
            if not success:
                warnings.append(f"Repo clone failed: {message}")
                return {
                    "evidences": {
                        "repo_analysis": [Evidence(
                            goal="Repository Access",
                            found=False,
                            content=message,
                            location=state["repo_url"],
                            rationale="Failed to clone repository",
                            confidence=0.0,
                            artifact_type="code"
                        )]
                    },
                    "warnings": warnings
                }
            
            # Collect all evidence
            evidences = {}
            
            # Git forensic analysis
            commits = self.repo_investigator.extract_git_history()
            git_evidence = self.repo_investigator.analyze_commit_pattern(commits)
            evidences["git_analysis"] = [git_evidence]
            
            # State management rigor
            state_evidence = self.repo_investigator.find_state_definition()
            evidences["state_management"] = [state_evidence]
            
            # Graph orchestration
            graph_evidence = self.repo_investigator.analyze_graph_structure()
            evidences["graph_orchestration"] = [graph_evidence]
            
            # Tool safety
            tool_evidence = self.repo_investigator.analyze_tool_safety()
            evidences["tool_safety"] = [tool_evidence]
            
            # Structured output
            structured_evidence = self.repo_investigator.analyze_structured_output()
            evidences["structured_output"] = [structured_evidence]
            
            return {
                "evidences": evidences,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"RepoInvestigator failed: {e}")
            warnings.append(f"RepoInvestigator error: {str(e)}")
            return {"warnings": warnings}
    
    async def doc_analyst_node(self, state: AgentState, config: RunnableConfig) -> Dict:
        """
        Document analysis node - collects PDF evidence
        Runs forensic protocols for document analysis
        """
        logger.info("Running DocAnalyst node")
        warnings = state.get("warnings", [])
        
        try:
            # Ingest PDF
            success, message = self.doc_analyst.ingest_pdf(state["pdf_path"])
            if not success:
                warnings.append(f"PDF ingestion failed: {message}")
                return {"warnings": warnings}
            
            # Collect evidence
            evidences = {}
            
            # Theoretical depth analysis
            depth_evidence = self.doc_analyst.query_keywords([
                "Dialectical Synthesis",
                "Fan-In",
                "Fan-Out",
                "Metacognition",
                "State Synchronization"
            ])
            evidences["theoretical_depth"] = [depth_evidence]
            
            # Concept verification
            concept_evidence = self.doc_analyst.analyze_concept_verification()
            evidences["concept_verification"] = [concept_evidence]
            
            # Cross-reference with repo evidence
            if "evidences" in state:
                cross_ref_evidence = self.doc_analyst.cross_reference_claims(state["evidences"])
                evidences["cross_reference"] = [cross_ref_evidence]
            
            return {
                "evidences": evidences,
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"DocAnalyst failed: {e}")
            warnings.append(f"DocAnalyst error: {str(e)}")
            return {"warnings": warnings}
    
    async def vision_inspector_node(self, state: AgentState, config: RunnableConfig) -> Dict:
        """
        Vision inspection node - analyzes diagrams
        Runs multimodal forensic protocols
        """
        logger.info("Running VisionInspector node")
        warnings = state.get("warnings", [])
        
        if not self.vision_inspector:
            warnings.append("Vision Inspector not initialized - missing API key")
            return {"warnings": warnings}
        
        try:
            # Ensure doc analyst has ingested PDF
            if not self.doc_analyst or not self.doc_analyst.images:
                # Try to ingest PDF if not already done
                self.doc_analyst = DocAnalyst()
                success, _ = self.doc_analyst.ingest_pdf(state["pdf_path"])
                if not success or not self.doc_analyst.images:
                    warnings.append("No images found in PDF for vision analysis")
                    return {"warnings": warnings}
            
            # Analyze diagrams
            diagram_evidence = self.vision_inspector.analyze_all_diagrams(self.doc_analyst.images)
            
            return {
                "evidences": {
                    "diagram_analysis": [diagram_evidence]
                },
                "warnings": warnings
            }
            
        except Exception as e:
            logger.error(f"VisionInspector failed: {e}")
            warnings.append(f"VisionInspector error: {str(e)}")
            return {"warnings": warnings}
    
    async def evidence_aggregator_node(self, state: AgentState, config: RunnableConfig) -> Dict:
        """
        Evidence aggregation node - synchronizes and structures evidence for judges
        Fan-in synchronization point
        """
        logger.info("Running EvidenceAggregator node")
        
        if "evidences" not in state or not state["evidences"]:
            return {
                "aggregated_evidence": {},
                "warnings": state.get("warnings", []) + ["No evidence collected"]
            }
        
        # Structure evidence by criterion
        aggregated = {}
        
        # Map evidence to rubric dimensions
        if self.context_builder:
            for dimension in self.context_builder.dimensions:
                criterion_id = dimension.id
                criterion_evidence = []
                
                # Collect all evidence relevant to this criterion
                for evidence_list in state["evidences"].values():
                    for evidence in evidence_list:
                        # Simple relevance matching based on goal
                        if dimension.name.lower() in evidence.goal.lower() or \
                           any(keyword in evidence.goal.lower() for keyword in criterion_id.split('_')):
                            criterion_evidence.append(evidence)
                
                if criterion_evidence:
                    # Create summary
                    summary = f"Found {len(criterion_evidence)} pieces of evidence for {dimension.name}\n"
                    contradictions = self._find_contradictions(criterion_evidence)
                    
                    aggregated[criterion_id] = {
                        "criterion_id": criterion_id,
                        "evidence_list": criterion_evidence,
                        "summary": summary,
                        "contradictions": contradictions,
                        "confidence": sum(e.confidence for e in criterion_evidence) / len(criterion_evidence)
                    }
        
        return {
            "aggregated_evidence": aggregated
        }
    
    def _find_contradictions(self, evidence_list: List[Evidence]) -> List[str]:
        """Find contradictions in evidence"""
        contradictions = []
        
        # Check for contradictions in findings
        found_count = sum(1 for e in evidence_list if e.found)
        if 0 < found_count < len(evidence_list):
            contradictions.append("Inconsistent findings across evidence sources")
        
        # Check confidence contradictions
        confidences = [e.confidence for e in evidence_list]
        if max(confidences) - min(confidences) > 0.5:
            contradictions.append("Wide variance in confidence levels")
        
        return contradictions
    
    def cleanup(self):
        """Cleanup temporary resources"""
        if self.repo_investigator:
            self.repo_investigator.cleanup()