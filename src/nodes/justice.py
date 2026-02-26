"""
Supreme Court node for synthesis and final verdict.
Resolves dialectical conflicts and generates final report.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import json
import logging
from collections import defaultdict

from ..state import AgentState, JudicialOpinion, Evidence

logger = logging.getLogger(__name__)


class ChiefJusticeNode:
    """Node for final synthesis and report generation."""
    
    def __init__(self):
        self.synthesis_rules = self._load_synthesis_rules()
    
    def _load_synthesis_rules(self) -> Dict[str, Any]:
        """Load synthesis rules from rubric."""
        return {
            "security_override": "Confirmed security flaws cap total score at 3",
            "fact_supremacy": "Forensic evidence overrules judicial opinion",
            "dissent_requirement": "Summarize prosecutor-defense disagreement"
        }
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """
        Synthesize final verdict from all opinions.
        
        Args:
            state: Current agent state
            
        Returns:
            Updated state with final report
        """
        logger.info("Running ChiefJustice synthesis node")
        
        # Collect all opinions
        opinions = state.get("opinions", [])
        
        if not opinions:
            return {
                "final_report": "No opinions were generated. Audit failed.",
                "synthesis_notes": "No opinions to synthesize"
            }
        
        # Group opinions by criterion
        opinions_by_criterion = defaultdict(list)
        for opinion in opinions:
            opinions_by_criterion[opinion.criterion_id].append(opinion)
        
        # Synthesize each criterion
        criterion_results = {}
        for criterion_id, criterion_opinions in opinions_by_criterion.items():
            criterion_results[criterion_id] = self._synthesize_criterion(
                criterion_id, 
                criterion_opinions,
                state.get("aggregated_evidence", {})
            )
        
        # Calculate overall score
        overall_score = self._calculate_overall_score(criterion_results)
        
        # Generate final report
        final_report = self._generate_report(
            state,
            criterion_results,
            overall_score
        )
        
        # Generate synthesis notes
        synthesis_notes = self._generate_synthesis_notes(criterion_results)
        
        return {
            "final_report": final_report,
            "synthesis_notes": synthesis_notes,
            "processing_completed": datetime.now()
        }
    
    def _synthesize_criterion(
        self, 
        criterion_id: str, 
        opinions: List[JudicialOpinion],
        evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesize opinions for a single criterion using dialectical resolution.
        
        Args:
            criterion_id: Rubric criterion ID
            opinions: List of judicial opinions
            evidence: Aggregated evidence
            
        Returns:
            Synthesized result for criterion
        """
        # Organize opinions by judge
        opinion_map = {op.judge: op for op in opinions}
        
        # Extract scores
        scores = {
            judge: op.score 
            for judge, op in opinion_map.items()
        }
        
        # Apply security override rule
        security_override = self._check_security_override(evidence, criterion_id)
        if security_override["applies"]:
            logger.info(f"Security override applied for {criterion_id}")
            final_score = min(3, max(scores.values()) if scores else 3)
            override_note = security_override["reason"]
        else:
            # Normal synthesis based on dialectical resolution
            final_score = self._resolve_scores(scores)
            override_note = None
        
        # Determine prevailing argument
        prevailing = self._get_prevailing_argument(opinion_map, final_score)
        
        # Summarize dissent
        dissent_summary = self._summarize_dissent(opinion_map)
        
        return {
            "criterion_id": criterion_id,
            "opinions": {op.judge: op.dict() for op in opinions},
            "scores": scores,
            "final_score": final_score,
            "prevailing_argument": prevailing,
            "dissent_summary": dissent_summary,
            "security_override": override_note,
            "confidence": self._calculate_confidence(opinions)
        }
    
    def _check_security_override(self, evidence: Dict[str, Any], criterion_id: str) -> Dict[str, Any]:
        """
        Check if security override should apply.
        
        Args:
            evidence: Aggregated evidence
            criterion_id: Criterion being judged
            
        Returns:
            Dict with 'applies' and 'reason'
        """
        # Look for security issues in evidence
        security_issues = []
        
        # Check tool safety evidence
        repo_evidence = evidence.get("evidence_by_dimension", {}).get("forensic_accuracy_code", [])
        
        for ev in repo_evidence:
            if isinstance(ev, Evidence) and ev.goal == "Analyze tool safety":
                if ev.found and ev.content:
                    import ast
                    try:
                        content_dict = ast.literal_eval(ev.content)
                        issues = content_dict.get("issues", [])
                        if issues:
                            security_issues.extend(issues)
                    except:
                        pass
        
        if security_issues:
            return {
                "applies": True,
                "reason": f"Security issues detected: {', '.join(security_issues[:3])}"
            }
        
        return {"applies": False, "reason": None}
    
    def _resolve_scores(self, scores: Dict[str, int]) -> int:
        """
        Resolve conflicting scores using weighted approach.
        
        Args:
            scores: Dict mapping judge to score
            
        Returns:
            Resolved score
        """
        if not scores:
            return 3
        
        # Tech Lead gets highest weight
        weights = {
            "TechLead": 0.5,
            "Prosecutor": 0.3,
            "Defense": 0.2
        }
        
        weighted_sum = 0
        total_weight = 0
        
        for judge, score in scores.items():
            weight = weights.get(judge, 0.25)
            weighted_sum += score * weight
            total_weight += weight
        
        if total_weight > 0:
            resolved = round(weighted_sum / total_weight)
        else:
            # Fallback to median
            sorted_scores = sorted(scores.values())
            resolved = sorted_scores[len(sorted_scores) // 2]
        
        return max(1, min(5, resolved))  # Clamp to 1-5
    
    def _get_prevailing_argument(self, opinion_map: Dict[str, JudicialOpinion], final_score: int) -> str:
        """
        Determine which judge's argument most closely matches the final score.
        
        Args:
            opinion_map: Map of judge to opinion
            final_score: Resolved final score
            
        Returns:
            Prevailing argument
        """
        closest_judge = None
        smallest_diff = float('inf')
        
        for judge, opinion in opinion_map.items():
            diff = abs(opinion.score - final_score)
            if diff < smallest_diff:
                smallest_diff = diff
                closest_judge = judge
        
        if closest_judge and closest_judge in opinion_map:
            return opinion_map[closest_judge].argument[:500]  # Limit length
        
        return "No prevailing argument identified"
    
    def _summarize_dissent(self, opinion_map: Dict[str, JudicialOpinion]) -> str:
        """
        Summarize points of disagreement between judges.
        
        Args:
            opinion_map: Map of judge to opinion
            
        Returns:
            Dissent summary
        """
        if "Prosecutor" in opinion_map and "Defense" in opinion_map:
            prosecutor = opinion_map["Prosecutor"]
            defense = opinion_map["Defense"]
            
            if prosecutor.score != defense.score:
                return f"Prosecutor (score {prosecutor.score}) and Defense (score {defense.score}) disagree. " \
                       f"Prosecutor: {prosecutor.argument[:100]}... Defense: {defense.argument[:100]}..."
        
        return "No significant dissent between judges."
    
    def _calculate_confidence(self, opinions: List[JudicialOpinion]) -> float:
        """
        Calculate confidence in synthesis based on opinion agreement.
        
        Args:
            opinions: List of opinions
            
        Returns:
            Confidence score 0-1
        """
        if len(opinions) < 2:
            return 0.5
        
        scores = [op.score for op in opinions]
        variance = sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores)
        
        # Lower variance = higher confidence
        confidence = 1.0 - min(1.0, variance / 4)  # Normalize
        
        return confidence
    
    def _calculate_overall_score(self, criterion_results: Dict[str, Dict]) -> float:
        """
        Calculate overall score across all criteria.
        
        Args:
            criterion_results: Results for each criterion
            
        Returns:
            Overall score (1-5)
        """
        if not criterion_results:
            return 3.0
        
        scores = [r["final_score"] for r in criterion_results.values()]
        return sum(scores) / len(scores)
    
    def _generate_report(
        self,
        state: AgentState,
        criterion_results: Dict[str, Dict],
        overall_score: float
    ) -> str:
        """
        Generate final markdown report.
        
        Args:
            state: Final agent state
            criterion_results: Synthesized results
            overall_score: Overall score
            
        Returns:
            Formatted markdown report
        """
        report_lines = []
        
        # Header
        report_lines.append("# Automaton Auditor Final Report\n")
        report_lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        report_lines.append(f"**Repository:** {state['repo_url']}")
        report_lines.append(f"**Report PDF:** {state['pdf_path']}\n")
        
        # Executive Summary
        report_lines.append("## Executive Summary\n")
        report_lines.append(f"### Overall Score: {overall_score:.1f}/5.0\n")
        
        # Summary table
        report_lines.append("| Criterion | Score | Confidence | Status |")
        report_lines.append("|-----------|-------|------------|--------|")
        
        for criterion_id, result in criterion_results.items():
            score = result["final_score"]
            confidence = result["confidence"]
            status = "✅" if score >= 4 else "⚠️" if score >= 3 else "❌"
            report_lines.append(
                f"| {criterion_id} | {score}/5 | {confidence:.0%} | {status} |"
            )
        report_lines.append("")
        
        # Criterion Breakdown
        report_lines.append("## Detailed Criterion Analysis\n")
        
        for criterion_id, result in criterion_results.items():
            report_lines.append(f"### {criterion_id}\n")
            report_lines.append(f"**Final Score:** {result['final_score']}/5\n")
            
            # Show judge opinions
            report_lines.append("#### Judicial Opinions\n")
            for judge, opinion in result["opinions"].items():
                score_symbol = "🔴" if judge == "Prosecutor" else "🟢" if judge == "Defense" else "🔵"
                report_lines.append(f"{score_symbol} **{judge}** (Score: {opinion['score']}/5)")
                report_lines.append(f"> {opinion['argument'][:200]}...")
                if opinion.get('cited_evidence'):
                    report_lines.append(f"  *Evidence: {', '.join(opinion['cited_evidence'][:3])}*")
                report_lines.append("")
            
            # Dissent summary
            if result["dissent_summary"]:
                report_lines.append("#### Dialectical Tension\n")
                report_lines.append(result["dismiss_summary"])
                report_lines.append("")
            
            # Security override if applied
            if result.get("security_override"):
                report_lines.append("#### ⚠️ Security Override Applied\n")
                report_lines.append(result["security_override"])
                report_lines.append("")
            
            report_lines.append("---\n")
        
        # Remediation Plan
        report_lines.append("## Remediation Plan\n")
        
        # Generate remediation items from low scores
        for criterion_id, result in criterion_results.items():
            if result["final_score"] < 4:
                report_lines.append(f"### Improvements for {criterion_id}\n")
                
                # Extract remediation from Tech Lead if available
                if "TechLead" in result["opinions"]:
                    tech_opinion = result["opinions"]["TechLead"]
                    report_lines.append(f"**Tech Lead Recommendation:**")
                    report_lines.append(f"> {tech_opinion['argument'][:300]}")
                    report_lines.append("")
                
                # Add specific file-level instructions
                if "cited_evidence" in result and result["cited_evidence"]:
                    report_lines.append("**Affected Files:**")
                    for evidence in result["cited_evidence"][:5]:
                        report_lines.append(f"- `{evidence}`")
                    report_lines.append("")
        
        # LangSmith trace link
        report_lines.append("## Audit Trail\n")
        report_lines.append("**Processing Timeline:**")
        report_lines.append(f"- Started: {state['processing_started'].strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"- Completed: {state['processing_completed'].strftime('%Y-%m-%d %H:%M:%S')}")
        
        if state.get("errors"):
            report_lines.append("\n**Errors Encountered:**")
            for error in state["errors"][:5]:
                report_lines.append(f"- ⚠️ {error}")
        
        if state.get("warnings"):
            report_lines.append("\n**Warnings:**")
            for warning in state["warnings"][:5]:
                report_lines.append(f"- ⚠️ {warning}")
        
        report_lines.append("\n---")
        report_lines.append("*Report generated by Automaton Auditor v2.0*")
        
        return "\n".join(report_lines)
    
    def _generate_synthesis_notes(self, criterion_results: Dict[str, Dict]) -> str:
        """
        Generate synthesis notes for traceability.
        
        Args:
            criterion_results: Synthesized results
            
        Returns:
            Synthesis notes
        """
        notes = ["# Synthesis Engine Notes\n"]
        
        for criterion_id, result in criterion_results.items():
            notes.append(f"## {criterion_id}")
            notes.append(f"Resolution Method: Weighted voting with security override")
            notes.append(f"Score Variance: {max(result['scores'].values()) - min(result['scores'].values())}")
            notes.append(f"Dialectical Quality: {'High' if result['dissent_summary'] != 'No significant dissent' else 'Low'}")
            notes.append("")
        
        return "\n".join(notes)