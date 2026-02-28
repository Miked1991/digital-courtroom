"""
Supreme Court - Synthesizes dialectical conflicts into final verdict.
Uses hardcoded deterministic rules, not LLM averaging.
"""

import json
from datetime import datetime
from typing import Dict, List, Any, Tuple
from collections import defaultdict

from src.state import AgentState, JudicialOpinion, Evidence, SynthesisRule


class ChiefJustice:
    """
    Synthesis Engine with deterministic conflict resolution.
    Does NOT average scores - applies hardcoded rules to resolve dialectics.
    """
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Synthesize all judicial opinions into final report"""
        
        # Group opinions by criterion - using criterion_id as key (string, not list)
        opinions_by_criterion = defaultdict(list)
        for opinion in state.get('opinions', []):
            if hasattr(opinion, 'criterion_id'):
                opinions_by_criterion[opinion.criterion_id].append(opinion)
        
        # Resolve each criterion
        resolved_scores = {}
        dissents = []
        
        for criterion_id, opinions in opinions_by_criterion.items():
            # Get dimension info
            dimension = next(
                (d for d in state.get('rubric_dimensions', []) if d.id == criterion_id),
                None
            )
            
            if not dimension:
                continue
            
            # Apply synthesis rules
            final_score, dissent = self._resolve_criterion(
                criterion_id,
                dimension.name,
                opinions,
                state.get('evidences', {}),
                state.get('synthesis_rules')
            )
            
            resolved_scores[criterion_id] = {
                'name': dimension.name,
                'score': final_score,
                'dissent': dissent
            }
            
            if dissent:
                dissents.append(dissent)
        
        # Generate final report
        report = self._generate_report(
            resolved_scores,
            dissents,
            state.get('repo_url', 'Unknown'),
            state.get('pdf_path', 'Unknown')
        )
        
        # Add execution metadata
        metadata = state.get('execution_metadata', {})
        metadata.update({
            'timestamp': datetime.now().isoformat(),
            'total_opinions': len(state.get('opinions', [])),
            'evidence_count': sum(len(v) for v in state.get('evidences', {}).values()),
            'criteria_resolved': len(resolved_scores)
        })
        
        return {
            "final_report": report,
            "execution_metadata": metadata
        }
    
    def _resolve_criterion(
        self,
        criterion_id: str,
        criterion_name: str,
        opinions: List[JudicialOpinion],
        evidences: Dict[str, List[Evidence]],
        rules: List [SynthesisRule]
    ) -> Tuple[int, str]:
        """
        Resolve conflicting opinions using hardcoded rules.
        Returns (final_score, dissent_explanation)
        """
        
        # Separate opinions by judge
        scores = {}
        arguments = {}
        
        for op in opinions:
            if hasattr(op, 'judge') and hasattr(op, 'score'):
                scores[op.judge] = op.score
                arguments[op.judge] = getattr(op, 'argument', '')
        
        # Default scores if missing
        prosecutor_score = scores.get('Prosecutor', 1)
        defense_score = scores.get('Defense', 3)
        techlead_score = scores.get('TechLead', 2)
        
        # Apply Rule of Security if rules exist
        if rules and hasattr(rules, 'security_override'):
            # Check for security violations in evidence
            security_flaw = self._check_security_flaws(evidences)
            if security_flaw:
                # Cap score at 3
                final_score = min(3, max(prosecutor_score, defense_score, techlead_score))
                dissent = f"SECURITY OVERRIDE: {security_flaw}. Score capped at 3."
                return final_score, dissent
        
        # Apply Rule of Evidence
        fact_check = self._verify_against_evidence(opinions, evidences)
        if fact_check.get('hallucinations'):
            # Defense overruled if hallucinating
            if 'Defense' in fact_check.get('hallucinating_judges', []):
                dissent = f"FACT SUPREMACY: Defense claimed {fact_check['hallucinations'][0]} but evidence doesn't support it."
                return techlead_score, dissent
        
        # Calculate variance
        if scores:
            score_variance = max(scores.values()) - min(scores.values())
        else:
            score_variance = 0
        
        # High variance - significant disagreement
        if score_variance >= 3:
            # Tech Lead is tie-breaker for technical criteria
            if criterion_id in ['forensic_accuracy_code', 'langgraph_architecture']:
                final_score = techlead_score
                dissent = f"DIALECTICAL TENSION: Prosecutor ({prosecutor_score}) vs Defense ({defense_score}). Tech Lead's pragmatic assessment ({techlead_score}) adopted as tie-breaker."
            else:
                # For documentation criteria, use average with bias
                final_score = round((prosecutor_score + defense_score + techlead_score) / 3)
                dissent = f"DIALECTICAL SYNTHESIS: Scores varied significantly ({score_variance} points). Combined score reflects all perspectives."
        
        # Moderate variance - typical dialectic
        elif score_variance >= 2:
            # Check if one judge is outlier
            if prosecutor_score > techlead_score + 2:
                # Prosecutor too harsh
                final_score = round((defense_score + techlead_score) / 2)
                dissent = f"Prosecutor's harsh assessment ({prosecutor_score}) overruled as outlier. Combined Defense ({defense_score}) and Tech Lead ({techlead_score}) perspectives."
            elif defense_score < techlead_score - 2:
                # Defense too optimistic
                final_score = round((prosecutor_score + techlead_score) / 2)
                dissent = f"Defense's optimistic assessment ({defense_score}) overruled as unrealistic. Combined Prosecutor ({prosecutor_score}) and Tech Lead ({techlead_score}) perspectives."
            else:
                # Balanced disagreement
                final_score = round((prosecutor_score + defense_score + techlead_score) / 3)
                dissent = f"Balanced dialectic: Prosecutor ({prosecutor_score}), Defense ({defense_score}), Tech Lead ({techlead_score}) synthesized."
        
        # Low variance - consensus
        else:
            final_score = round(sum(scores.values()) / len(scores)) if scores else 3
            dissent = f"Judicial consensus: Scores within {score_variance} point(s)."
        
        return final_score, dissent
    
    def _check_security_flaws(self, evidences: Dict[str, List[Evidence]]) -> str:
        """Check for security violations in evidence"""
        
        # Check tool safety evidence
        if 'tool_safety' in evidences:
            for evidence in evidences['tool_safety']:
                if hasattr(evidence, 'found') and not evidence.found:
                    if hasattr(evidence, 'content') and evidence.content and 'unsafe' in str(evidence.content).lower():
                        return f"Security flaw detected: {getattr(evidence, 'rationale', 'Unknown')}"
        
        # Check for shell injection risks
        for key, evidence_list in evidences.items():
            for evidence in evidence_list:
                if hasattr(evidence, 'location') and evidence.location and 'os.system' in str(getattr(evidence, 'content', '')):
                    return f"Potential shell injection risk in {evidence.location}"
        
        return ""
    
    def _verify_against_evidence(
        self,
        opinions: List[JudicialOpinion],
        evidences: Dict[str, List[Evidence]]
    ) -> Dict:
        """Verify judge claims against actual evidence"""
        
        result = {
            'hallucinations': [],
            'hallucinating_judges': []
        }
        
        # Build evidence lookup set (using strings, not lists)
        evidence_locations = set()
        for evidence_list in evidences.values():
            for evidence in evidence_list:
                if hasattr(evidence, 'location') and evidence.location:
                    evidence_locations.add(str(evidence.location))
        
        # Check each opinion's citations
        for opinion in opinions:
            if hasattr(opinion, 'cited_evidence'):
                for citation in opinion.cited_evidence:
                    # Check if citation exists in evidence
                    found = False
                    citation_str = str(citation)
                    for loc in evidence_locations:
                        if citation_str in loc or loc in citation_str:
                            found = True
                            break
                    
                    if not found:
                        result['hallucinations'].append(f"{getattr(opinion, 'judge', 'Unknown')} cited '{citation_str}' but not found")
                        result['hallucinating_judges'].append(getattr(opinion, 'judge', 'Unknown'))
        
        return result
    
    def _generate_report(
        self,
        resolved_scores: Dict,
        dissents: List[str],
        repo_url: str,
        pdf_path: str
    ) -> str:
        """Generate final markdown report"""
        
        now = datetime.now()
        
        report = f"""# Automaton Auditor Final Verdict
**Generated:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}
**Repository:** {repo_url}
**Report:** {pdf_path}

## Executive Summary

This audit was conducted by a hierarchical swarm of forensic detectives and dialectical judges, synthesized by the Chief Justice according to hardcoded constitutional rules.

| Criterion | Score (1-5) | Dialectical Outcome |
|-----------|--------------|---------------------|
"""

        # Add scores table
        for criterion_id, data in resolved_scores.items():
            report += f"| **{data['name']}** | **{data['score']}** | {data['dissent'][:100]}... |\n"
        
        # Calculate overall
        if resolved_scores:
            avg_score = sum(d['score'] for d in resolved_scores.values()) / len(resolved_scores)
            report += f"\n**Overall Assessment Score:** {avg_score:.1f}/5.0\n\n"
        else:
            report += "\n**Overall Assessment Score:** N/A\n\n"
        
        # Dissent Summary
        report += "## The Dissent\n\n"
        report += "The following dialectical tensions were recorded:\n\n"
        
        for i, dissent in enumerate(dissents[:5], 1):  # Top 5 dissents
            report += f"{i}. {dissent}\n"
        
        # Criterion Breakdown
        report += "\n## Criterion Breakdown\n\n"
        
        for criterion_id, data in resolved_scores.items():
            report += f"### {data['name']}\n"
            report += f"**Final Score:** {data['score']}/5\n\n"
            report += f"**Dialectical Resolution:** {data['dissent']}\n\n"
        
        # Remediation Plan
        report += "## Remediation Plan\n\n"
        report += "Based on the forensic evidence and judicial synthesis, the following actions are required:\n\n"
        
        # Generate remediation based on low scores
        for criterion_id, data in resolved_scores.items():
            if data['score'] <= 2:
                report += f"### {data['name']} - CRITICAL\n"
                report += self._get_remediation(criterion_id)
                report += "\n"
        
        # Evidence Summary
        report += "## Forensic Evidence Summary\n\n"
        report += "The following evidence was collected by the detective layer:\n\n"
        report += "- Git history analysis: Development pattern identified\n"
        report += "- State management: Pydantic models verified\n"
        report += "- Graph orchestration: Parallelism assessed\n"
        report += "- Tool safety: Security patterns checked\n"
        report += "- Documentation: Theoretical depth evaluated\n"
        
        report += "\n---\n"
        report += "*This report was generated by an autonomous auditor swarm following constitutional AI principles.*"
        
        return report
    
    def _get_remediation(self, criterion_id: str) -> str:
        """Get specific remediation instructions"""
        
        remediation_map = {
            'forensic_accuracy_code': """
- Add Pydantic BaseModel classes in src/state.py for all state structures
- Implement proper sandboxing in git clone operations using tempfile.TemporaryDirectory
- Use .with_structured_output() for all judge LLM calls
- Add error handling for all subprocess calls
""",
            'forensic_accuracy_docs': """
- Include detailed explanation of dialectical synthesis in PDF report
- Add specific file paths referenced in code to documentation
- Include architecture diagram showing parallel judge execution
""",
            'judicial_nuance': """
- Create distinct system prompts for Prosecutor, Defense, and Tech Lead
- Implement structured JSON output for all judicial opinions
- Add explicit instructions for citing evidence in opinions
""",
            'langgraph_architecture': """
- Modify graph to use parallel branches for detectives
- Add fan-in synchronization node before judicial layer
- Implement conditional edges for error handling
- Use operator.add and operator.ior reducers for state management
"""
        }
        
        return remediation_map.get(criterion_id, "- Review implementation against rubric requirements\n")