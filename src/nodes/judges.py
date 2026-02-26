"""
Dialectical judges that apply rubric criteria through distinct personas.
Each judge analyzes the SAME evidence but from different philosophical lenses.
"""

import json
from typing import Dict, List, Any
from groq import Groq
import os

from src.state import AgentState, JudicialOpinion, RubricDimension
from src.config.prompts import JudgePrompts


class Prosecutor:
    """The Critical Lens - 'Trust No One. Assume Vibe Coding.'"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = Groq(api_key=api_key or os.getenv('GROQ_API_KEY'))
        self.model = "gemma2-9b-it"  # Groq model with good reasoning
        self.prompts = JudgePrompts()
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Prosecutor's analysis of evidence for each criterion"""
        opinions = []
        
        for dimension in state['rubric_dimensions']:
            # Skip if not targeting repo (Prosecutor focuses on code)
            if dimension.target_artifact != "github_repo":
                continue
            
            # Get relevant evidence for this dimension
            relevant_evidence = self._get_relevant_evidence(state['evidences'], dimension.id)
            
            # Format evidence for LLM
            evidence_text = self._format_evidence(relevant_evidence)
            
            # Get structured opinion from LLM
            opinion = self._get_opinion(dimension, evidence_text)
            
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
                    relevant.append({
                        'type': key,
                        'evidence': evidence.model_dump()
                    })
        
        return relevant
    
    def _format_evidence(self, evidence_list: List) -> str:
        """Format evidence for LLM consumption"""
        if not evidence_list:
            return "NO EVIDENCE FOUND"
        
        lines = []
        for item in evidence_list:
            e = item['evidence']
            lines.append(f"Type: {item['type']}")
            lines.append(f"Goal: {e['goal']}")
            lines.append(f"Found: {e['found']}")
            lines.append(f"Location: {e['location']}")
            lines.append(f"Rationale: {e['rationale']}")
            lines.append(f"Confidence: {e['confidence']}")
            lines.append("---")
        
        return "\n".join(lines)
    
    def _get_opinion(self, dimension: RubricDimension, evidence_text: str) -> JudicialOpinion:
        """Get structured opinion from LLM with prosecutor lens"""
        
        prompt = self.prompts.get_prosecutor_prompt(
            dimension.name,
            dimension.judicial_logic.get('prosecutor', ''),
            evidence_text
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a strict Prosecutor. You must find violations and flaws. Be harsh but fair."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,  # Low temp for consistency
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return JudicialOpinion(
                judge="Prosecutor",
                criterion_id=dimension.id,
                score=result.get('score', 1),  # Default to harsh
                argument=result.get('argument', 'No argument provided'),
                cited_evidence=result.get('cited_evidence', []),
                dissent_notes=result.get('dissent_notes', 'Found violations in implementation')
            )
            
        except Exception as e:
            # Fallback opinion
            return JudicialOpinion(
                judge="Prosecutor",
                criterion_id=dimension.id,
                score=1,
                argument=f"Analysis failed: {str(e)}. Defaulting to score 1 due to inability to verify.",
                cited_evidence=[],
                dissent_notes="System error prevented full analysis"
            )


class Defense:
    """The Optimistic Lens - 'Reward Effort and Intent'"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = Groq(api_key=api_key or os.getenv('GROQ_API_KEY'))
        self.model = "gemma2-9b-it"
        self.prompts = JudgePrompts()
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Defense's analysis of evidence for each criterion"""
        opinions = []
        
        for dimension in state['rubric_dimensions']:
            # Defense considers both code and documentation
            relevant_evidence = self._get_relevant_evidence(state['evidences'], dimension.id)
            evidence_text = self._format_evidence(relevant_evidence)
            
            opinion = self._get_opinion(dimension, evidence_text)
            
            if opinion:
                opinions.append(opinion)
        
        return {"opinions": state['opinions'] + opinions}
    
    def _get_relevant_evidence(self, evidences: Dict, criterion_id: str) -> List[Dict]:
        """Extract evidence, focusing on effort indicators"""
        relevant = []
        
        # Include all evidence, but prioritize effort indicators
        for key, evidence_list in evidences.items():
            for evidence in evidence_list:
                relevant.append({
                    'type': key,
                    'evidence': evidence.model_dump()
                })
        
        return relevant
    
    def _format_evidence(self, evidence_list: List) -> str:
        """Format evidence, highlighting effort indicators"""
        if not evidence_list:
            return "NO EVIDENCE FOUND - This may indicate a minimal submission"
        
        lines = []
        for item in evidence_list:
            e = item['evidence']
            lines.append(f"Type: {item['type']}")
            lines.append(f"Goal: {e['goal']}")
            lines.append(f"Found: {e['found']}")
            lines.append(f"Location: {e['location']}")
            lines.append(f"Rationale: {e['rationale']}")
            lines.append(f"Confidence: {e['confidence']}")
            
            # Highlight effort indicators
            if 'commit' in e['location'] or 'history' in e['goal'].lower():
                lines.append("*** EFFORT INDICATOR: Shows development process ***")
            
            lines.append("---")
        
        return "\n".join(lines)
    
    def _get_opinion(self, dimension: RubricDimension, evidence_text: str) -> JudicialOpinion:
        """Get structured opinion from LLM with defense lens"""
        
        prompt = self.prompts.get_defense_prompt(
            dimension.name,
            dimension.judicial_logic.get('defense', ''),
            evidence_text
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a compassionate Defense Attorney. Look for effort, creativity, and understanding. Be generous."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return JudicialOpinion(
                judge="Defense",
                criterion_id=dimension.id,
                score=result.get('score', 3),  # Default to mid
                argument=result.get('argument', 'No argument provided'),
                cited_evidence=result.get('cited_evidence', []),
                dissent_notes=result.get('dissent_notes', 'Student showed good effort')
            )
            
        except Exception as e:
            return JudicialOpinion(
                judge="Defense",
                criterion_id=dimension.id,
                score=3,
                argument=f"Analysis attempted but encountered {str(e)}. Assuming good faith effort.",
                cited_evidence=[],
                dissent_notes="Benefit of the doubt applied"
            )


class TechLead:
    """The Pragmatic Lens - 'Does it actually work? Is it maintainable?'"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = Groq(api_key=api_key or os.getenv('GROQ_API_KEY'))
        self.model = "gemma2-9b-it"
        self.prompts = JudgePrompts()
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Tech Lead's analysis of evidence for each criterion"""
        opinions = []
        
        for dimension in state['rubric_dimensions']:
            # Tech Lead focuses on practical implementation
            relevant_evidence = self._get_relevant_evidence(state['evidences'], dimension.id)
            evidence_text = self._format_evidence(relevant_evidence)
            
            opinion = self._get_opinion(dimension, evidence_text)
            
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
                    relevant.append({
                        'type': key,
                        'evidence': evidence.model_dump(),
                        'priority': 'high'
                    })
        
        # Then add others
        for key, evidence_list in evidences.items():
            if key not in priority_types:
                for evidence in evidence_list:
                    relevant.append({
                        'type': key,
                        'evidence': evidence.model_dump(),
                        'priority': 'normal'
                    })
        
        return relevant
    
    def _format_evidence(self, evidence_list: List) -> str:
        """Format evidence with technical focus"""
        if not evidence_list:
            return "NO IMPLEMENTATION EVIDENCE FOUND"
        
        lines = []
        for item in evidence_list:
            e = item['evidence']
            lines.append(f"[{item.get('priority', 'normal').upper()}] Type: {item['type']}")
            lines.append(f"Goal: {e['goal']}")
            lines.append(f"Found: {e['found']}")
            lines.append(f"Location: {e['location']}")
            lines.append(f"Rationale: {e['rationale']}")
            
            # Add technical assessment
            if e['found']:
                if 'confidence' in e and e['confidence'] > 0.8:
                    lines.append("✓ TECHNICAL: Implementation appears robust")
                else:
                    lines.append("⚠ TECHNICAL: Implementation present but confidence low")
            else:
                lines.append("✗ TECHNICAL: Missing critical component")
            
            lines.append("---")
        
        return "\n".join(lines)
    
    def _get_opinion(self, dimension: RubricDimension, evidence_text: str) -> JudicialOpinion:
        """Get structured opinion from LLM with tech lead lens"""
        
        prompt = self.prompts.get_techlead_prompt(
            dimension.name,
            dimension.judicial_logic.get('tech_lead', ''),
            evidence_text
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a pragmatic Tech Lead. Evaluate if the code actually works and is maintainable. Be realistic."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1024,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return JudicialOpinion(
                judge="TechLead",
                criterion_id=dimension.id,
                score=result.get('score', 2),  # Default to realistic
                argument=result.get('argument', 'No argument provided'),
                cited_evidence=result.get('cited_evidence', []),
                dissent_notes=result.get('dissent_notes', 'Technical implementation has issues')
            )
            
        except Exception as e:
            return JudicialOpinion(
                judge="TechLead",
                criterion_id=dimension.id,
                score=2,
                argument=f"Technical evaluation incomplete due to {str(e)}. Evidence suggests implementation gaps.",
                cited_evidence=[],
                dissent_notes="Unable to fully verify technical implementation"
            )