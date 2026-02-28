"""
Sandboxed git operations for repository forensic analysis.
Always use temporary directories for isolation with comprehensive error handling.
"""

import os
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Union
from datetime import datetime
import logging
import stat
import time

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GitForensics:
    """Sandboxed git operations with comprehensive error handling"""
    
    def __init__(self, timeout: int = 60):
        self.temp_dir = None
        self.repo_path = None
        self.timeout = timeout
        self._cleanup_registered = False
    
    def __enter__(self):
        """Context manager for automatic cleanup"""
        self.temp_dir = tempfile.TemporaryDirectory(prefix="git_audit_")
        self.repo_path = self.temp_dir.name
        logger.info(f"Created sandbox directory: {self.repo_path}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure cleanup even on errors"""
        self.cleanup()
    
    def cleanup(self):
        """Safely cleanup temporary directory"""
        if self.temp_dir:
            try:
                # On Windows, we need to handle file locks
                if os.name == 'nt':
                    self._force_cleanup_windows()
                else:
                    self.temp_dir.cleanup()
                logger.info("Cleaned up sandbox directory")
            except Exception as e:
                logger.warning(f"Cleanup warning (non-fatal): {e}")
            finally:
                self.temp_dir = None
                self.repo_path = None
    
    def _force_cleanup_windows(self):
        """Force cleanup on Windows by retrying and changing file attributes"""
        if not self.temp_dir:
            return
        
        retries = 3
        for i in range(retries):
            try:
                # Make all files writable
                for root, dirs, files in os.walk(self.temp_dir.name):
                    for f in files:
                        try:
                            os.chmod(os.path.join(root, f), stat.S_IWRITE)
                        except:
                            pass
                
                self.temp_dir.cleanup()
                return
            except Exception as e:
                if i < retries - 1:
                    time.sleep(1)  # Wait and retry
                else:
                    # If all retries fail, try shutil.rmtree
                    try:
                        shutil.rmtree(self.temp_dir.name, ignore_errors=True)
                    except:
                        pass
    
    def _run_git_command(self, cmd: List[str], cwd: Optional[str] = None, 
                        timeout: Optional[int] = None) -> Tuple[bool, str, str]:
        """
        Safely run git command with comprehensive error handling
        
        Returns:
            Tuple[success, stdout, stderr]
        """
        if cwd is None:
            cwd = self.repo_path if self.repo_path else os.getcwd()
        
        timeout = timeout or self.timeout
        
        try:
            # Validate that we're in a safe directory
            if not cwd or not os.path.exists(cwd):
                return False, "", f"Invalid working directory: {cwd}"
            
            # Run command with timeout
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,  # Don't raise on non-zero return
                env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}  # Disable prompts
            )
            
            # Log command for debugging
            logger.debug(f"Git command: {' '.join(cmd)}")
            logger.debug(f"Return code: {result.returncode}")
            
            if result.returncode == 0:
                return True, result.stdout, result.stderr
            else:
                error_msg = f"Git command failed: {result.stderr}"
                logger.error(error_msg)
                return False, result.stdout, error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = f"Git command timed out after {timeout} seconds"
            logger.error(error_msg)
            return False, "", error_msg
            
        except FileNotFoundError:
            error_msg = "Git executable not found. Please ensure Git is installed."
            logger.error(error_msg)
            return False, "", error_msg
            
        except PermissionError as e:
            error_msg = f"Permission error: {str(e)}"
            logger.error(error_msg)
            return False, "", error_msg
            
        except Exception as e:
            error_msg = f"Unexpected error running git command: {str(e)}"
            logger.error(error_msg)
            return False, "", error_msg
    
    def validate_github_url(self, repo_url: str) -> Tuple[bool, str]:
        """Validate GitHub URL for security"""
        # List of allowed domains
        allowed_domains = ['github.com', 'raw.githubusercontent.com']
        allowed_prefixes = ['https://', 'git@']
        
        # Basic validation
        if not repo_url or len(repo_url) > 200:  # Prevent extremely long URLs
            return False, "Invalid URL length"
        
        # Check for allowed domains
        valid = False
        for domain in allowed_domains:
            if domain in repo_url:
                valid = True
                break
        
        if not valid:
            return False, f"Only GitHub URLs are allowed. Domain must be one of: {allowed_domains}"
        
        # Check for allowed protocols
        valid = False
        for prefix in allowed_prefixes:
            if repo_url.startswith(prefix):
                valid = True
                break
        
        if not valid:
            return False, f"URL must start with one of: {allowed_prefixes}"
        
        # Prevent command injection
        dangerous_chars = [';', '&', '|', '`', '$', '(', ')', '<', '>', '\\', '"', "'"]
        for char in dangerous_chars:
            if char in repo_url:
                return False, f"URL contains dangerous character: {char}"
        
        return True, "URL validation passed"
    
    def clone_repository(self, repo_url: str, branch: Optional[str] = None) -> Tuple[bool, str]:
        """
        Safely clone repository into sandboxed temp directory.
        Returns (success, message)
        """
        if not self.repo_path:
            return False, "No sandbox directory initialized"
        
        # Validate URL for security
        valid, message = self.validate_github_url(repo_url)
        if not valid:
            return False, f"Security validation failed: {message}"
        
        try:
            # Build clone command with security options
            cmd = ['git', 'clone', '--depth', '1']  # Shallow clone for speed
            
            # Add branch if specified
            if branch:
                # Validate branch name
                if not self._validate_branch_name(branch):
                    return False, f"Invalid branch name: {branch}"
                cmd.extend(['--branch', branch])
            
            cmd.append(repo_url)
            cmd.append('.')  # Clone into current directory
            
            # Execute in sandbox
            success, stdout, stderr = self._run_git_command(cmd, cwd=self.repo_path)
            
            if success:
                # Verify the clone actually created files
                if not self._verify_clone():
                    return False, "Clone appeared successful but no files found"
                
                return True, f"Successfully cloned to {self.repo_path}"
            else:
                return False, f"Clone failed: {stderr}"
                
        except Exception as e:
            error_msg = f"Clone error: {str(e)}"
            logger.exception(error_msg)
            return False, error_msg
    
    def _validate_branch_name(self, branch: str) -> bool:
        """Validate branch name to prevent injection"""
        # Branch names should only contain alphanumeric, dash, underscore, dot, slash
        import re
        pattern = r'^[a-zA-Z0-9_\-\.\/]+$'
        return bool(re.match(pattern, branch)) and len(branch) < 100
    
    def _verify_clone(self) -> bool:
        """Verify that the clone actually created a git repository"""
        git_dir = os.path.join(self.repo_path, '.git')
        return os.path.exists(git_dir) and os.path.isdir(git_dir)
    
    def get_commit_history(self, max_count: int = 50) -> List[Dict]:
        """
        Extract commit history with forensic detail.
        Returns list of commits with metadata.
        """
        if not self.repo_path or not self._verify_clone():
            logger.warning("No valid git repository to get history from")
            return []
        
        try:
            # Get formatted log with %h (hash), %s (subject), %ct (timestamp), %an (author)
            cmd = [
                'git', 'log', 
                f'--max-count={max_count}',
                '--pretty=format:%h||%s||%ct||%an||%ae',
                '--reverse'
            ]
            
            success, stdout, stderr = self._run_git_command(cmd)
            
            commits = []
            if success and stdout:
                for line in stdout.strip().split('\n'):
                    if line and '||' in line:
                        parts = line.split('||')
                        if len(parts) >= 5:
                            try:
                                timestamp = int(parts[2])
                                commits.append({
                                    'hash': parts[0],
                                    'message': parts[1],
                                    'timestamp': datetime.fromtimestamp(timestamp).isoformat(),
                                    'author': parts[3],
                                    'email': parts[4]
                                })
                            except (ValueError, IndexError) as e:
                                logger.warning(f"Error parsing commit line: {e}")
            
            return commits
            
        except Exception as e:
            logger.exception(f"Error getting commit history: {e}")
            return []
    
    def find_files(self, pattern: str) -> List[str]:
        """Find files matching pattern in repository"""
        if not self.repo_path:
            return []
        
        matches = []
        try:
            for root, dirs, files in os.walk(self.repo_path):
                # Skip .git directory
                dirs[:] = [d for d in dirs if d != '.git']
                
                for file in files:
                    if pattern in file or file.endswith(pattern.replace('*', '')):
                        full_path = os.path.join(root, file)
                        # Get relative path safely
                        try:
                            rel_path = os.path.relpath(full_path, self.repo_path)
                            matches.append(rel_path)
                        except ValueError:
                            # Path relativity error, skip
                            continue
        except Exception as e:
            logger.exception(f"Error finding files: {e}")
        
        return matches
    
    def read_file(self, file_path: str) -> Optional[str]:
        """Safely read file content from repository"""
        if not self.repo_path:
            return None
        
        # Normalize paths to prevent directory traversal
        try:
            # Get absolute paths
            repo_abs = os.path.abspath(self.repo_path)
            file_abs = os.path.abspath(os.path.join(self.repo_path, file_path))
            
            # Security: prevent directory traversal
            if not file_abs.startswith(repo_abs):
                logger.warning(f"Directory traversal attempt blocked: {file_path}")
                return None
            
            # Check file exists and is within limits
            if not os.path.isfile(file_abs):
                return None
            
            # Check file size (limit to 1MB)
            if os.path.getsize(file_abs) > 1_000_000:
                logger.warning(f"File too large (>1MB): {file_path}")
                return None
            
            # Try multiple encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            for encoding in encodings:
                try:
                    with open(file_abs, 'r', encoding=encoding) as f:
                        return f.read()
                except UnicodeDecodeError:
                    continue
            
            return None
            
        except Exception as e:
            logger.exception(f"Error reading file {file_path}: {e}")
            return None
    
    def file_exists(self, file_path: str) -> bool:
        """Check if file exists in repository"""
        if not self.repo_path:
            return False
        
        try:
            full_path = os.path.join(self.repo_path, file_path)
            # Normalize to prevent directory traversal
            full_path = os.path.abspath(full_path)
            repo_abs = os.path.abspath(self.repo_path)
            
            # Security: prevent directory traversal
            if not full_path.startswith(repo_abs):
                return False
            
            return os.path.isfile(full_path)
        except Exception:
            return False