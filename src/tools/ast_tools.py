"""
Advanced AST parsing tools for code forensic analysis.
Never rely on regex - use Python's AST module for structural verification.
"""

import ast
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import re


class ASTAnalyzer:
    """Production AST parser for code structure verification"""
    
    @staticmethod
    def parse_file(file_path: str) -> Optional[ast.AST]:
        """Safely parse Python file into AST"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return ast.parse(content)
        except (SyntaxError, UnicodeDecodeError, FileNotFoundError) as e:
            return None
    
    @staticmethod
    def find_pydantic_models(tree: ast.AST) -> List[Dict[str, Any]]:
        """Find all Pydantic BaseModel subclasses"""
        models = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check for BaseModel inheritance
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id == 'BaseModel':
                        models.append({
                            'name': node.name,
                            'line': node.lineno,
                            'fields': ASTAnalyzer._extract_class_fields(node)
                        })
                    elif isinstance(base, ast.Attribute) and base.attr == 'BaseModel':
                        models.append({
                            'name': node.name,
                            'line': node.lineno,
                            'fields': ASTAnalyzer._extract_class_fields(node)
                        })
        
        return models
    
    @staticmethod
    def _extract_class_fields(class_node: ast.ClassDef) -> List[Dict]:
        """Extract field definitions from a class"""
        fields = []
        
        for node in class_node.body:
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                field_type = ast.unparse(node.annotation) if node.annotation else "Any"
                fields.append({
                    'name': node.target.id,
                    'type': field_type,
                    'line': node.lineno
                })
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        fields.append({
                            'name': target.id,
                            'value': ast.unparse(node.value) if node.value else None,
                            'line': node.lineno
                        })
        
        return fields
    
    @staticmethod
    def find_stategraph_usage(tree: ast.AST) -> Dict[str, Any]:
        """Analyze StateGraph construction and edges"""
        graph_info = {
            'has_stategraph': False,
            'nodes': [],
            'edges': [],
            'parallel_patterns': [],
            'linear': True
        }
        
        for node in ast.walk(tree):
            # Look for StateGraph instantiation
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'StateGraph':
                    graph_info['has_stategraph'] = True
                elif isinstance(node.func, ast.Attribute) and node.func.attr == 'StateGraph':
                    graph_info['has_stategraph'] = True
            
            # Look for add_edge calls (parallelism indicators)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == 'add_edge':
                        if len(node.args) >= 2:
                            # Check for fan-out pattern (single source to multiple targets)
                            graph_info['edges'].append({
                                'from': ast.unparse(node.args[0]),
                                'to': ast.unparse(node.args[1]),
                                'line': node.lineno
                            })
                    elif node.func.attr == 'add_conditional_edges':
                        graph_info['parallel_patterns'].append('conditional')
        
        # Analyze edge patterns for parallelism
        sources = [e['from'] for e in graph_info['edges']]
        if len(set(sources)) < len(sources):  # Same source appears multiple times
            graph_info['parallel_patterns'].append('fan-out')
            graph_info['linear'] = False
        
        return graph_info
    
    @staticmethod
    def find_structured_output_usage(tree: ast.AST) -> List[Dict]:
        """Find .with_structured_output() or .bind_tools() calls"""
        structured_calls = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ['with_structured_output', 'bind_tools']:
                        structured_calls.append({
                            'method': node.func.attr,
                            'line': node.lineno,
                            'context': ast.unparse(node) [:100]  # First 100 chars
                        })
        
        return structured_calls
    
    @staticmethod
    def find_os_system_calls(tree: ast.AST) -> List[Dict]:
        """Find potentially unsafe os.system calls"""
        unsafe_calls = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == 'system' and isinstance(node.func.value, ast.Name):
                        if node.func.value.id == 'os':
                            unsafe_calls.append({
                                'type': 'os.system',
                                'line': node.lineno,
                                'args': [ast.unparse(arg) for arg in node.args]
                            })
        
        return unsafe_calls