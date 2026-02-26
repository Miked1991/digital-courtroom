"""
Forensic detective agents that collect objective evidence.
No opinions - only facts based on strict forensic protocols.
"""

import os
import json
from typing import Dict, List, Any
from langgraph.graph import StateGraph
import asyncio

from src.state import AgentState, Evidence
from src.tools.git_tools import GitForensics
from src.tools.ast_tools import ASTAnalyzer
from src.tools.pdf_tools import PDFForensics
from src.tools.vision_tools import VisionForensics
from src.config.prompts import DetectivePrompts


class RepoInvestigator:
    """Code detective - analyzes repository structure with AST-level precision"""
    
    def __init__(self):
        self.ast_analyzer = ASTAnalyzer()
        self.prompts = DetectivePrompts()
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Execute forensic analysis on repository"""
        evidences = {}
        
        try:
            with GitForensics() as git:
                # Clone repo in sandbox
                success, message = git.clone_repository(state['repo_url'])
                
                if not success:
                    evidences['git_clone'] = [Evidence(
                        goal="Clone repository for analysis",
                        found=False,
                        content=message,
                        location="git clone operation",
                        rationale="Repository clone failed - cannot proceed with code analysis",
                        confidence=1.0
                    )]
                    return {"evidences": state['evidences'] | evidences}
                
                # Collect forensic evidence
                
                # 1. Git History Analysis
                commits = git.get_commit_history()
                evidences['git_history'] = [Evidence(
                    goal="Analyze commit history for development patterns",
                    found=len(commits) > 0,
                    content=json.dumps(commits, indent=2),
                    location="git log",
                    rationale=f"Found {len(commits)} commits showing development progression",
                    confidence=0.95 if len(commits) > 3 else 0.7
                )]
                
                # 2. State Management Check
                state_files = git.find_files('state.py') + git.find_files('graph.py')
                state_evidence = []
                
                for file in state_files[:3]:  # Check first few
                    content = git.read_file(file)
                    if content:
                        tree = self.ast_analyzer.parse_file(os.path.join(git.repo_path, file))
                        if tree:
                            models = self.ast_analyzer.find_pydantic_models(tree)
                            state_evidence.append(Evidence(
                                goal="Verify Pydantic state models",
                                found=len(models) > 0,
                                content=f"Found models: {[m['name'] for m in models]}",
                                location=file,
                                rationale=f"{'Found' if models else 'No'} Pydantic models in {file}",
                                confidence=0.9 if models else 0.8
                            ))
                
                if not state_evidence:
                    state_evidence.append(Evidence(
                        goal="Verify Pydantic state models",
                        found=False,
                        content=None,
                        location="src/state.py or src/graph.py",
                        rationale="No state definition files found with Pydantic models",
                        confidence=1.0
                    ))
                
                evidences['state_management'] = state_evidence
                
                # 3. Graph Orchestration Analysis
                graph_evidence = []
                for file in git.find_files('graph.py'):
                    content = git.read_file(file)
                    if content:
                        tree = self.ast_analyzer.parse_file(os.path.join(git.repo_path, file))
                        if tree:
                            graph_info = self.ast_analyzer.find_stategraph_usage(tree)
                            graph_evidence.append(Evidence(
                                goal="Analyze graph orchestration for parallelism",
                                found=graph_info['has_stategraph'],
                                content=json.dumps(graph_info, indent=2),
                                location=file,
                                rationale=f"Graph {'has' if graph_info['has_stategraph'] else 'lacks'} StateGraph. Parallel patterns: {graph_info['parallel_patterns']}",
                                confidence=0.85
                            ))
                
                evidences['graph_orchestration'] = graph_evidence
                
                # 4. Tool Safety Check
                tool_files = git.find_files('tools/')
                safety_evidence = []
                
                for file in tool_files:
                    if file.endswith('.py'):
                        content = git.read_file(file)
                        if content:
                            tree = self.ast_analyzer.parse_file(os.path.join(git.repo_path, file))
                            if tree:
                                unsafe_calls = self.ast_analyzer.find_os_system_calls(tree)
                                if unsafe_calls:
                                    safety_evidence.append(Evidence(
                                        goal="Verify sandboxed tool execution",
                                        found=False,
                                        content=json.dumps(unsafe_calls),
                                        location=file,
                                        rationale=f"Found {len(unsafe_calls)} unsafe os.system calls without sandboxing",
                                        confidence=1.0
                                    ))
                
                if not safety_evidence:
                    safety_evidence.append(Evidence(
                        goal="Verify sandboxed tool execution",
                        found=True,
                        content="No unsafe system calls detected",
                        location="src/tools/",
                        rationale="All tools appear to use safe practices",
                        confidence=0.9
                    ))
                
                evidences['tool_safety'] = safety_evidence
                
                # 5. Structured Output Check
                judge_files = git.find_files('judges.py') + git.find_files('nodes/')
                structured_evidence = []
                
                for file in judge_files:
                    if file.endswith('.py'):
                        content = git.read_file(file)
                        if content:
                            tree = self.ast_analyzer.parse_file(os.path.join(git.repo_path, file))
                            if tree:
                                structured_calls = self.ast_analyzer.find_structured_output_usage(tree)
                                if structured_calls:
                                    structured_evidence.append(Evidence(
                                        goal="Verify structured JSON output enforcement",
                                        found=True,
                                        content=json.dumps(structured_calls),
                                        location=file,
                                        rationale=f"Found structured output enforcement: {[c['method'] for c in structured_calls]}",
                                        confidence=0.9
                                    ))
                
                if not structured_evidence:
                    structured_evidence.append(Evidence(
                        goal="Verify structured JSON output enforcement",
                        found=False,
                        content=None,
                        location="src/nodes/judges.py",
                        rationale="No .with_structured_output() or .bind_tools() calls detected",
                        confidence=0.85
                    ))
                
                evidences['structured_output'] = structured_evidence
                
        except Exception as e:
            evidences['error'] = [Evidence(
                goal="Handle repository analysis errors",
                found=False,
                content=str(e),
                location="RepoInvestigator",
                rationale=f"Analysis failed with error: {str(e)}",
                confidence=1.0
            )]
        
        # Merge with existing evidences using operator.ior
        return {"evidences": state['evidences'] | evidences}


class DocAnalyst:
    """Document detective - analyzes PDF reports with RAG-lite"""
    
    def __init__(self):
        self.pdf_forensics = PDFForensics()
        self.prompts = DetectivePrompts()
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Execute forensic analysis on PDF report"""
        evidences = {}
        
        try:
            # Load PDF
            if not os.path.exists(state['pdf_path']):
                evidences['pdf_load'] = [Evidence(
                    goal="Load PDF report for analysis",
                    found=False,
                    content=None,
                    location=state['pdf_path'],
                    rationale="PDF file not found at specified path",
                    confidence=1.0
                )]
                return {"evidences": state['evidences'] | evidences}
            
            success = self.pdf_forensics.load_pdf(state['pdf_path'])
            
            if not success:
                evidences['pdf_load'] = [Evidence(
                    goal="Load PDF report for analysis",
                    found=False,
                    content=None,
                    location=state['pdf_path'],
                    rationale="Failed to parse PDF file",
                    confidence=1.0
                )]
                return {"evidences": state['evidences'] | evidences}
            
            # 1. Theoretical Depth Analysis
            key_terms = [
                "Dialectical Synthesis",
                "Fan-In",
                "Fan-Out",
                "Metacognition",
                "State Synchronization",
                "Parallel Execution",
                "Forensic Accuracy"
            ]
            
            term_results = self.pdf_forensics.extract_key_terms(key_terms)
            
            theoretical_evidence = []
            for term, contexts in term_results.items():
                theoretical_evidence.append(Evidence(
                    goal="Verify theoretical depth and concept understanding",
                    found=True,
                    content=json.dumps(contexts[:2], indent=2),  # First 2 contexts
                    location=f"PDF Report, page {contexts[0]['page'] if contexts else 'unknown'}",
                    rationale=f"Found discussion of '{term}' with proper context",
                    confidence=0.85 if contexts else 0.5
                ))
            
            # Add evidence for missing terms
            missing_terms = [t for t in key_terms if t not in term_results]
            if missing_terms:
                theoretical_evidence.append(Evidence(
                    goal="Verify theoretical depth and concept understanding",
                    found=False,
                    content=None,
                    location="PDF Report",
                    rationale=f"Missing discussion of key concepts: {', '.join(missing_terms[:3])}",
                    confidence=0.9
                ))
            
            evidences['theoretical_depth'] = theoretical_evidence
            
            # 2. Cross-Reference Claims
            # Extract potential file path claims from PDF
            claims = []
            for chunk in self.pdf_forensics.chunks:
                # Look for file path patterns
                words = chunk['text'].split()
                for word in words:
                    if '.py' in word or '/' in word and '.' in word:
                        claims.append(word.strip('.,;:()'))
            
            # Verify claims against repo evidence
            verified_claims = []
            for claim in list(set(claims))[:10]:  # Limit to 10 claims
                # Check if claim exists in repo evidence
                found_in_repo = False
                for evidence_list in state['evidences'].values():
                    for evidence in evidence_list:
                        if evidence.location and claim in evidence.location:
                            found_in_repo = True
                            break
                
                verified_claims.append({
                    'claim': claim,
                    'verified': found_in_repo,
                    'source': 'PDF'
                })
            
            evidences['cross_reference'] = [Evidence(
                goal="Cross-reference PDF claims with repository evidence",
                found=any(vc['verified'] for vc in verified_claims),
                content=json.dumps(verified_claims, indent=2),
                location="PDF Report cross-reference",
                rationale=f"Verified {sum(1 for vc in verified_claims if vc['verified'])} out of {len(verified_claims)} claims",
                confidence=0.8
            )]
            
        except Exception as e:
            evidences['error'] = [Evidence(
                goal="Handle document analysis errors",
                found=False,
                content=str(e),
                location="DocAnalyst",
                rationale=f"Analysis failed with error: {str(e)}",
                confidence=1.0
            )]
        
        return {"evidences": state['evidences'] | evidences}


class VisionInspector:
    """Diagram detective - analyzes architectural diagrams in PDF"""
    
    def __init__(self):
        self.vision = VisionForensics()
        self.pdf_forensics = PDFForensics()
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Execute forensic analysis on diagrams"""
        evidences = {}
        
        try:
            # Extract images from PDF
            images = self.pdf_forensics.extract_images(state['pdf_path'])
            
            if not images:
                evidences['diagrams'] = [Evidence(
                    goal="Analyze architectural diagrams",
                    found=False,
                    content=None,
                    location="PDF Report",
                    rationale="No images found in PDF for diagram analysis",
                    confidence=1.0
                )]
                return {"evidences": state['evidences'] | evidences}
            
            # Analyze each diagram
            diagram_evidence = []
            for img in images[:3]:  # Analyze first 3 diagrams
                analysis = self.vision.analyze_diagram(
                    img['path'],
                    "Analyze this architecture diagram. Is it a LangGraph state machine showing parallel execution paths?"
                )
                
                diagram_evidence.append(Evidence(
                    goal="Analyze architectural diagrams for swarm visualization",
                    found=True,
                    content=json.dumps(analysis, indent=2),
                    location=f"PDF Report, page {img['page']}",
                    rationale=f"Diagram type: {analysis.get('diagram_type', 'Unknown')}. Parallel detected: {analysis.get('parallel_detected', False)}",
                    confidence=0.75
                ))
                
                # Cleanup temp file
                try:
                    os.unlink(img['path'])
                except:
                    pass
            
            evidences['diagrams'] = diagram_evidence
            
        except Exception as e:
            evidences['error'] = [Evidence(
                goal="Handle vision analysis errors",
                found=False,
                content=str(e),
                location="VisionInspector",
                rationale=f"Analysis failed with error: {str(e)}",
                confidence=1.0
            )]
        
        return {"evidences": state['evidences'] | evidences}