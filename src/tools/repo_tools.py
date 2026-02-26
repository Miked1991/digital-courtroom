"""
Sandboxed git operations for repository forensic analysis.
Always use temporary directories for isolation.
"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import logging


class GitForensics:
    """Sandboxed git operations with comprehensive error handling"""
    
    def __init__(self):
        self.temp_dir = None
        self.repo_path = None
    
    def __enter__(self):
        """Context manager for automatic cleanup"""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_path = self.temp_dir.name
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure cleanup even on errors"""
        if self.temp_dir:
            self.temp_dir.cleanup()
    
    def clone_repository(self, repo_url: str, branch: Optional[str] = None) -> Tuple[bool, str]:
        """
        Safely clone repository into sandboxed temp directory.
        Returns (success, message)
        """
        if not self.repo_path:
            return False, "No sandbox directory initialized"
        
        try:
            # Validate URL (basic security check)
            if not repo_url.startswith(('https://github.com/', 'git@github.com:')):
                return False, "Only GitHub URLs are supported for security"
            
            # Build clone command
            cmd = ['git', 'clone', '--depth', '1', repo_url]
            if branch:
                cmd.extend(['--branch', branch])
            cmd.append('.')  # Clone into current (temp) directory
            
            # Execute in sandbox
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60  # Prevent hanging
            )
            
            if result.returncode == 0:
                return True, f"Successfully cloned to {self.repo_path}"
            else:
                return False, f"Clone failed: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Clone operation timed out"
        except Exception as e:
            return False, f"Clone error: {str(e)}"
    
    def get_commit_history(self, max_count: int = 50) -> List[Dict]:
        """
        Extract commit history with forensic detail.
        Returns list of commits with metadata.
        """
        if not self.repo_path:
            return []
        
        try:
            # Get formatted log with %h (hash), %s (subject), %ct (timestamp), %an (author)
            cmd = [
                'git', 'log', 
                f'--max-count={max_count}',
                '--pretty=format:%h||%s||%ct||%an',
                '--reverse'
            ]
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            commits = []
            if result.returncode == 0:
                for line in result.stdout.strip().split('\n'):
                    if '||' in line:
                        parts = line.split('||')
                        if len(parts) >= 4:
                            commits.append({
                                'hash': parts[0],
                                'message': parts[1],
                                'timestamp': datetime.fromtimestamp(int(parts[2])).isoformat(),
                                'author': parts[3]
                            })
            
            return commits
            
        except Exception as e:
            return [{'error': str(e)}]
    
    def find_files(self, pattern: str) -> List[str]:
        """Find files matching pattern in repository"""
        if not self.repo_path:
            return []
        
        matches = []
        for root, dirs, files in os.walk(self.repo_path):
            # Skip .git directory
            dirs[:] = [d for d in dirs if d != '.git']
            
            for file in files:
                if pattern in file or file.endswith(pattern.replace('*', '')):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.repo_path)
                    matches.append(rel_path)
        
        return matches
    
    def read_file(self, file_path: str) -> Optional[str]:
        """Safely read file content from repository"""
        if not self.repo_path:
            return None
        
        full_path = os.path.join(self.repo_path, file_path)
        
        # Security: prevent directory traversal
        if not os.path.realpath(full_path).startswith(os.path.realpath(self.repo_path)):
            return None
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            return None
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in repository"""
        if not self.repo_path:
            return False
        
        full_path = os.path.join(self.repo_path, file_path)
        
        # Security: prevent directory traversal
        if not os.path.realpath(full_path).startswith(os.path.realpath(self.repo_path)):
            return False
        
        return os.path.isfile(full_path)