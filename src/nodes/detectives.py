"""
Detective layer nodes for forensic evidence collection.
Runs in parallel to gather objective evidence.
"""

from typing import Dict, List, Any
import asyncio
import logging

from ..state import AgentState, Evidence
from ..tools.repo_investigator import RepoInvestigatorTools
from ..tools.doc_analyst import DocAnalystTools
from ..tools.vision_inspector import VisionInspectorTools
from ..utils.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class DetectiveNodes:
    """Nodes for the Detective layer - objective evidence collection."""
    
    def __init__(self):
        self.context_builder = ContextBuilder()
        
    def repo_investigator_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Node for repository forensic analysis.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with repo evidence
        """
        logger.info("Running RepoInvestigator node")
        
        try:
            with RepoInvestigatorTools() as tools:
                # Clone repository
                clone_evidence = tools.clone_repository(state["repo_url"])
                
                # Collect all repo evidence
                repo_evidence = {
                    "clone_result": clone_evidence,
                }
                
                if clone_evidence.found:
                    # Analyze git history
                    repo_evidence["git_history"] = tools.analyze_git_history()
                    
                    # Analyze state definitions
                    repo_evidence["state_definitions"] = tools.analyze_state_definition()
                    
                    # Analyze graph orchestration
                    repo_evidence["graph_orchestration"] = tools.analyze_graph_orchestration()
                    
                    # Analyze tool safety
                    repo_evidence["tool_safety"] = tools.analyze_tool_safety()
                    
                    # Analyze structured output
                    repo_evidence["structured_output"] = tools.analyze_structured_output()
                
                # Filter to only relevant dimensions
                relevant_dimensions = self.context_builder.get_dimensions_for_target(
                    state["rubric_dimensions"], 
                    "github_repo"
                )
                
                # Organize evidence by rubric dimension
                evidences = {}
                for dim in relevant_dimensions:
                    dim_evidence = []
                    
                    # Map dimension ID to relevant evidence
                    if dim.id == "forensic_accuracy_code":
                        dim_evidence.extend([
                            repo_evidence.get("state_definitions"),
                            repo_evidence.get("tool_safety"),
                            repo_evidence.get("structured_output")
                        ])
                    elif dim.id == "langgraph_architecture":
                        dim_evidence.append(repo_evidence.get("graph_orchestration"))
                    elif dim.id == "judicial_nuance":
                        dim_evidence.append(repo_evidence.get("structured_output"))
                    
                    # Filter out None and add to evidences
                    valid_evidence = [e for e in dim_evidence if e and e.found]
                    if valid_evidence:
                        evidences[dim.id] = valid_evidence
                
                return {
                    "evidences": {
                        "repo_investigator": repo_evidence,
                        "organized_by_dimension": evidences
                    }
                }
                
        except Exception as e:
            logger.error(f"Error in RepoInvestigator: {e}")
            return {
                "errors": [f"RepoInvestigator error: {str(e)}"],
                "evidences": {
                    "repo_investigator_error": Evidence(
                        goal="Repository investigation",
                        found=False,
                        content=None,
                        location=state["repo_url"],
                        rationale=f"Error: {str(e)}",
                        confidence=0.0,
                        artifact_type="code"
                    )
                }
            }
    
    def doc_analyst_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Node for document forensic analysis.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with document evidence
        """
        logger.info("Running DocAnalyst node")
        
        try:
            tools = DocAnalystTools()
            
            # Extract text from PDF
            text_evidence = tools.extract_text_from_pdf(state["pdf_path"])
            
            doc_evidence = {
                "text_extraction": text_evidence,
            }
            
            if text_evidence.found:
                # Analyze theoretical depth
                doc_evidence["theoretical_depth"] = tools.analyze_theoretical_depth(state["pdf_path"])
                
                # Cross-reference with repo evidence if available
                if "repo_investigator" in state.get("evidences", {}):
                    doc_evidence["cross_reference"] = tools.cross_reference_claims(
                        state["pdf_path"],
                        state["evidences"]["repo_investigator"]
                    )
            
            # Filter to document-relevant dimensions
            relevant_dimensions = self.context_builder.get_dimensions_for_target(
                state["rubric_dimensions"],
                "pdf_report"
            )
            
            # Organize evidence by rubric dimension
            evidences = {}
            for dim in relevant_dimensions:
                if dim.id == "forensic_accuracy_docs":
                    dim_evidence = [
                        doc_evidence.get("theoretical_depth"),
                        doc_evidence.get("cross_reference")
                    ]
                    valid_evidence = [e for e in dim_evidence if e and e.found]
                    if valid_evidence:
                        evidences[dim.id] = valid_evidence
            
            return {
                "evidences": {
                    "doc_analyst": doc_evidence,
                    "organized_by_dimension": evidences
                }
            }
            
        except Exception as e:
            logger.error(f"Error in DocAnalyst: {e}")
            return {
                "errors": [f"DocAnalyst error: {str(e)}"],
                "evidences": {
                    "doc_analyst_error": Evidence(
                        goal="Document analysis",
                        found=False,
                        content=None,
                        location=state["pdf_path"],
                        rationale=f"Error: {str(e)}",
                        confidence=0.0,
                        artifact_type="documentation"
                    )
                }
            }
    
    def vision_inspector_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Node for vision-based diagram analysis.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with diagram evidence
        """
        logger.info("Running VisionInspector node")
        
        try:
            tools = VisionInspectorTools()
            
            # Analyze diagrams
            diagram_analysis = tools.analyze_diagram(state["pdf_path"])
            diagram_classification = tools.classify_diagram_type(state["pdf_path"])
            
            vision_evidence = {
                "diagram_analysis": diagram_analysis,
                "diagram_classification": diagram_classification
            }
            
            # Add to organized evidence
            evidences = {}
            if diagram_analysis.found:
                evidences["diagram_analysis"] = [diagram_analysis]
            if diagram_classification.found:
                evidences["diagram_classification"] = [diagram_classification]
            
            return {
                "evidences": {
                    "vision_inspector": vision_evidence,
                    "organized_by_dimension": evidences
                }
            }
            
        except Exception as e:
            logger.error(f"Error in VisionInspector: {e}")
            return {
                "errors": [f"VisionInspector error: {str(e)}"],
                "evidences": {
                    "vision_inspector_error": Evidence(
                        goal="Vision analysis",
                        found=False,
                        content=None,
                        location=state["pdf_path"],
                        rationale=f"Error: {str(e)}",
                        confidence=0.0,
                        artifact_type="diagram"
                    )
                }
            }


class EvidenceAggregator:
    """Node for synchronizing and aggregating evidence from parallel detectives."""
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        Aggregate evidence from all detective nodes.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with aggregated evidence
        """
        logger.info("Running EvidenceAggregator node")
        
        # Collect all evidence
        all_evidence = []
        organized_evidence = {}
        
        # Flatten all evidence collections
        for source, evidence_dict in state.get("evidences", {}).items():
            if source == "organized_by_dimension":
                for dim_id, evidence_list in evidence_dict.items():
                    if dim_id not in organized_evidence:
                        organized_evidence[dim_id] = []
                    organized_evidence[dim_id].extend(evidence_list)
                    all_evidence.extend(evidence_list)
            elif isinstance(evidence_dict, dict):
                for key, evidence in evidence_dict.items():
                    if isinstance(evidence, Evidence):
                        all_evidence.append(evidence)
        
        # Create aggregated view
        aggregated = {
            "total_evidence": len(all_evidence),
            "evidence_by_dimension": organized_evidence,
            "evidence_by_type": {},
            "confidence_summary": {}
        }
        
        # Group by artifact type
        for evidence in all_evidence:
            art_type = evidence.artifact_type
            if art_type not in aggregated["evidence_by_type"]:
                aggregated["evidence_by_type"][art_type] = []
            aggregated["evidence_by_type"][art_type].append({
                "goal": evidence.goal,
                "found": evidence.found,
                "confidence": evidence.confidence
            })
        
        # Calculate confidence by dimension
        for dim_id, evidence_list in organized_evidence.items():
            if evidence_list:
                avg_confidence = sum(e.confidence for e in evidence_list) / len(evidence_list)
                aggregated["confidence_summary"][dim_id] = avg_confidence
        
        return {
            "aggregated_evidence": aggregated
        }