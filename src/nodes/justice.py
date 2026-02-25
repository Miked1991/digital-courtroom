"""
Supreme Court node - Chief Justice synthesis
Resolves dialectical conflicts and generates final report
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.runnables import RunnableConfig

from ..state import AgentState, JudicialOpinion, SynthesisRule
from ..utils.context_builder import ContextBuilder

logger = logging.getLogger(__name__)


class ChiefJusticeNode:
    """Supreme Court synthesis node"""
    
    def __init__(self, api_keys: Dict[str, str], model: str = "gpt-4-turbo-preview"):
        self.api_keys = api_keys
        self.model = model
        self.llm = None
        self.context_builder = None
        
        # Initialize LLM for report generation
        if "openai" in api_keys:
            self.llm = ChatOpenAI(
                api_key=api_keys["openai"],
                model=model,
                temperature=0.2
            )
    
    def _ensure_context_builder(self, state: AgentState):
        """Ensure context builder is initialized"""
        if not self.context_builder and "rubric_path" in state:
            self.context_builder = ContextBuilder(state["rubric_path"])
    
    async def synthesize_verdict(self, state: AgentState, config: RunnableConfig) -> Dict:
        """
        Synthesize final verdict from judicial opinions
        Applies synthesis rules and generates report
        """
        logger.info("Running ChiefJustice synthesis node")
        
        self._ensure_context_builder(state)
        
        if "opinions" not in state or not state["opinions"]:
            return {
                "final_report": "# Audit Failed\n\nNo judicial opinions were generated.",
                "remediation_plan": ["Ensure evidence collection completed successfully"],
                "warnings": state.get("warnings", []) + ["No opinions to synthesize"]
            }
        
        # Group opinions by criterion
        opinions_by_criterion = self._group_opinions(state["opinions"])
        
        # Apply synthesis rules to get final scores
        final_scores = self._apply_synthesis_rules(
            opinions_by_criterion,
            state.get("synthesis_rules"),
            state.get("aggregated_evidence", {})
        )
        
        # Generate remediation plan
        remediation_plan = self._generate_remediation_plan(
            opinions_by_criterion,
            final_scores
        )
        
        # Generate final report
        final_report = await self._generate_report(
            opinions_by_criterion,
            final_scores,
            remediation_plan,
            state
        )
        
        return {
            "criterion_scores": final_scores,
            "remediation_plan": remediation_plan,
            "final_report": final_report
        }
    
    def _group_opinions(self, opinions: List[JudicialOpinion]) -> Dict[str, List[JudicialOpinion]]:
        """Group opinions by criterion"""
        grouped = {}
        for opinion in opinions:
            if opinion.criterion_id not in grouped:
                grouped[opinion.criterion_id] = []
            grouped[opinion.criterion_id].append(opinion)
        return grouped
    
    def _apply_synthesis_rules(self, 
                               opinions_by_criterion: Dict[str, List[JudicialOpinion]],
                               synthesis_rules: Optional[SynthesisRule],
                               evidence: Dict) -> Dict[str, Dict[str, Any]]:
        """Apply synthesis rules to resolve conflicts"""
        final_scores = {}
        
        for criterion_id, opinions in opinions_by_criterion.items():
            # Calculate statistics
            scores = [o.score for o in opinions]
            avg_score = sum(scores) / len(scores)
            min_score = min(scores)
            max_score = max(scores)
            variance = max_score - min_score
            
            # Check for security override
            security_override = False
            if synthesis_rules and synthesis_rules.security_override:
                # Look for security-related evidence
                for opinion in opinions:
                    if opinion.judge == "Prosecutor":
                        if "security" in opinion.argument.lower() or "vulnerability" in opinion.argument.lower():
                            if opinion.score <= 2:
                                security_override = True
                                break
            
            # Check for fact supremacy
            fact_override = False
            fact_score = None
            if synthesis_rules and synthesis_rules.fact_supremacy and criterion_id in evidence:
                # If evidence contradicts opinions, evidence wins
                evidence_list = evidence[criterion_id].get("evidence_list", [])
                if evidence_list:
                    # Check if evidence strongly contradicts opinions
                    evidence_confidence = sum(e.confidence for e in evidence_list) / len(evidence_list)
                    if evidence_confidence > 0.8:
                        # Evidence is strong, use evidence-based score
                        evidence_based_score = 5 if all(e.found for e in evidence_list) else 1
                        fact_override = True
                        fact_score = evidence_based_score
            
            # Determine final score
            if security_override:
                final_score = min(3, max_score)  # Cap at 3
                resolution = "Security override applied"
            elif fact_override and fact_score is not None:
                final_score = fact_score
                resolution = "Fact supremacy applied - evidence overrides opinions"
            elif variance <= 1:
                # Consensus
                final_score = round(avg_score)
                resolution = "Consensus reached"
            else:
                # Significant disagreement, use Tech Lead as tie-breaker
                tech_lead_opinions = [o for o in opinions if o.judge == "TechLead"]
                if tech_lead_opinions:
                    final_score = tech_lead_opinions[0].score
                    resolution = "Tech Lead tie-breaker applied"
                else:
                    # Fallback to median
                    sorted_scores = sorted(scores)
                    final_score = sorted_scores[len(sorted_scores) // 2]
                    resolution = "Median score used due to disagreement"
            
            # Document dissent if required
            dissent = None
            if synthesis_rules and synthesis_rules.dissent_requirement and variance > 1:
                dissent = self._summarize_dissent(opinions)
            
            final_scores[criterion_id] = {
                "final_score": final_score,
                "individual_scores": {o.judge: o.score for o in opinions},
                "avg_score": avg_score,
                "variance": variance,
                "resolution": resolution,
                "dissent": dissent,
                "opinions": opinions
            }
        
        return final_scores
    
    def _summarize_dissent(self, opinions: List[JudicialOpinion]) -> str:
        """Summarize disagreement between judges"""
        prosecutor = next((o for o in opinions if o.judge == "Prosecutor"), None)
        defense = next((o for o in opinions if o.judge == "Defense"), None)
        
        if prosecutor and defense:
            return f"Prosecutor (score {prosecutor.score}): {prosecutor.argument[:100]}... vs Defense (score {defense.score}): {defense.argument[:100]}..."
        return "Disagreement between judges"
    
    def _generate_remediation_plan(self, 
                                  opinions_by_criterion: Dict[str, List[JudicialOpinion]],
                                  final_scores: Dict[str, Dict]) -> List[str]:
        """Generate actionable remediation plan"""
        remediation = []
        
        for criterion_id, score_data in final_scores.items():
            if score_data["final_score"] < 4:
                # Needs improvement
                criterion_name = criterion_id.replace('_', ' ').title()
                
                # Collect low-scoring opinions
                low_opinions = []
                for opinion in score_data["opinions"]:
                    if opinion.score < 4:
                        low_opinions.append(opinion)
                
                if low_opinions:
                    # Get most critical opinion
                    critical = min(low_opinions, key=lambda o: o.score)
                    remediation.append(f"**{criterion_name}** (Score {score_data['final_score']}):")
                    
                    # Extract actionable items from argument
                    lines = critical.argument.split('\n')
                    for line in lines:
                        if any(keyword in line.lower() for keyword in ["fix", "add", "implement", "change", "improve", "ensure"]):
                            remediation.append(f"  - {line.strip()}")
                    
                    # Add file-level suggestions
                    if critical.cited_evidence:
                        remediation.append("  Files to modify:")
                        for evidence in critical.cited_evidence[:3]:
                            remediation.append(f"    - {evidence}")
        
        if not remediation:
            remediation = ["No remediation needed - all scores 4 or above"]
        
        return remediation
    
    async def _generate_report(self,
                              opinions_by_criterion: Dict[str, List[JudicialOpinion]],
                              final_scores: Dict[str, Dict],
                              remediation_plan: List[str],
                              state: AgentState) -> str:
        """Generate final markdown report"""
        
        # Build report sections
        report = []
        
        # Header
        report.append("# Automaton Auditor Final Verdict\n")
        report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report.append(f"**Repository:** {state.get('repo_url', 'N/A')}\n")
        report.append(f"**Report:** {state.get('pdf_path', 'N/A')}\n\n")
        
        # Executive Summary
        report.append("## Executive Summary\n")
        
        avg_final_score = sum(s["final_score"] for s in final_scores.values()) / len(final_scores) if final_scores else 0
        report.append(f"**Overall Score:** {avg_final_score:.1f}/5\n\n")
        
        # Score distribution
        report.append("### Score Distribution\n")
        for criterion_id, score_data in final_scores.items():
            name = criterion_id.replace('_', ' ').title()
            report.append(f"- **{name}:** {score_data['final_score']}/5")
            if score_data.get('dissent'):
                report.append(f"  - *Dissent:* {score_data['dissent']}")
        report.append("\n")
        
        # Criterion Breakdown
        report.append("## Criterion Breakdown\n")
        
        for criterion_id, score_data in final_scores.items():
            name = criterion_id.replace('_', ' ').title()
            report.append(f"### {name}\n")
            report.append(f"**Final Score:** {score_data['final_score']}/5\n")
            report.append(f"**Resolution:** {score_data['resolution']}\n\n")
            
            report.append("**Individual Opinions:**\n")
            for opinion in score_data["opinions"]:
                report.append(f"- **{opinion.judge}** (Score: {opinion.score}, Confidence: {opinion.confidence:.1f})")
                report.append(f"  - {opinion.argument[:200]}...")
                if opinion.cited_evidence:
                    report.append(f"  - *Cited:* {', '.join(opinion.cited_evidence[:2])}")
                report.append("")
            
            report.append("")
        
        # Remediation Plan
        report.append("## Remediation Plan\n")
        for item in remediation_plan:
            report.append(item)
        report.append("")
        
        # Evidence Summary
        report.append("## Evidence Summary\n")
        if "aggregated_evidence" in state:
            for criterion_id, agg_data in state["aggregated_evidence"].items():
                name = criterion_id.replace('_', ' ').title()
                report.append(f"### {name} Evidence\n")
                for evidence in agg_data.get("evidence_list", [])[:3]:
                    status = "✅" if evidence.found else "❌"
                    report.append(f"- {status} **{evidence.location}** (Confidence: {evidence.confidence:.1f})")
                    report.append(f"  - {evidence.rationale}")
                if len(agg_data.get("evidence_list", [])) > 3:
                    report.append(f"  - *...and {len(agg_data['evidence_list']) - 3} more*")
                report.append("")
        
        # Warnings
        if state.get("warnings"):
            report.append("## Warnings & Limitations\n")
            for warning in state["warnings"]:
                report.append(f"- ⚠️ {warning}")
        
        return '\n'.join(report)