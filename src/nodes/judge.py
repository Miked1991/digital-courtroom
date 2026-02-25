"""
Judicial layer nodes - dialectical bench with three personas
Parallel execution of Prosecutor, Defense, and Tech Lead
"""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from ..state import AgentState, JudicialOpinion, EvidenceAggregation
from ..utils.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class JudgeNodes:
    """Judicial layer nodes with dialectical personas"""
    
    def __init__(self, api_keys: Dict[str, str], model: str = "gpt-4-turbo-preview"):
        self.api_keys = api_keys
        self.model = model
        self.llm = None
        self.context_builder = None
        
        # Initialize LLM
        if "openai" in api_keys:
            self.llm = ChatOpenAI(
                api_key=api_keys["openai"],
                model=model,
                temperature=0.3  # Low temperature for consistency
            )
        elif "anthropic" in api_keys:
            self.llm = ChatAnthropic(
                api_key=api_keys["anthropic"],
                model="claude-3-opus-20240229",
                temperature=0.3
            )
    
    def _ensure_context_builder(self, state: AgentState):
        """Ensure context builder is initialized"""
        if not self.context_builder and "rubric_path" in state:
            self.context_builder = ContextBuilder(state["rubric_path"])
    
    async def prosecutor_node(self, state: AgentState, config: RunnableConfig) -> Dict:
        """
        Prosecutor persona - critical lens
        Thesis in dialectical process
        """
        return await self._judge_node(state, "Prosecutor")
    
    async def defense_node(self, state: AgentState, config: RunnableConfig) -> Dict:
        """
        Defense persona - optimistic lens
        Antithesis in dialectical process
        """
        return await self._judge_node(state, "Defense")
    
    async def tech_lead_node(self, state: AgentState, config: RunnableConfig) -> Dict:
        """
        Tech Lead persona - pragmatic lens
        Tie-breaker and technical evaluator
        """
        return await self._judge_node(state, "TechLead")
    
    async def _judge_node(self, state: AgentState, persona: str) -> Dict:
        """
        Generic judge node for all personas
        Processes each criterion independently
        """
        logger.info(f"Running {persona} node")
        
        if not self.llm:
            return {"warnings": state.get("warnings", []) + [f"{persona} LLM not initialized"]}
        
        self._ensure_context_builder(state)
        
        if "aggregated_evidence" not in state or not state["aggregated_evidence"]:
            return {"warnings": state.get("warnings", []) + ["No aggregated evidence available"]}
        
        new_opinions = []
        warnings = state.get("warnings", [])
        
        # Process each criterion
        for criterion_id, agg_data in state["aggregated_evidence"].items():
            try:
                # Get dimension from context builder
                dimension = None
                if self.context_builder:
                    dimension = next(
                        (d for d in self.context_builder.dimensions if d.id == criterion_id),
                        None
                    )
                
                # Build evidence summary
                evidence_summary = self._build_evidence_summary(agg_data)
                
                # Build prompt
                if self.context_builder and dimension:
                    prompt = self.context_builder.build_judicial_prompt(
                        criterion_id, persona, evidence_summary
                    )
                else:
                    prompt = self._build_fallback_prompt(persona, criterion_id, evidence_summary)
                
                # Get structured opinion from LLM
                opinion = await self._get_structured_opinion(
                    persona, criterion_id, prompt, agg_data["evidence_list"]
                )
                
                if opinion:
                    new_opinions.append(opinion)
                
            except Exception as e:
                logger.error(f"{persona} failed for criterion {criterion_id}: {e}")
                warnings.append(f"{persona} error on {criterion_id}: {str(e)}")
        
        return {
            "opinions": new_opinions,
            "warnings": warnings
        }
    
    def _build_evidence_summary(self, agg_data: Dict) -> str:
        """Build summary of evidence for a criterion"""
        summary = agg_data.get("summary", "")
        evidence_list = agg_data.get("evidence_list", [])
        
        # Add detailed evidence
        summary += "\n\nDetailed Evidence:\n"
        for evidence in evidence_list:
            summary += f"\n--- {evidence.location} ---\n"
            summary += f"Found: {evidence.found}\n"
            summary += f"Confidence: {evidence.confidence}\n"
            if evidence.content:
                summary += f"Content: {evidence.content[:300]}...\n"
        
        # Add contradictions
        if agg_data.get("contradictions"):
            summary += "\nContradictions:\n"
            for contradiction in agg_data["contradictions"]:
                summary += f"- {contradiction}\n"
        
        return summary
    
    def _build_fallback_prompt(self, persona: str, criterion_id: str, evidence_summary: str) -> str:
        """Build fallback prompt if context builder not available"""
        base_prompts = {
            "Prosecutor": f"""You are the PROSECUTOR. Scrutinize this evidence harshly.
            Look for gaps, flaws, and violations. Score strictly (1-5).""",
            
            "Defense": f"""You are the DEFENSE ATTORNEY. Look for effort and understanding.
            Be generous but honest. Score fairly (1-5).""",
            
            "TechLead": f"""You are the TECH LEAD. Evaluate technical soundness and maintainability.
            Be pragmatic. Score realistically (1-5)."""
        }
        
        return f"""{base_prompts[persona]}

Criterion: {criterion_id}

Evidence Summary:
{evidence_summary}

Provide a JSON response with:
- score: integer 1-5
- argument: detailed reasoning
- cited_evidence: list of evidence locations cited
- confidence: float 0-1
"""
    
    async def _get_structured_opinion(self, 
                                      persona: str, 
                                      criterion_id: str, 
                                      prompt: str,
                                      evidence_list: List) -> Optional[JudicialOpinion]:
        """Get structured opinion from LLM with retry logic"""
        try:
            # Add structured output instructions
            structured_prompt = prompt + """

Return your response as a valid JSON object with exactly these fields:
{
    "score": integer between 1 and 5,
    "argument": "detailed reasoning string",
    "cited_evidence": ["location1", "location2"],
    "confidence": float between 0 and 1
}"""
            
            messages = [
                SystemMessage(content="You are a judicial AI in a digital courtroom. Return only valid JSON."),
                HumanMessage(content=structured_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON response
            try:
                # Extract JSON from response
                content = response.content
                # Find JSON boundaries
                start = content.find('{')
                end = content.rfind('}') + 1
                if start >= 0 and end > start:
                    json_str = content[start:end]
                    result = json.loads(json_str)
                else:
                    # Try to parse entire content
                    result = json.loads(content)
                
                # Create opinion
                return JudicialOpinion(
                    judge=persona,
                    criterion_id=criterion_id,
                    score=result.get("score", 3),
                    argument=result.get("argument", "No argument provided"),
                    cited_evidence=result.get("cited_evidence", []),
                    confidence=result.get("confidence", 0.7)
                )
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                # Return fallback opinion
                return JudicialOpinion(
                    judge=persona,
                    criterion_id=criterion_id,
                    score=3,
                    argument=f"Failed to parse structured output: {response.content[:200]}",
                    cited_evidence=[e.location for e in evidence_list[:2]] if evidence_list else [],
                    confidence=0.3
                )
                
        except Exception as e:
            logger.error(f"Failed to get structured opinion: {e}")
            return None