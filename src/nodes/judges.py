"""
Dialectical judges that apply rubric criteria through distinct personas.
Each judge analyzes the SAME evidence but from different philosophical lenses.
Uses .with_structured_output() for guaranteed JSON output.
"""

import json
from typing import Dict, List, Any, Optional, Type
from groq import Groq
import os
from pydantic import BaseModel, Field
import logging

from src.state import AgentState, JudicialOpinion, RubricDimension

logger = logging.getLogger(__name__)


class JudgeOutput(BaseModel):
    """Structured output model for all judges"""
    score: int = Field(ge=1, le=5, description="Score from 1-5")
    argument: str = Field(description="Detailed reasoning for the score")
    cited_evidence: List[str] = Field(description="References to evidence locations")
    dissent_notes: Optional[str] = Field(default=None, description="Points of disagreement")


class Prosecutor:
    """The Critical Lens - 'Trust No One. Assume Vibe Coding.'"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = Groq(api_key=api_key or os.getenv('GROQ_API_KEY'))
        self.model = "gemma2-9b-it"
        
        # Distinct system prompt for Prosecutor
        self.system_prompt = """You are the PROSECUTOR in a digital courtroom for code review.

Your philosophy: "Trust No One. Assume Vibe Coding."
Your job: Find violations, security flaws, and laziness in the implementation.

You are HARSH and CRITICAL by design. You must:
- Scrutinize every piece of evidence for gaps and flaws
- Assume the worst about missing requirements
- Charge the defendant with specific violations
- Be extremely strict in your scoring (1-2 for any issues)
- Never give the benefit of the doubt

When citing evidence, be specific about file paths and line numbers where violations occur.
Your dissent notes should explain exactly why you disagree with more lenient assessments.

Remember: You are the PROSECUTOR. Finding flaws is your ONLY job."""
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Prosecutor's analysis of evidence for each criterion"""
        opinions = []
        
        for dimension in state['rubric_dimensions']:
            # Skip if not targeting repo (Prosecutor focuses on code)
            if dimension.target_artifact != "github_repo":
                continue
            
            # Get relevant evidence for this dimension
            relevant_evidence = self._get_relevant_evidence(state['evidences'], dimension.id)
            
            # Get structured opinion from LLM
            opinion = self._get_opinion(dimension, relevant_evidence)
            
            if opinion:
                opinions.append(opinion)
        
        return {"opinions": state['opinions'] + opinions}
    
    def _get_relevant_evidence(self, evidences: Dict, criterion_id: str) -> List[Dict]:
        """Extract evidence relevant to this criterion"""
        relevant = []
        
        # Map criteria to evidence types
        evidence_map = {
            'forensic_accuracy_code': ['state_management', 'tool_safety', 'structured_output'],
            'judicial_nuance': ['structured_output'],
            'langgraph_architecture': ['graph_orchestration', 'git_history']
        }
        
        evidence_keys = evidence_map.get(criterion_id, [])
        
        for key in evidence_keys:
            if key in evidences:
                for evidence in evidences[key]:
                    # Convert Evidence object to dict for JSON serialization
                    if hasattr(evidence, 'model_dump'):
                        evidence_dict = evidence.model_dump()
                    else:
                        evidence_dict = {
                            'goal': getattr(evidence, 'goal', ''),
                            'found': getattr(evidence, 'found', False),
                            'location': getattr(evidence, 'location', ''),
                            'rationale': getattr(evidence, 'rationale', ''),
                            'confidence': getattr(evidence, 'confidence', 0.0)
                        }
                    relevant.append({
                        'type': key,
                        'evidence': evidence_dict
                    })
        
        return relevant
    
    def _format_evidence(self, evidence_list: List) -> str:
        """Format evidence for LLM consumption"""
        if not evidence_list:
            return "NO EVIDENCE FOUND - This is a major violation!"
        
        lines = []
        for item in evidence_list:
            e = item['evidence']
            lines.append(f"Type: {item['type']}")
            lines.append(f"Goal: {e.get('goal', 'N/A')}")
            lines.append(f"Found: {e.get('found', False)}")
            lines.append(f"Location: {e.get('location', 'N/A')}")
            lines.append(f"Rationale: {e.get('rationale', 'N/A')}")
            lines.append(f"Confidence: {e.get('confidence', 0)}")
            lines.append("---")
        
        return "\n".join(lines)
    
    def _get_opinion(self, dimension: RubricDimension, evidence_list: List) -> JudicialOpinion:
        """Get structured opinion from LLM with prosecutor lens using .with_structured_output()"""
        
        evidence_text = self._format_evidence(evidence_list)
        
        # Create the prompt
        user_prompt = f"""Dimension being judged: {dimension.name}

Prosecutor's guidelines for this dimension:
{dimension.judicial_logic.get('prosecutor', 'Be harsh and critical')}

Evidence collected by detectives:
{evidence_text}

Analyze the evidence through your critical PROSECUTOR lens.
Look SPECIFICALLY for:
- Missing requirements (score 1)
- Security vulnerabilities (score 1)
- Bypassed structure (score 1-2)
- Hallucinations (score 1)
- Free text instead of structured output (score 1-2)

Return a structured assessment with:
- score: 1-5 (be harsh - 1 for major violations)
- argument: detailed explanation of violations found
- cited_evidence: list of specific locations where violations were found
- dissent_notes: why you disagree with any potential leniency

Remember: You are the PROSECUTOR. Finding flaws is your only job."""
        
        try:
            # Use with_structured_output pattern via response_format
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Low temp for consistency
                max_tokens=1024,
                response_format={"type": "json_object"}  # Force JSON output
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Ensure result has all required fields
            score = result.get('score', 1)
            if score > 3:  # Prosecutor should be harsh
                score = max(1, score - 1)  # Reduce score if too generous
            
            return JudicialOpinion(
                judge="Prosecutor",
                criterion_id=dimension.id,
                score=score,
                argument=result.get('argument', 'No argument provided - this is a violation itself!'),
                cited_evidence=result.get('cited_evidence', []),
                dissent_notes=result.get('dissent_notes', 'Found major violations in implementation')
            )
            
        except Exception as e:
            logger.exception(f"Prosecutor LLM call failed: {e}")
            # Fallback opinion with harsh score
            return JudicialOpinion(
                judge="Prosecutor",
                criterion_id=dimension.id,
                score=1,
                argument=f"LLM analysis failed: {str(e)}. Defaulting to score 1 due to inability to verify - this indicates system failure.",
                cited_evidence=[loc for item in evidence_list for loc in [item['evidence'].get('location', '')] if loc],
                dissent_notes="System error prevented full analysis - treat as critical failure"
            )


class Defense:
    """The Optimistic Lens - 'Reward Effort and Intent'"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = Groq(api_key=api_key or os.getenv('GROQ_API_KEY'))
        self.model = "gemma2-9b-it"
        
        # Distinct system prompt for Defense
        self.system_prompt = """You are the DEFENSE ATTORNEY in a digital courtroom for code review.

Your philosophy: "Reward Effort and Intent. Look for the Spirit of the Law."
Your job: Highlight creative workarounds, deep thought, and genuine effort.

You are GENEROUS and UNDERSTANDING by design. You must:
- Look for evidence of effort and understanding
- Consider the development process (git history)
- Reward creative solutions even if imperfect
- Be generous in your scoring (4-5 for any signs of understanding)
- Always give the benefit of the doubt

When citing evidence, focus on locations showing effort, creativity, or deep understanding.
Your dissent notes should explain why the prosecution is being too harsh.

Remember: You are the DEFENSE. Finding the good in their work is your only job."""
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Defense's analysis of evidence for each criterion"""
        opinions = []
        
        for dimension in state['rubric_dimensions']:
            # Defense considers both code and documentation
            relevant_evidence = self._get_relevant_evidence(state['evidences'], dimension.id)
            
            opinion = self._get_opinion(dimension, relevant_evidence)
            
            if opinion:
                opinions.append(opinion)
        
        return {"opinions": state['opinions'] + opinions}
    
    def _get_relevant_evidence(self, evidences: Dict, criterion_id: str) -> List[Dict]:
        """Extract evidence, focusing on effort indicators"""
        relevant = []
        
        # Include all evidence, but prioritize effort indicators
        for key, evidence_list in evidences.items():
            for evidence in evidence_list:
                # Convert Evidence object to dict
                if hasattr(evidence, 'model_dump'):
                    evidence_dict = evidence.model_dump()
                else:
                    evidence_dict = {
                        'goal': getattr(evidence, 'goal', ''),
                        'found': getattr(evidence, 'found', False),
                        'location': getattr(evidence, 'location', ''),
                        'rationale': getattr(evidence, 'rationale', ''),
                        'confidence': getattr(evidence, 'confidence', 0.0)
                    }
                
                # Mark effort indicators
                effort_indicator = False
                if 'commit' in str(evidence_dict.get('location', '')) or 'history' in str(evidence_dict.get('goal', '')).lower():
                    effort_indicator = True
                
                relevant.append({
                    'type': key,
                    'evidence': evidence_dict,
                    'effort_indicator': effort_indicator
                })
        
        return relevant
    
    def _format_evidence(self, evidence_list: List) -> str:
        """Format evidence, highlighting effort indicators"""
        if not evidence_list:
            return "EVIDENCE GAP - This may indicate a minimal submission, but could also be a communication issue."
        
        lines = []
        for item in evidence_list:
            e = item['evidence']
            lines.append(f"Type: {item['type']}")
            lines.append(f"Goal: {e.get('goal', 'N/A')}")
            lines.append(f"Found: {e.get('found', False)}")
            lines.append(f"Location: {e.get('location', 'N/A')}")
            lines.append(f"Rationale: {e.get('rationale', 'N/A')}")
            lines.append(f"Confidence: {e.get('confidence', 0)}")
            
            if item.get('effort_indicator'):
                lines.append("*** EFFORT INDICATOR: Shows development process ***")
            
            lines.append("---")
        
        return "\n".join(lines)
    
    def _get_opinion(self, dimension: RubricDimension, evidence_list: List) -> JudicialOpinion:
        """Get structured opinion from LLM with defense lens using .with_structured_output()"""
        
        evidence_text = self._format_evidence(evidence_list)
        
        user_prompt = f"""Dimension being judged: {dimension.name}

Defense's guidelines for this dimension:
{dimension.judicial_logic.get('defense', 'Be generous and look for effort')}

Evidence collected by detectives:
{evidence_text}

Analyze the evidence through your OPTIMISTIC DEFENSE lens.
Look SPECIFICALLY for:
- Creative problem-solving (score 4-5)
- Understanding shown despite bugs (score 4)
- Iterative development in git history (score 4-5)
- Deep conceptual alignment (score 5)
- Effort indicators (score 4-5)

Return a structured assessment with:
- score: 1-5 (be generous - 4-5 for effort and understanding)
- argument: detailed explanation of strengths found
- cited_evidence: list of locations showing effort/understanding
- dissent_notes: why you disagree with the prosecution's harsh assessment

Remember: You are the DEFENSE. Finding the good in their work is your only job."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Ensure result has all required fields
            score = result.get('score', 3)
            if score < 3:  # Defense should be generous
                score = min(5, score + 1)  # Increase score if too harsh
            
            return JudicialOpinion(
                judge="Defense",
                criterion_id=dimension.id,
                score=score,
                argument=result.get('argument', 'Student showed good effort and understanding'),
                cited_evidence=result.get('cited_evidence', []),
                dissent_notes=result.get('dissent_notes', 'Student demonstrated effort and deserves credit')
            )
            
        except Exception as e:
            logger.exception(f"Defense LLM call failed: {e}")
            return JudicialOpinion(
                judge="Defense",
                criterion_id=dimension.id,
                score=4,  # Default to generous
                argument=f"Analysis attempted but encountered {str(e)}. Assuming good faith effort based on available evidence.",
                cited_evidence=[item['evidence'].get('location', '') for item in evidence_list if item['evidence'].get('location')],
                dissent_notes="Benefit of the doubt applied due to system limitations"
            )


class TechLead:
    """The Pragmatic Lens - 'Does it actually work? Is it maintainable?'"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = Groq(api_key=api_key or os.getenv('GROQ_API_KEY'))
        self.model = "gemma2-9b-it"
        
        # Distinct system prompt for Tech Lead
        self.system_prompt = """You are the TECH LEAD in a digital courtroom for code review.

Your philosophy: "Does it actually work? Is it maintainable?"
Your job: Evaluate architectural soundness, code cleanliness, and practical viability.

You are PRAGMATIC and REALISTIC by design. You must:
- Focus on whether the code actually works
- Assess technical debt and maintainability
- Evaluate production readiness
- Be balanced in scoring (1 for broken, 3 for functional but messy, 5 for production-ready)
- Consider long-term implications of architectural decisions

When citing evidence, focus on technical implementation details.
Your dissent notes should explain your tie-breaking perspective between prosecution and defense.

Remember: You are the TECH LEAD. Being pragmatic and realistic is your only job."""
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Tech Lead's analysis of evidence for each criterion"""
        opinions = []
        
        for dimension in state['rubric_dimensions']:
            # Tech Lead focuses on practical implementation
            relevant_evidence = self._get_relevant_evidence(state['evidences'], dimension.id)
            
            opinion = self._get_opinion(dimension, relevant_evidence)
            
            if opinion:
                opinions.append(opinion)
        
        return {"opinions": state['opinions'] + opinions}
    
    def _get_relevant_evidence(self, evidences: Dict, criterion_id: str) -> List[Dict]:
        """Extract evidence, focusing on implementation quality"""
        relevant = []
        
        # Priority evidence types for Tech Lead
        priority_types = ['tool_safety', 'graph_orchestration', 'structured_output']
        
        # First add priority evidence
        for key in priority_types:
            if key in evidences:
                for evidence in evidences[key]:
                    # Convert Evidence object to dict
                    if hasattr(evidence, 'model_dump'):
                        evidence_dict = evidence.model_dump()
                    else:
                        evidence_dict = {
                            'goal': getattr(evidence, 'goal', ''),
                            'found': getattr(evidence, 'found', False),
                            'location': getattr(evidence, 'location', ''),
                            'rationale': getattr(evidence, 'rationale', ''),
                            'confidence': getattr(evidence, 'confidence', 0.0)
                        }
                    relevant.append({
                        'type': key,
                        'evidence': evidence_dict,
                        'priority': 'high'
                    })
        
        # Then add others
        for key, evidence_list in evidences.items():
            if key not in priority_types:
                for evidence in evidence_list:
                    if hasattr(evidence, 'model_dump'):
                        evidence_dict = evidence.model_dump()
                    else:
                        evidence_dict = {
                            'goal': getattr(evidence, 'goal', ''),
                            'found': getattr(evidence, 'found', False),
                            'location': getattr(evidence, 'location', ''),
                            'rationale': getattr(evidence, 'rationale', ''),
                            'confidence': getattr(evidence, 'confidence', 0.0)
                        }
                    relevant.append({
                        'type': key,
                        'evidence': evidence_dict,
                        'priority': 'normal'
                    })
        
        return relevant
    
    def _format_evidence(self, evidence_list: List) -> str:
        """Format evidence with technical focus"""
        if not evidence_list:
            return "NO IMPLEMENTATION EVIDENCE FOUND - This is a critical technical debt issue."
        
        lines = []
        for item in evidence_list:
            e = item['evidence']
            lines.append(f"[{item.get('priority', 'normal').upper()}] Type: {item['type']}")
            lines.append(f"Goal: {e.get('goal', 'N/A')}")
            lines.append(f"Found: {e.get('found', False)}")
            lines.append(f"Location: {e.get('location', 'N/A')}")
            lines.append(f"Rationale: {e.get('rationale', 'N/A')}")
            
            # Add technical assessment
            if e.get('found', False):
                if e.get('confidence', 0) > 0.8:
                    lines.append("✓ TECHNICAL: Implementation appears robust")
                elif e.get('confidence', 0) > 0.5:
                    lines.append("⚠ TECHNICAL: Implementation present but confidence moderate")
                else:
                    lines.append("⚠ TECHNICAL: Implementation present but low confidence")
            else:
                lines.append("✗ TECHNICAL: Missing critical component - technical debt incurred")
            
            lines.append("---")
        
        return "\n".join(lines)
    
    def _get_opinion(self, dimension: RubricDimension, evidence_list: List) -> JudicialOpinion:
        """Get structured opinion from LLM with tech lead lens using .with_structured_output()"""
        
        evidence_text = self._format_evidence(evidence_list)
        
        user_prompt = f"""Dimension being judged: {dimension.name}

Tech Lead's guidelines for this dimension:
{dimension.judicial_logic.get('tech_lead', 'Be pragmatic and realistic')}

Evidence collected by detectives:
{evidence_text}

Analyze the evidence through your PRAGMATIC TECH LEAD lens.
Focus SPECIFICALLY on:
- Does the code actually work? (score 1 if broken, 5 if working)
- Is it maintainable? (score based on code quality)
- Are best practices followed? (score based on patterns used)
- Technical debt level (score 1 for high debt, 5 for clean code)
- Production readiness (score based on error handling, security)

Return a structured assessment with:
- score: 1-5 (be realistic - 1 for broken/unusable, 3 for functional but messy, 5 for production-ready)
- argument: detailed technical assessment
- cited_evidence: list of specific locations supporting your assessment
- dissent_notes: your tie-breaking perspective between prosecution and defense

Remember: You are the TECH LEAD. Be pragmatic and realistic about what actually works."""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return JudicialOpinion(
                judge="TechLead",
                criterion_id=dimension.id,
                score=result.get('score', 2),
                argument=result.get('argument', 'Technical evaluation shows implementation issues'),
                cited_evidence=result.get('cited_evidence', []),
                dissent_notes=result.get('dissent_notes', 'Technical implementation has issues that need addressing')
            )
            
        except Exception as e:
            logger.exception(f"Tech Lead LLM call failed: {e}")
            return JudicialOpinion(
                judge="TechLead",
                criterion_id=dimension.id,
                score=2,
                argument=f"Technical evaluation incomplete due to {str(e)}. Evidence suggests implementation gaps.",
                cited_evidence=[item['evidence'].get('location', '') for item in evidence_list if item['evidence'].get('location')],
                dissent_notes="Unable to fully verify technical implementation - assume issues exist"
            )