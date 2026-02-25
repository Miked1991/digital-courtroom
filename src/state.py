"""
State Management for the Automaton Auditor
Pydantic models with proper reducers for parallel execution
"""

import operator
from typing import Annotated, Dict, List, Literal, Optional, Any, TypedDict
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class Evidence(BaseModel):
    """Forensic evidence collected by detective agents"""
    model_config = ConfigDict(extra='forbid')
    
    goal: str = Field(description="The forensic goal this evidence addresses")
    found: bool = Field(description="Whether the artifact exists")
    content: Optional[str] = Field(default=None, description="Extracted content or snippet")
    location: str = Field(description="File path, commit hash, or page number")
    rationale: str = Field(description="Reasoning for confidence level")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    timestamp: datetime = Field(default_factory=datetime.now)
    artifact_type: Literal["code", "doc", "image", "git"] = Field(description="Type of evidence")


class JudicialOpinion(BaseModel):
    """Opinion from a judge in the dialectical bench"""
    model_config = ConfigDict(extra='forbid')
    
    judge: Literal["Prosecutor", "Defense", "TechLead"]
    criterion_id: str
    score: int = Field(ge=1, le=5)
    argument: str
    cited_evidence: List[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.now)
    confidence: float = Field(ge=0.0, le=1.0, default=0.9)


class RubricDimension(BaseModel):
    """Rubric dimension from the constitution"""
    model_config = ConfigDict(extra='forbid')
    
    id: str
    name: str
    target_artifact: Literal["github_repo", "pdf_report", "both"]
    forensic_instruction: str
    judicial_logic: Dict[str, str]


class SynthesisRule(BaseModel):
    """Rules for the Chief Justice synthesis"""
    security_override: str
    fact_supremacy: str
    dissent_requirement: str


class AgentState(TypedDict):
    """Main state graph state with proper reducers"""
    
    # Input
    repo_url: str
    pdf_path: str
    rubric_path: str
    
    # Configuration
    rubric_dimensions: List[RubricDimension]
    synthesis_rules: Optional[SynthesisRule]
    
    # Evidence Collection - Using reducer to merge from parallel detectives
    evidences: Annotated[Dict[str, List[Evidence]], operator.ior]
    
    # Judicial Opinions - Using add reducer to accumulate from parallel judges
    opinions: Annotated[List[JudicialOpinion], operator.add]
    
    # Aggregated State
    aggregated_evidence: Optional[Dict[str, Any]]
    criterion_scores: Annotated[Dict[str, Dict[str, Any]], operator.ior]
    
    # Output
    final_report: str
    remediation_plan: List[str]
    
    # Metadata
    errors: List[str]
    warnings: List[str]
    trace_url: Optional[str]
    execution_time: Optional[float]


class EvidenceAggregation(BaseModel):
    """Structured aggregation of evidence for judges"""
    criterion_id: str
    evidence_list: List[Evidence]
    summary: str
    contradictions: List[str]
    confidence: float