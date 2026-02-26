"""
Utility parsers for evidence processing.
"""

import ast
import json
from typing import Any, Dict, Optional


class EvidenceParser:
    """Parses and validates evidence from various sources."""
    
    @staticmethod
    def parse_ast_content(content: str) -> Optional[Dict[str, Any]]:
        """
        Parse Python content using AST.
        
        Args:
            content: Python source code
            
        Returns:
            AST structure or None if invalid
        """
        try:
            tree = ast.parse(content)
            return {"valid": True, "tree": ast.dump(tree)}
        except SyntaxError as e:
            return {"valid": False, "error": str(e)}
    
    @staticmethod
    def parse_json_safely(content: str) -> Optional[Dict[str, Any]]:
        """
        Safely parse JSON content.
        
        Args:
            content: JSON string
            
        Returns:
            Parsed JSON or None
        """
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None
    
    @staticmethod
    def extract_code_snippets(content: str, max_length: int = 500) -> str:
        """
        Extract relevant code snippets from content.
        
        Args:
            content: Full content
            max_length: Maximum snippet length
            
        Returns:
            Extracted snippet
        """
        if len(content) <= max_length:
            return content
        
        # Try to find a good cutting point
        cut_point = content[:max_length].rfind('\n')
        if cut_point == -1:
            cut_point = max_length
        
        return content[:cut_point] + "...\n[truncated]"