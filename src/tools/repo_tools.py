"""
Repository investigation tools with AST parsing and git analysis
"""

import os
import ast
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
import shutil
from datetime import datetime

import git
from git.exc import GitCommandError
import astroid

from ..state import Evidence

logger = logging.getLogger(__name__)


class RepoInvestigator:
    """Code detective for repository analysis"""
    
    def __init__(self, temp_dir: Optional[str] = None):
        self.temp_dir = temp_dir or tempfile.mkdtemp(prefix="automaton_")
        self.repo_path: Optional[Path] = None
        
    def clone_repository(self, repo_url: str) -> Tuple[bool, Optional[str]]:
        """
        Safely clone repository into sandboxed temporary directory
        Uses tempfile for isolation
        """
        try:
            # Create unique temp directory for this clone
            self.repo_path = Path(tempfile.mkdtemp(dir=self.temp_dir))
            
            # Clone with error handling
            logger.info(f"Cloning {repo_url} to {self.repo_path}")
            repo = git.Repo.clone_from(
                repo_url, 
                str(self.repo_path),
                depth=1  # Shallow clone for efficiency
            )
            
            # Verify clone succeeded
            if not repo.head.is_valid():
                return False, "Repository cloned but has no commits"
                
            return True, str(self.repo_path)
            
        except GitCommandError as e:
            error_msg = f"Git clone failed: {e.stderr if hasattr(e, 'stderr') else str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error during clone: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def extract_git_history(self) -> List[Dict[str, Any]]:
        """Extract detailed git history with atomic commit analysis"""
        if not self.repo_path:
            return []
            
        try:
            repo = git.Repo(self.repo_path)
            commits = []
            
            for commit in repo.iter_commits():
                commits.append({
                    "hash": commit.hexsha,
                    "message": commit.message.strip(),
                    "timestamp": datetime.fromtimestamp(commit.committed_date).isoformat(),
                    "author": str(commit.author),
                    "files_changed": len(commit.stats.files),
                    "insertions": commit.stats.total['insertions'],
                    "deletions": commit.stats.total['deletions']
                })
            
            return commits
        except Exception as e:
            logger.error(f"Failed to extract git history: {e}")
            return []
    
    def analyze_commit_pattern(self, commits: List[Dict]) -> Evidence:
        """Analyze git history for atomic vs monolithic patterns"""
        if not commits:
            return Evidence(
                goal="Git Forensic Analysis",
                found=False,
                content="No commits found",
                location="git log",
                rationale="Repository has no commit history",
                confidence=0.0,
                artifact_type="git"
            )
        
        # Analyze commit pattern
        num_commits = len(commits)
        is_atomic = num_commits > 3
        
        # Check commit message progression
        messages = [c["message"].lower() for c in commits]
        has_progression = any(
            any(keyword in msg for keyword in ["setup", "init", "env"]) for msg in messages
        ) and any(
            any(keyword in msg for keyword in ["tool", "ast", "parser"]) for msg in messages
        ) and any(
            any(keyword in msg for keyword in ["graph", "orchestr", "node"]) for msg in messages
        )
        
        pattern_type = "atomic" if (is_atomic and has_progression) else "monolithic"
        confidence = 0.9 if pattern_type == "atomic" else 0.3
        
        content = f"Commit Pattern: {pattern_type}\n"
        content += f"Total Commits: {num_commits}\n"
        content += f"Progression: {'Yes' if has_progression else 'No'}\n"
        content += f"First commit: {commits[-1]['message'] if commits else 'N/A'}\n"
        content += f"Latest commit: {commits[0]['message'] if commits else 'N/A'}"
        
        return Evidence(
            goal="Git Forensic Analysis",
            found=is_atomic,
            content=content,
            location="git log --reverse",
            rationale=f"Found {num_commits} commits with {'progression' if has_progression else 'no clear progression'}",
            confidence=confidence,
            artifact_type="git"
        )
    
    def find_state_definition(self) -> Evidence:
        """Find Pydantic/TypedDict state definitions using AST"""
        if not self.repo_path:
            return self._create_not_found_evidence("State Management Rigor")
        
        # Look in common locations
        possible_files = [
            self.repo_path / "src" / "state.py",
            self.repo_path / "src" / "graph.py",
            self.repo_path / "state.py",
            self.repo_path / "graph.py"
        ]
        
        for file_path in possible_files:
            if file_path.exists():
                return self._analyze_state_file(file_path)
        
        return self._create_not_found_evidence(
            "State Management Rigor", 
            "No state.py or graph.py found in expected locations"
        )
    
    def _analyze_state_file(self, file_path: Path) -> Evidence:
        """Analyze a file for state definitions using AST"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            # Look for Pydantic BaseModel inheritance
            has_pydantic = False
            has_typeddict = False
            has_reducers = False
            evidence_fields = False
            opinion_fields = False
            
            for node in ast.walk(tree):
                # Check for class definitions
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            if base.id == "BaseModel":
                                has_pydantic = True
                            elif base.id == "TypedDict":
                                has_typeddict = True
                
                # Check for Annotated types with reducers
                if isinstance(node, ast.Subscript):
                    if hasattr(node, 'value') and isinstance(node.value, ast.Name):
                        if node.value.id == "Annotated":
                            has_reducers = True
                
                # Check for Evidence fields
                if isinstance(node, ast.ClassDef) and node.name in ["AgentState", "Evidence"]:
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign):
                            if hasattr(item.annotation, 'id'):
                                if item.annotation.id == "Evidence":
                                    evidence_fields = True
                                if item.annotation.id == "JudicialOpinion":
                                    opinion_fields = True
            
            found = has_pydantic or has_typeddict
            confidence = 0.0
            
            if found:
                confidence = 0.5
                if has_reducers:
                    confidence += 0.2
                if evidence_fields and opinion_fields:
                    confidence += 0.3
                    
            snippet = self._extract_snippet(content, ["class", "TypedDict", "BaseModel"])
            
            rationale = f"Found {'Pydantic' if has_pydantic else ''} "
            rationale += f"{'TypedDict' if has_typeddict else ''} "
            rationale += f"with reducers: {has_reducers}, "
            rationale += f"Evidence fields: {evidence_fields}, "
            rationale += f"Opinion fields: {opinion_fields}"
            
            return Evidence(
                goal="State Management Rigor",
                found=found,
                content=snippet,
                location=str(file_path),
                rationale=rationale,
                confidence=confidence,
                artifact_type="code"
            )
            
        except Exception as e:
            logger.error(f"Error analyzing state file {file_path}: {e}")
            return Evidence(
                goal="State Management Rigor",
                found=False,
                content=f"Error analyzing file: {str(e)}",
                location=str(file_path),
                rationale=f"Failed to parse AST: {str(e)}",
                confidence=0.0,
                artifact_type="code"
            )
    
    def analyze_graph_structure(self) -> Evidence:
        """Analyze StateGraph for parallelism using AST"""
        if not self.repo_path:
            return self._create_not_found_evidence("Graph Orchestration")
        
        possible_files = [
            self.repo_path / "src" / "graph.py",
            self.repo_path / "graph.py"
        ]
        
        for file_path in possible_files:
            if file_path.exists():
                return self._analyze_graph_file(file_path)
        
        return self._create_not_found_evidence("Graph Orchestration")
    
    def _analyze_graph_file(self, file_path: Path) -> Evidence:
        """Analyze graph file for parallel structure"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            has_stategraph = False
            has_add_edge = False
            has_parallel = False
            has_fan_out = False
            has_fan_in = False
            
            for node in ast.walk(tree):
                # Check for StateGraph instantiation
                if isinstance(node, ast.Call):
                    if hasattr(node.func, 'attr') and node.func.attr == "StateGraph":
                        has_stategraph = True
                    elif hasattr(node.func, 'attr') and node.func.attr == "add_edge":
                        has_add_edge = True
                
                # Check for parallel branches (multiple add_edge from same node)
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "builder":
                            has_parallel = True  # Simple heuristic
            
            # Look for specific parallel patterns
            if "add_edge" in content and "add_node" in content:
                # Count unique nodes mentioned
                nodes = set()
                lines = content.split('\n')
                for line in lines:
                    if ".add_node(" in line:
                        # Extract node name
                        start = line.find("(") + 1
                        end = line.find(")", start)
                        if start > 0 and end > start:
                            node_name = line[start:end].strip().strip("'\"")
                            nodes.add(node_name)
                
                # Check for fan-out pattern (multiple edges from aggregator)
                if "EvidenceAggregator" in content or "aggregator" in str(nodes).lower():
                    # Look for edges after aggregator
                    aggregator_lines = [i for i, line in enumerate(lines) if "aggregator" in line.lower()]
                    edge_lines = [i for i, line in enumerate(lines) if ".add_edge(" in line]
                    
                    for agg_idx in aggregator_lines:
                        following_edges = [idx for idx in edge_lines if idx > agg_idx]
                        if len(following_edges) > 1:
                            has_fan_out = True
                            break
            
            found = has_stategraph and has_add_edge
            confidence = 0.0
            
            if found:
                confidence = 0.4
                if has_parallel:
                    confidence += 0.2
                if has_fan_out:
                    confidence += 0.2
                if has_fan_in:
                    confidence += 0.2
            
            snippet = self._extract_snippet(content, ["StateGraph", "add_edge", "add_node"])
            
            rationale = f"StateGraph found: {has_stategraph}, "
            rationale += f"add_edge calls: {has_add_edge}, "
            rationale += f"parallel structure: {has_parallel}, "
            rationale += f"fan-out pattern: {has_fan_out}"
            
            return Evidence(
                goal="Graph Orchestration",
                found=found,
                content=snippet,
                location=str(file_path),
                rationale=rationale,
                confidence=confidence,
                artifact_type="code"
            )
            
        except Exception as e:
            logger.error(f"Error analyzing graph file {file_path}: {e}")
            return self._create_not_found_evidence("Graph Orchestration", str(e))
    
    def analyze_tool_safety(self) -> Evidence:
        """Analyze tools for sandboxing and security"""
        if not self.repo_path:
            return self._create_not_found_evidence("Safe Tool Engineering")
        
        tools_dir = self.repo_path / "src" / "tools"
        if not tools_dir.exists():
            return self._create_not_found_evidence("Safe Tool Engineering", "No tools directory")
        
        evidence_list = []
        for tool_file in tools_dir.glob("*.py"):
            evidence = self._analyze_tool_file(tool_file)
            evidence_list.append(evidence)
        
        # Aggregate findings
        if not evidence_list:
            return self._create_not_found_evidence("Safe Tool Engineering")
        
        # Overall assessment
        all_safe = all(e.found for e in evidence_list)
        avg_confidence = sum(e.confidence for e in evidence_list) / len(evidence_list)
        
        combined_content = "\n---\n".join([e.content for e in evidence_list if e.content])
        
        return Evidence(
            goal="Safe Tool Engineering",
            found=all_safe,
            content=combined_content,
            location=str(tools_dir),
            rationale=f"Analyzed {len(evidence_list)} tool files. All safe: {all_safe}",
            confidence=avg_confidence,
            artifact_type="code"
        )
    
    def _analyze_tool_file(self, file_path: Path) -> Evidence:
        """Analyze a single tool file for security"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            uses_tempfile = False
            has_error_handling = False
            no_os_system = True
            has_input_sanitization = False
            
            for node in ast.walk(tree):
                # Check for tempfile usage
                if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
                    if any(name.name == "tempfile" for name in node.names):
                        uses_tempfile = True
                
                # Check for try-except blocks
                if isinstance(node, ast.Try):
                    has_error_handling = True
                
                # Check for os.system calls
                if isinstance(node, ast.Call):
                    if hasattr(node.func, 'attr') and node.func.attr == "system":
                        if hasattr(node.func.value, 'id') and node.func.value.id == "os":
                            no_os_system = False
                
                # Check for input sanitization (basic check)
                if isinstance(node, ast.Call):
                    if hasattr(node.func, 'attr') and node.func.attr in ["sanitize", "validate", "escape"]:
                        has_input_sanitization = True
            
            found = uses_tempfile and has_error_handling and no_os_system
            confidence = 0.0
            
            if uses_tempfile:
                confidence += 0.3
            if has_error_handling:
                confidence += 0.3
            if no_os_system:
                confidence += 0.3
            if has_input_sanitization:
                confidence += 0.1
            
            snippet = self._extract_snippet(content, ["tempfile", "try", "except", "system"])
            
            rationale = f"Tempfile: {uses_tempfile}, "
            rationale += f"Error handling: {has_error_handling}, "
            rationale += f"No os.system: {no_os_system}, "
            rationale += f"Sanitization: {has_input_sanitization}"
            
            return Evidence(
                goal="Safe Tool Engineering",
                found=found,
                content=snippet,
                location=str(file_path),
                rationale=rationale,
                confidence=confidence,
                artifact_type="code"
            )
            
        except Exception as e:
            logger.error(f"Error analyzing tool file {file_path}: {e}")
            return Evidence(
                goal="Safe Tool Engineering",
                found=False,
                content=f"Error analyzing file: {str(e)}",
                location=str(file_path),
                rationale=f"Failed to analyze: {str(e)}",
                confidence=0.0,
                artifact_type="code"
            )
    
    def analyze_structured_output(self) -> Evidence:
        """Analyze for structured output enforcement"""
        if not self.repo_path:
            return self._create_not_found_evidence("Structured Output")
        
        judges_file = self.repo_path / "src" / "nodes" / "judges.py"
        if not judges_file.exists():
            return self._create_not_found_evidence("Structured Output", "No judges.py found")
        
        try:
            with open(judges_file, 'r') as f:
                content = f.read()
            
            tree = ast.parse(content)
            
            has_with_structured_output = False
            has_bind_tools = False
            has_pydantic_schema = False
            
            for node in ast.walk(tree):
                # Check for with_structured_output
                if isinstance(node, ast.Call):
                    if hasattr(node.func, 'attr') and node.func.attr == "with_structured_output":
                        has_with_structured_output = True
                    elif hasattr(node.func, 'attr') and node.func.attr == "bind_tools":
                        has_bind_tools = True
                
                # Check for Pydantic schema references
                if isinstance(node, ast.ClassDef):
                    for base in node.bases:
                        if isinstance(base, ast.Name) and base.id == "BaseModel":
                            if "JudicialOpinion" in node.name or "Opinion" in node.name:
                                has_pydantic_schema = True
            
            found = (has_with_structured_output or has_bind_tools) and has_pydantic_schema
            confidence = 0.0
            
            if has_with_structured_output:
                confidence += 0.4
            if has_bind_tools:
                confidence += 0.3
            if has_pydantic_schema:
                confidence += 0.3
            
            snippet = self._extract_snippet(content, ["with_structured_output", "bind_tools", "BaseModel"])
            
            return Evidence(
                goal="Structured Output",
                found=found,
                content=snippet,
                location=str(judges_file),
                rationale=f"with_structured_output: {has_with_structured_output}, "
                         f"bind_tools: {has_bind_tools}, "
                         f"Pydantic schema: {has_pydantic_schema}",
                confidence=confidence,
                artifact_type="code"
            )
            
        except Exception as e:
            logger.error(f"Error analyzing structured output: {e}")
            return self._create_not_found_evidence("Structured Output", str(e))
    
    def _extract_snippet(self, content: str, keywords: List[str], lines: int = 10) -> str:
        """Extract relevant snippet containing keywords"""
        lines_list = content.split('\n')
        relevant_indices = []
        
        for i, line in enumerate(lines_list):
            if any(keyword in line for keyword in keywords):
                relevant_indices.append(i)
        
        if not relevant_indices:
            return ""
        
        # Get context around first relevant line
        start = max(0, relevant_indices[0] - 5)
        end = min(len(lines_list), relevant_indices[0] + 5)
        
        return '\n'.join(lines_list[start:end])
    
    def _create_not_found_evidence(self, goal: str, reason: str = "Not found") -> Evidence:
        """Create evidence for not found artifacts"""
        return Evidence(
            goal=goal,
            found=False,
            content=reason,
            location="N/A",
            rationale=reason,
            confidence=0.0,
            artifact_type="code"
        )
    
    def cleanup(self):
        """Clean up temporary directory"""
        if self.repo_path and self.repo_path.exists():
            shutil.rmtree(self.repo_path, ignore_errors=True)