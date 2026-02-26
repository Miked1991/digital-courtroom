 """
Production-grade state management using Pydantic models.
Enforces strict typing and proper state reduction for parallel execution.
"""

from typing import Annotated, Dict, List, Literal, Optional, Any
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, ConfigDict
import operator
from datetime import datetime


class Evidence(BaseModel):
    """Forensic evidence collected by detective agents."""
    
    model_config = ConfigDict(extra="forbid")  # Prevent arbitrary fields
    
    goal: str = Field(description="The specific forensic goal this evidence addresses")
    found: bool = Field(description="Whether the artifact exists")
    content: Optional[str] = Field(default=None, description="Extracted content or snippet")
    location: str = Field(description="File path, commit hash, or page number")
    rationale: str = Field(description="Reasoning for confidence level in this evidence")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    collected_at: datetime = Field(default_factory=datetime.now)
    artifact_type: Literal["code", "documentation", "diagram", "git_history"] = Field(
        description="Type of artifact examined"
    )


class JudicialOpinion(BaseModel):
    """Structured output from judge agents with persona-specific perspectives."""
    
    model_config = ConfigDict(extra="forbid")
    
    judge: Literal["Prosecutor", "Defense", "TechLead"] = Field(
        description="Which persona rendered this opinion"
    )
    criterion_id: str = Field(description="ID of the rubric criterion being judged")
    score: int = Field(ge=1, le=5, description="Score 1-5 based on persona's lens")
    argument: str = Field(description="Detailed reasoning for the score")
    cited_evidence: List[str] = Field(
        description="List of evidence IDs or locations supporting this opinion"
    )
    dissent_notes: Optional[str] = Field(
        default=None, 
        description="Points of disagreement with other judges"
    )


class RubricDimension(BaseModel):
    """Machine-readable rubric dimension."""
    
    model_config = ConfigDict(extra="forbid")
    
    id: str
    name: str
    target_artifact: Literal["github_repo", "pdf_report"]
    forensic_instruction: str
    judicial_logic: Dict[str, str]


class AgentState(TypedDict):
    """
    Central state for the Automaton Auditor swarm.
    Uses reducers to prevent data overwriting during parallel execution.
    """
    
    # Inputs
    repo_url: str
    pdf_path: str
    rubric_data: Dict[str, Any]
    
    # Processed rubric dimensions
    rubric_dimensions: List[RubricDimension]
    
    # Evidence collection (uses ior reducer to merge dicts from parallel detectives)
    evidences: Annotated[Dict[str, List[Evidence]], operator.ior]
    
    # Judicial opinions (uses add reducer to append from parallel judges)
    opinions: Annotated[List[JudicialOpinion], operator.add]
    
    # Aggregated data
    aggregated_evidence: Dict[str, Any]
    
    # Final outputs
    final_report: str
    synthesis_notes: str
    
    # Error tracking
    errors: Annotated[List[str], operator.add]
    warnings: Annotated[List[str], operator.add]
    
    # Processing metadata
    processing_started: datetime
    processing_completed: Optional[datetime]


class SynthesisRule(BaseModel):
    """Rules for the Chief Justice to resolve dialectical conflicts."""
    
    name: str
    condition: str
    override_behavior: Dict[str, Any]
    priority: int