"""
Automaton Auditor - A multi-agent system for autonomous code governance.
Uses LangGraph orchestration with Gemini models for forensic analysis.
"""

from .graph import AutomatonAuditor
from .state import AgentState, Evidence, JudicialOpinion

__version__ = "2.0.0"
__all__ = ["AutomatonAuditor", "AgentState", "Evidence", "JudicialOpinion"]