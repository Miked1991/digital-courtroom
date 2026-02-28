"""
Production-grade state management with Pydantic models.
Enforces strict typing and proper state reduction for parallel execution.
All models are hashable (frozen) to prevent issues with parallel processing.
"""

from typing import Annotated, Dict, List, Literal, Optional, Any, Set
from typing_extensions import TypedDict
from pydantic import BaseModel, Field, ConfigDict
import operator
from datetime import datetime
import uuid


class Evidence(BaseModel):
    """Forensic evidence collected by detectives - must be factual, no opinions."""
    model_config = ConfigDict(frozen=True)  # Immutable evidence for hashability
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # Unique ID for hashability
    goal: str = Field(description="The specific forensic goal this evidence addresses")
    found: bool = Field(description="Whether the artifact exists")
    content: Optional[str] = Field(default=None, description="The actual content found")
    location: str = Field(description="File path or commit hash where evidence was found")
    rationale: str = Field(description="Reasoning for confidence level in this evidence")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0-1")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def __hash__(self):
        """Make Evidence hashable for set operations"""
        return hash((self.id, self.goal, self.location, self.timestamp.isoformat()))


class JudicialOpinion(BaseModel):
    """Structured output from judges - must be enforced via .with_structured_output()"""
    model_config = ConfigDict(frozen=True)
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))  # Unique ID for hashability
    judge: Literal["Prosecutor", "Defense", "TechLead"]
    criterion_id: str
    score: int = Field(ge=1, le=5, description="Score from 1-5")
    argument: str = Field(description="Detailed reasoning for the score")
    cited_evidence: List[str] = Field(description="References to evidence locations")
    dissent_notes: Optional[str] = Field(default=None, description="Points of disagreement with other judges")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    def __hash__(self):
        """Make JudicialOpinion hashable for set operations"""
        return hash((self.id, self.judge, self.criterion_id, self.timestamp.isoformat()))


class RubricDimension(BaseModel):
    """Machine-readable rubric dimension from JSON"""
    model_config = ConfigDict(frozen=True)
    
    id: str
    name: str
    target_artifact: Literal["github_repo", "pdf_report"]
    forensic_instruction: str
    judicial_logic: Dict[str, str]
    
    def __hash__(self):
        """Make RubricDimension hashable"""
        return hash((self.id, self.name))


class SynthesisRule(BaseModel):
    """Hardcoded rules for the Chief Justice"""
    model_config = ConfigDict(frozen=True)
    
    security_override: str
    fact_supremacy: str
    dissent_requirement: str
    
    def __hash__(self):
        """Make SynthesisRule hashable"""
        return hash((self.security_override, self.fact_supremacy))


class AgentState(TypedDict):
    """
    State graph definition with reducers for parallel execution.
    Uses operator.ior and operator.add to prevent overwrites in parallel branches.
    All collections use immutable types where possible.
    """
    # Input
    repo_url: str
    pdf_path: str
    rubric_path: str
    
    # Runtime
    rubric_dimensions: List[RubricDimension]
    synthesis_rules: SynthesisRule
    
    # Evidence collection - uses ior to merge dictionaries from parallel detectives
    # Using Dict[str, Set[Evidence]] instead of List to prevent duplicates and improve hashability
    evidences: Annotated[Dict[str, Set[Evidence]], operator.ior]
    
    # Judicial opinions - uses add to append from parallel judges
    opinions: Annotated[List[JudicialOpinion], operator.add]
    
    # Output
    final_report: str
    error_log: Annotated[List[str], operator.add]
    
    # Tracking
    execution_metadata: Dict[str, Any]