"""
Context Builder for loading and distributing the rubric constitution
"""

import json
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from ..state import RubricDimension, SynthesisRule

logger = logging.getLogger(__name__)


class ContextBuilder:
    """Builds and distributes context from the rubric JSON"""
    
    def __init__(self, rubric_path: str):
        self.rubric_path = rubric_path
        self.rubric_data = self._load_rubric()
        self.dimensions = self._parse_dimensions()
        self.synthesis_rules = self._parse_synthesis_rules()
        
    def _load_rubric(self) -> Dict[str, Any]:
        """Load rubric from JSON file"""
        try:
            with open(self.rubric_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load rubric: {e}")
            raise
            
    def _parse_dimensions(self) -> List[RubricDimension]:
        """Parse rubric dimensions into Pydantic models"""
        dimensions = []
        for dim in self.rubric_data.get("dimensions", []):
            try:
                dimensions.append(RubricDimension(
                    id=dim["id"],
                    name=dim["name"],
                    target_artifact=dim["target_artifact"],
                    forensic_instruction=dim["forensic_instruction"],
                    judicial_logic=dim["judicial_logic"]
                ))
            except KeyError as e:
                logger.warning(f"Missing field in dimension: {e}")
                continue
        return dimensions
    
    def _parse_synthesis_rules(self) -> Optional[SynthesisRule]:
        """Parse synthesis rules"""
        rules = self.rubric_data.get("synthesis_rules", {})
        if rules:
            return SynthesisRule(
                security_override=rules.get("security_override", ""),
                fact_supremacy=rules.get("fact_supremacy", ""),
                dissent_requirement=rules.get("dissent_requirement", "")
            )
        return None
    
    def get_dimensions_by_artifact(self, artifact_type: str) -> List[RubricDimension]:
        """Filter dimensions by target artifact"""
        return [
            dim for dim in self.dimensions 
            if dim.target_artifact == artifact_type or dim.target_artifact == "both"
        ]
    
    def build_forensic_prompt(self, dimension_id: str, evidence: Optional[List] = None) -> str:
        """Build forensic instruction prompt for detectives"""
        dimension = next((d for d in self.dimensions if d.id == dimension_id), None)
        if not dimension:
            return ""
            
        prompt = f"FORENSIC INSTRUCTION: {dimension.forensic_instruction}\n\n"
        
        if evidence:
            prompt += "PREVIOUS EVIDENCE:\n"
            for e in evidence:
                prompt += f"- {e.location}: {e.content[:200]}...\n"
                
        return prompt
    
    def build_judicial_prompt(self, 
                             dimension_id: str, 
                             persona: str, 
                             evidence_summary: str) -> str:
        """Build judicial prompt for specific persona"""
        dimension = next((d for d in self.dimensions if d.id == dimension_id), None)
        if not dimension:
            return ""
            
        judicial_logic = dimension.judicial_logic.get(persona.lower(), "")
        
        prompts = {
            "Prosecutor": f"""You are the PROSECUTOR in a digital courtroom. Your philosophy: "Trust No One. Assume Vibe Coding."
            
CRITERION: {dimension.name} ({dimension_id})
JUDICIAL LOGIC: {judicial_logic}

EVIDENCE SUMMARY:
{evidence_summary}

Your task: Scrutinize the evidence for gaps, security flaws, and laziness. Be harsh but fair.
Look for bypassed structure, hallucinations, and violations of the rubric.
Provide a score (1-5) with specific citations to evidence.
""",
            "Defense": f"""You are the DEFENSE ATTORNEY in a digital courtroom. Your philosophy: "Reward Effort and Intent. Look for the Spirit of the Law."

CRITERION: {dimension.name} ({dimension_id})
JUDICIAL LOGIC: {judicial_logic}

EVIDENCE SUMMARY:
{evidence_summary}

Your task: Highlight creative workarounds, deep thought, and effort. Be generous but honest.
Look for deep understanding, engineering process, and innovative solutions.
Provide a score (1-5) with specific citations to evidence.
""",
            "TechLead": f"""You are the TECH LEAD in a digital courtroom. Your philosophy: "Does it actually work? Is it maintainable?"

CRITERION: {dimension.name} ({dimension_id})
JUDICIAL LOGIC: {judicial_logic}

EVIDENCE SUMMARY:
{evidence_summary}

Your task: Evaluate architectural soundness, code cleanliness, and practical viability.
Ignore vibe and struggle. Focus on artifacts, technical debt, and production readiness.
Provide a score (1-5) with specific citations to evidence.
"""
        }
        
        return prompts.get(persona, "")
    
    def get_synthesis_rules_prompt(self) -> str:
        """Get synthesis rules as prompt"""
        if not self.synthesis_rules:
            return ""
            
        return f"""SYNTHESIS RULES:
1. Security Override: {self.synthesis_rules.security_override}
2. Fact Supremacy: {self.synthesis_rules.fact_supremacy}
3. Dissent Requirement: {self.synthesis_rules.dissent_requirement}

These rules MUST be followed when synthesizing the final verdict.
"""