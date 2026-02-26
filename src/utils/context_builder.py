"""
Context building utilities for routing rubric dimensions to agents.
"""

from typing import List, Dict, Any
from ..state import RubricDimension


class ContextBuilder:
    """Builds context and routes rubric dimensions to appropriate agents."""
    
    def get_dimensions_for_target(self, dimensions: List[RubricDimension], target: str) -> List[RubricDimension]:
        """
        Filter dimensions by target artifact.
        
        Args:
            dimensions: List of rubric dimensions
            target: Target artifact type (github_repo or pdf_report)
            
        Returns:
            Filtered dimensions
        """
        return [d for d in dimensions if d.target_artifact == target]
    
    def build_detective_context(self, dimension: RubricDimension) -> Dict[str, Any]:
        """
        Build context for detective agents.
        
        Args:
            dimension: Rubric dimension
            
        Returns:
            Detective context
        """
        return {
            "dimension_id": dimension.id,
            "dimension_name": dimension.name,
            "forensic_instruction": dimension.forensic_instruction,
            "target": dimension.target_artifact
        }
    
    def build_judge_context(self, dimension: RubricDimension, persona: str) -> Dict[str, Any]:
        """
        Build context for judge agents.
        
        Args:
            dimension: Rubric dimension
            persona: Judge persona
            
        Returns:
            Judge context
        """
        return {
            "dimension_id": dimension.id,
            "dimension_name": dimension.name,
            "judicial_logic": dimension.judicial_logic.get(persona.lower(), ""),
            "persona": persona
        }
    
    def build_synthesis_context(self, rubric_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build context for chief justice.
        
        Args:
            rubric_data: Full rubric data
            
        Returns:
            Synthesis context
        """
        return {
            "synthesis_rules": rubric_data.get("synthesis_rules", {}),
            "rubric_metadata": rubric_data.get("rubric_metadata", {})
        }