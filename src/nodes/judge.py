"""
Judicial layer nodes for dialectical analysis.
Each judge applies a distinct persona to evaluate evidence.
"""

from typing import Dict, List, Any
import json
import logging
import google.generativeai as genai
from dotenv import load_dotenv
import os

from ..state import AgentState, JudicialOpinion, RubricDimension

load_dotenv()
logger = logging.getLogger(__name__)


class JudgeNodes:
    """Nodes for the Judicial layer - persona-based evaluation."""
    
    def __init__(self, gemini_model: str = "gemini-1.5-pro"):
        """Initialize judges with Gemini model."""
        self.gemini_model = gemini_model
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(gemini_model)
    
    def _create_judge_prompt(
        self, 
        persona: str, 
        rubric_dimension: RubricDimension,
        evidence: Dict[str, Any]
    ) -> str:
        """
        Create persona-specific judge prompt.
        
        Args:
            persona: Judge persona (Prosecutor/Defense/TechLead)
            rubric_dimension: Rubric dimension being judged
            evidence: Collected evidence for this dimension
            
        Returns:
            Formatted prompt string
        """
        base_prompt = f"""
        You are acting as the {persona} in a Digital Courtroom for code audit.
        
        Your Core Philosophy:
        {self._get_persona_philosophy(persona)}
        
        Rubric Dimension: {rubric_dimension.name}
        ID: {rubric_dimension.id}
        
        Judicial Logic for {persona}:
        {rubric_dimension.judicial_logic.get(persona.lower(), "Apply standard judgment")}
        
        Evidence to evaluate:
        {json.dumps(evidence, indent=2, default=str)}
        
        Your task:
        1. Analyze the evidence through your persona's lens
        2. Assign a score from 1-5 based on the rubric standards
        3. Provide detailed reasoning for your score
        4. Cite specific evidence supporting your opinion
        5. Note any points of disagreement you anticipate with other judges
        
        You MUST return your opinion as a valid JSON object with exactly these fields:
        - judge: "{persona}"
        - criterion_id: "{rubric_dimension.id}"
        - score: integer between 1 and 5
        - argument: detailed string explaining your reasoning
        - cited_evidence: list of strings referencing evidence locations
        - dissent_notes: optional string noting anticipated disagreements
        
        Ensure your response contains ONLY the JSON object, no additional text.
        """
        
        return base_prompt
    
    def _get_persona_philosophy(self, persona: str) -> str:
        """Get core philosophy for each persona."""
        philosophies = {
            "Prosecutor": """
                "Trust No One. Assume Vibe Coding."
                Scrutinize evidence for gaps, security flaws, and laziness.
                Look specifically for bypassed structure and hallucination liability.
                Be harsh but fair - your job is to find what's missing.
            """,
            "Defense": """
                "Reward Effort and Intent. Look for the Spirit of the Law."
                Highlight creative workarounds, deep thought, and effort.
                Consider the engineering process and learning journey.
                Be generous but honest - your job is to see potential.
            """,
            "TechLead": """
                "Does it actually work? Is it maintainable?"
                Evaluate architectural soundness, code cleanliness, and practical viability.
                Ignore the vibe and the struggle. Focus on the artifacts.
                Be pragmatic - your job is to assess technical debt.
            """
        }
        return philosophies.get(persona, "Apply balanced judgment.")
    
    def _parse_judicial_response(self, response_text: str, persona: str, criterion_id: str) -> JudicialOpinion:
        """
        Parse and validate judge response into structured opinion.
        
        Args:
            response_text: Raw response from Gemini
            persona: Judge persona
            criterion_id: Rubric criterion ID
            
        Returns:
            Structured JudicialOpinion
        """
        try:
            # Extract JSON from response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            
            if start_idx >= 0 and end_idx > start_idx:
                json_str = response_text[start_idx:end_idx]
                data = json.loads(json_str)
            else:
                # Fallback if no JSON found
                data = {
                    "judge": persona,
                    "criterion_id": criterion_id,
                    "score": 3,
                    "argument": response_text[:500],
                    "cited_evidence": []
                }
            
            # Ensure required fields
            opinion = JudicialOpinion(
                judge=persona,
                criterion_id=data.get("criterion_id", criterion_id),
                score=int(data.get("score", 3)),
                argument=data.get("argument", "No argument provided"),
                cited_evidence=data.get("cited_evidence", []),
                dissent_notes=data.get("dissent_notes")
            )
            
            return opinion
            
        except Exception as e:
            logger.error(f"Error parsing judge response: {e}")
            # Return default opinion on error
            return JudicialOpinion(
                judge=persona,
                criterion_id=criterion_id,
                score=3,
                argument=f"Error parsing response: {str(e)}",
                cited_evidence=[]
            )
    
    def prosecutor_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Prosecutor judge node - critical lens.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with prosecutor opinions
        """
        logger.info("Running Prosecutor node")
        return self._judge_dimensions(state, "Prosecutor")
    
    def defense_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Defense judge node - optimistic lens.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with defense opinions
        """
        logger.info("Running Defense node")
        return self._judge_dimensions(state, "Defense")
    
    def tech_lead_node(self, state: AgentState) -> Dict[str, Any]:
        """
        Tech Lead judge node - pragmatic lens.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with tech lead opinions
        """
        logger.info("Running TechLead node")
        return self._judge_dimensions(state, "TechLead")
    
    def _judge_dimensions(self, state: AgentState, persona: str) -> Dict[str, Any]:
        """
        Judge all rubric dimensions from a specific persona.
        
        Args:
            state: Current agent state
            persona: Judge persona
            
        Returns:
            Updated state with opinions
        """
        opinions = []
        
        # Get aggregated evidence
        aggregated = state.get("aggregated_evidence", {})
        evidence_by_dimension = aggregated.get("evidence_by_dimension", {})
        
        # Judge each dimension
        for dimension in state["rubric_dimensions"]:
            try:
                # Get evidence for this dimension
                dim_evidence = evidence_by_dimension.get(dimension.id, [])
                
                # Convert evidence to serializable format
                evidence_list = []
                for e in dim_evidence:
                    if hasattr(e, 'dict'):
                        evidence_list.append(e.dict())
                    elif isinstance(e, dict):
                        evidence_list.append(e)
                    else:
                        evidence_list.append(str(e))
                
                # Create prompt
                prompt = self._create_judge_prompt(
                    persona, 
                    dimension,
                    {
                        "dimension_id": dimension.id,
                        "dimension_name": dimension.name,
                        "evidence": evidence_list,
                        "rubric_logic": dimension.judicial_logic
                    }
                )
                
                # Get judgment from Gemini
                response = self.model.generate_content(prompt)
                
                # Parse into structured opinion
                opinion = self._parse_judicial_response(response.text, persona, dimension.id)
                opinions.append(opinion)
                
                logger.info(f"{persona} judged {dimension.id}: score={opinion.score}")
                
            except Exception as e:
                logger.error(f"Error in {persona} judging {dimension.id}: {e}")
                # Add error opinion
                opinions.append(JudicialOpinion(
                    judge=persona,
                    criterion_id=dimension.id,
                    score=3,
                    argument=f"Error during judgment: {str(e)}",
                    cited_evidence=[]
                ))
        
        return {"opinions": opinions}