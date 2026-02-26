"""
Forensic code analysis tools using AST parsing and git history analysis.
"""

import ast
import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import git
from git.exc import GitCommandError, InvalidGitRepositoryError
import logging

from ..state import Evidence

logger = logging.getLogger(__name__)


class RepoInvestigatorTools:
    """Production-grade tools for repository forensic analysis."""
    
    def __init__(self, sandbox_dir: Optional[str] = None):
        self.sandbox_dir = sandbox_dir or tempfile.mkdtemp(prefix="audit_")
        self.repo_path: Optional[Path] = None
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cleanup sandbox directory."""
        if self.sandbox_dir and os.path.exists(self.sandbox_dir):
            shutil.rmtree(self.sandbox_dir, ignore_errors=True)
    
    def clone_repository(self, repo_url: str, branch: str = "main") -> Evidence:
        """
        Safely clone a repository in a sandboxed environment.
        
        Args:
            repo_url: GitHub repository URL
            branch: Branch to clone
            
        Returns:
            Evidence object with clone results
        """
        try:
            # Validate URL format
            if not repo_url.startswith(("https://github.com/", "git@github.com:")):
                return Evidence(
                    goal="Clone repository for analysis",
                    found=False,
                    content=None,
                    location="N/A",
                    rationale=f"Invalid repository URL format: {repo_url}",
                    confidence=1.0,
                    artifact_type="code"
                )
            
            # Sanitize URL to prevent injection
            repo_url = repo_url.strip()
            
            # Clone into sandbox
            repo_path = Path(self.sandbox_dir) / "repo"
            repo = git.Repo.clone_from(
                repo_url, 
                repo_path,
                branch=branch,
                depth=1  # Shallow clone for efficiency
            )
            
            self.repo_path = repo_path
            
            return Evidence(
                goal="Clone repository for analysis",
                found=True,
                content=f"Successfully cloned to {repo_path}",
                location=str(repo_path),
                rationale="Repository cloned successfully in sandboxed environment",
                confidence=1.0,
                artifact_type="code"
            )
            
        except GitCommandError as e:
            return Evidence(
                goal="Clone repository for analysis",
                found=False,
                content=None,
                location="N/A",
                rationale=f"Git command error: {str(e)}",
                confidence=1.0,
                artifact_type="code"
            )
        except Exception as e:
            return Evidence(
                goal="Clone repository for analysis",
                found=False,
                content=None,
                location="N/A",
                rationale=f"Unexpected error: {str(e)}",
                confidence=0.9,
                artifact_type="code"
            )
    
    def analyze_git_history(self) -> Evidence:
        """
        Extract and analyze git commit history for forensic evidence.
        
        Returns:
            Evidence with commit history analysis
        """
        if not self.repo_path or not Path(self.repo_path).exists():
            return Evidence(
                goal="Analyze git commit history",
                found=False,
                content=None,
                location="N/A",
                rationale="No repository available for analysis",
                confidence=0.0,
                artifact_type="git_history"
            )
        
        try:
            repo = git.Repo(self.repo_path)
            
            # Get commit history
            commits = list(repo.iter_commits(max_count=20))
            
            commit_data = []
            for i, commit in enumerate(reversed(commits)):
                commit_data.append({
                    "hash": commit.hexsha[:8],
                    "message": commit.message.strip(),
                    "author": str(commit.author),
                    "date": commit.committed_datetime.isoformat(),
                    "files_changed": len(commit.stats.files) if commit.stats else 0
                })
            
            # Analyze patterns
            is_atomic = len(commits) > 3
            has_progression = self._check_commit_progression(commit_data)
            
            content = {
                "total_commits": len(commits),
                "commits": commit_data,
                "patterns": {
                    "is_atomic": is_atomic,
                    "has_progression": has_progression,
                    "commit_frequency": len(commits) / 30 if len(commits) > 0 else 0
                }
            }
            
            rationale = f"Found {len(commits)} commits. "
            if is_atomic and has_progression:
                rationale += "Shows atomic progression with meaningful commit history."
            else:
                rationale += "Limited commit history detected."
            
            return Evidence(
                goal="Analyze git commit history",
                found=True,
                content=str(content),
                location="git log",
                rationale=rationale,
                confidence=0.95 if len(commits) > 0 else 0.5,
                artifact_type="git_history"
            )
            
        except Exception as e:
            return Evidence(
                goal="Analyze git commit history",
                found=False,
                content=None,
                location="N/A",
                rationale=f"Error analyzing git history: {str(e)}",
                confidence=0.7,
                artifact_type="git_history"
            )
    
    def _check_commit_progression(self, commits: List[Dict]) -> bool:
        """Check if commits show logical progression."""
        if len(commits) < 2:
            return False
        
        # Look for typical progression patterns
        patterns = ["init", "setup", "add", "implement", "fix", "test", "refactor"]
        messages = [c["message"].lower() for c in commits]
        
        # Check if messages follow a logical order
        found_patterns = []
        for msg in messages:
            for pattern in patterns:
                if pattern in msg and pattern not in found_patterns:
                    found_patterns.append(pattern)
        
        return len(found_patterns) >= 2
    
    def analyze_state_definition(self) -> Evidence:
        """
        Scan for Pydantic state models using AST parsing.
        
        Returns:
            Evidence with state definition analysis
        """
        if not self.repo_path:
            return Evidence(
                goal="Analyze state definitions",
                found=False,
                content=None,
                location="N/A",
                rationale="No repository path available",
                confidence=0.0,
                artifact_type="code"
            )
        
        try:
            # Look for state.py or graph.py
            state_files = [
                self.repo_path / "src" / "state.py",
                self.repo_path / "src" / "graph.py",
                self.repo_path / "state.py",
                self.repo_path / "graph.py"
            ]
            
            for file_path in state_files:
                if file_path.exists():
                    return self._parse_python_file_for_state(file_path)
            
            return Evidence(
                goal="Analyze state definitions",
                found=False,
                content=None,
                location="N/A",
                rationale="No state.py or graph.py found with state definitions",
                confidence=0.8,
                artifact_type="code"
            )
            
        except Exception as e:
            return Evidence(
                goal="Analyze state definitions",
                found=False,
                content=None,
                location="N/A",
                rationale=f"Error analyzing state: {str(e)}",
                confidence=0.6,
                artifact_type="code"
            )
    
    def _parse_python_file_for_state(self, file_path: Path) -> Evidence:
        """Parse Python file using AST to find Pydantic models."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        pydantic_models = []
        typed_dicts = []
        
        for node in ast.walk(tree):
            # Find class definitions
            if isinstance(node, ast.ClassDef):
                # Check for BaseModel inheritance
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == "BaseModel":
                        pydantic_models.append({
                            "name": node.name,
                            "line": node.lineno,
                            "fields": self._extract_class_fields(node)
                        })
                    elif isinstance(base, ast.Attribute) and base.attr == "BaseModel":
                        pydantic_models.append({
                            "name": node.name,
                            "line": node.lineno,
                            "fields": self._extract_class_fields(node)
                        })
                
                # Check for TypedDict
                for decorator in node.decorator_list:
                    if isinstance(decorator, ast.Name) and decorator.id == "TypedDict":
                        typed_dicts.append({
                            "name": node.name,
                            "line": node.lineno,
                            "fields": self._extract_class_fields(node)
                        })
        
        found_models = pydantic_models + typed_dicts
        
        if found_models:
            return Evidence(
                goal="Analyze state definitions",
                found=True,
                content=str({
                    "pydantic_models": pydantic_models,
                    "typed_dicts": typed_dicts
                }),
                location=str(file_path),
                rationale=f"Found {len(pydantic_models)} Pydantic models and {len(typed_dicts)} TypedDicts",
                confidence=0.95,
                artifact_type="code"
            )
        else:
            return Evidence(
                goal="Analyze state definitions",
                found=False,
                content=None,
                location=str(file_path),
                rationale="No Pydantic models or TypedDicts found",
                confidence=0.9,
                artifact_type="code"
            )
    
    def _extract_class_fields(self, class_node: ast.ClassDef) -> List[str]:
        """Extract field names from a class definition."""
        fields = []
        for node in class_node.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                fields.append(node.target.id)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        fields.append(target.id)
        return fields
    
    def analyze_graph_orchestration(self) -> Evidence:
        """
        Analyze StateGraph definition for parallel execution patterns.
        
        Returns:
            Evidence with graph orchestration analysis
        """
        if not self.repo_path:
            return Evidence(
                goal="Analyze graph orchestration",
                found=False,
                content=None,
                location="N/A",
                rationale="No repository path available",
                confidence=0.0,
                artifact_type="code"
            )
        
        try:
            # Look for graph.py or main graph definition
            graph_files = [
                self.repo_path / "src" / "graph.py",
                self.repo_path / "graph.py",
                self.repo_path / "src" / "main.py"
            ]
            
            for file_path in graph_files:
                if file_path.exists():
                    return self._parse_graph_file(file_path)
            
            return Evidence(
                goal="Analyze graph orchestration",
                found=False,
                content=None,
                location="N/A",
                rationale="No graph definition files found",
                confidence=0.7,
                artifact_type="code"
            )
            
        except Exception as e:
            return Evidence(
                goal="Analyze graph orchestration",
                found=False,
                content=None,
                location="N/A",
                rationale=f"Error analyzing graph: {str(e)}",
                confidence=0.6,
                artifact_type="code"
            )
    
    def _parse_graph_file(self, file_path: Path) -> Evidence:
        """Parse graph file for StateGraph patterns."""
        with open(file_path, 'r') as f:
            content = f.read()
        
        tree = ast.parse(content)
        
        graph_info = {
            "has_stategraph": False,
            "parallel_patterns": [],
            "nodes": [],
            "edges": [],
            "reducers": []
        }
        
        for node in ast.walk(tree):
            # Look for StateGraph instantiation
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "StateGraph":
                    graph_info["has_stategraph"] = True
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "StateGraph":
                    graph_info["has_stategraph"] = True
            
            # Look for add_edge calls (parallelism)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "add_edge":
                        graph_info["edges"].append("add_edge")
                    elif node.func.attr == "add_parallel_edge":
                        graph_info["parallel_patterns"].append("add_parallel_edge")
                        graph_info["edges"].append("add_parallel_edge")
                    elif node.func.attr == "add_node":
                        if node.args:
                            graph_info["nodes"].append(ast.unparse(node.args[0]))
            
            # Look for operator reducers
            if isinstance(node, ast.Attribute):
                if node.attr in ["add", "ior", "and_"]:
                    graph_info["reducers"].append(f"operator.{node.attr}")
        
        if graph_info["has_stategraph"]:
            has_parallel = len(graph_info["parallel_patterns"]) > 0 or len(graph_info["edges"]) > 1
            
            return Evidence(
                goal="Analyze graph orchestration",
                found=True,
                content=str(graph_info),
                location=str(file_path),
                rationale=f"Found StateGraph with {len(graph_info['nodes'])} nodes. "
                         f"{'Parallel patterns detected.' if has_parallel else 'Linear flow detected.'}",
                confidence=0.9,
                artifact_type="code"
            )
        else:
            return Evidence(
                goal="Analyze graph orchestration",
                found=False,
                content=None,
                location=str(file_path),
                rationale="No StateGraph definition found",
                confidence=0.8,
                artifact_type="code"
            )
    
    def analyze_tool_safety(self) -> Evidence:
        """
        Check for sandboxed tooling and security practices.
        
        Returns:
            Evidence with tool safety analysis
        """
        if not self.repo_path:
            return Evidence(
                goal="Analyze tool safety",
                found=False,
                content=None,
                location="N/A",
                rationale="No repository path available",
                confidence=0.0,
                artifact_type="code"
            )
        
        try:
            tools_dir = self.repo_path / "src" / "tools"
            if not tools_dir.exists():
                return Evidence(
                    goal="Analyze tool safety",
                    found=False,
                    content=None,
                    location="N/A",
                    rationale="No tools directory found",
                    confidence=0.7,
                    artifact_type="code"
                )
            
            safety_issues = []
            safety_good = []
            
            for py_file in tools_dir.glob("*.py"):
                with open(py_file, 'r') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                
                for node in ast.walk(tree):
                    # Check for os.system calls
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            if node.func.attr == "system" and isinstance(node.func.value, ast.Name) and node.func.value.id == "os":
                                safety_issues.append(f"Raw os.system call in {py_file.name}")
                        elif isinstance(node.func, ast.Name) and node.func.id == "os_system":
                            safety_issues.append(f"Potential os.system call in {py_file.name}")
                    
                    # Check for tempfile usage
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            if node.func.attr in ["TemporaryDirectory", "NamedTemporaryFile"]:
                                if isinstance(node.func.value, ast.Name) and node.func.value.id == "tempfile":
                                    safety_good.append(f"Sandboxed tempfile usage in {py_file.name}")
                    
                    # Check for subprocess.run with shell=True
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute) and node.func.attr == "run":
                            for kw in node.keywords:
                                if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                                    safety_issues.append(f"Dangerous shell=True in subprocess.run in {py_file.name}")
            
            if safety_issues:
                return Evidence(
                    goal="Analyze tool safety",
                    found=True,
                    content=str({"issues": safety_issues, "good": safety_good}),
                    location=str(tools_dir),
                    rationale=f"Found {len(safety_issues)} safety issues and {len(safety_good)} good practices",
                    confidence=0.9,
                    artifact_type="code"
                )
            else:
                return Evidence(
                    goal="Analyze tool safety",
                    found=True,
                    content=str({"good": safety_good}),
                    location=str(tools_dir),
                    rationale=f"No safety issues found. {len(safety_good)} good practices detected.",
                    confidence=0.95,
                    artifact_type="code"
                )
                
        except Exception as e:
            return Evidence(
                goal="Analyze tool safety",
                found=False,
                content=None,
                location="N/A",
                rationale=f"Error analyzing tools: {str(e)}",
                confidence=0.5,
                artifact_type="code"
            )
    
    def analyze_structured_output(self) -> Evidence:
        """
        Check for structured output enforcement using Pydantic.
        
        Returns:
            Evidence with structured output analysis
        """
        if not self.repo_path:
            return Evidence(
                goal="Analyze structured output",
                found=False,
                content=None,
                location="N/A",
                rationale="No repository path available",
                confidence=0.0,
                artifact_type="code"
            )
        
        try:
            nodes_dir = self.repo_path / "src" / "nodes"
            if not nodes_dir.exists():
                return Evidence(
                    goal="Analyze structured output",
                    found=False,
                    content=None,
                    location="N/A",
                    rationale="No nodes directory found",
                    confidence=0.7,
                    artifact_type="code"
                )
            
            structured_outputs = []
            
            for py_file in nodes_dir.glob("*.py"):
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Look for with_structured_output or bind_tools
                if ".with_structured_output" in content or ".bind_tools" in content:
                    structured_outputs.append(py_file.name)
                    
                # Look for Pydantic model usage
                if "BaseModel" in content or "JudicialOpinion" in content:
                    if py_file.name not in structured_outputs:
                        structured_outputs.append(f"{py_file.name} (has models)")
            
            if structured_outputs:
                return Evidence(
                    goal="Analyze structured output",
                    found=True,
                    content=str({"files_with_structured_output": structured_outputs}),
                    location=str(nodes_dir),
                    rationale=f"Found structured output enforcement in {len(structured_outputs)} files",
                    confidence=0.9,
                    artifact_type="code"
                )
            else:
                return Evidence(
                    goal="Analyze structured output",
                    found=False,
                    content=None,
                    location=str(nodes_dir),
                    rationale="No structured output enforcement found",
                    confidence=0.8,
                    artifact_type="code"
                )
                
        except Exception as e:
            return Evidence(
                goal="Analyze structured output",
                found=False,
                content=None,
                location="N/A",
                rationale=f"Error analyzing structured output: {str(e)}",
                confidence=0.6,
                artifact_type="code"
            )