"""
Production-grade state management with Pydantic models.
Enforces strict typing and proper state reduction for parallel execution.
"""

from typing import Annotated, Dict, List, Literal, Optional, Any
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, ConfigDict
import operator
from datetime import datetime


class Evidence(BaseModel):
    """Forensic evidence collected by detectives - must be factual, no opinions."""
    model_config = ConfigDict(frozen=True)  # Immutable evidence
    
    goal: str = Field(description="The specific forensic goal this evidence addresses")
    found: bool = Field(description="Whether the artifact exists")
    content: Optional[str] = Field(default=None, description="The actual content found")
    location: str = Field(description="File path or commit hash where evidence was found")
    rationale: str = Field(description="Reasoning for confidence level in this evidence")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    timestamp: datetime = Field(default_factory=datetime.now)


class JudicialOpinion(BaseModel):
    """Structured output from judges - must be enforced via .with_structured_output()"""
    model_config = ConfigDict(frozen=True)
    
    judge: Literal["Prosecutor", "Defense", "TechLead"]
    criterion_id: str
    score: int = Field(ge=1, le=5, description="Score from 1-5")
    argument: str = Field(description="Detailed reasoning for the score")
    cited_evidence: List[str] = Field(description="References to evidence locations")
    dissent_notes: Optional[str] = Field(default=None, description="Points of disagreement with other judges")


class RubricDimension(BaseModel):
    """Machine-readable rubric dimension from JSON"""
    id: str
    name: str
    target_artifact: Literal["github_repo", "pdf_report"]
    forensic_instruction: str
    judicial_logic: Dict[str, str]


class SynthesisRule(BaseModel):
    """Hardcoded rules for the Chief Justice"""
    security_override: str
    fact_supremacy: str
    dissent_requirement: str


class AgentState(TypedDict):
    """
    State graph definition with reducers for parallel execution.
    Uses operator.ior and operator.add to prevent overwrites in parallel branches.
    """
    # Input
    repo_url: str
    pdf_path: str
    rubric_path: str
    
    # Runtime
    rubric_dimensions: List[RubricDimension]
    synthesis_rules: SynthesisRule
    
    # Evidence collection - uses ior to merge dictionaries from parallel detectives
    evidences: Annotated[Dict[str, List[Evidence]], operator.ior]
    
    # Judicial opinions - uses add to append from parallel judges
    opinions: Annotated[List[JudicialOpinion], operator.add]
    
    # Output
    final_report: str
    error_log: List[str]
    
    # Tracking
    execution_metadata: Dict[str, Any]