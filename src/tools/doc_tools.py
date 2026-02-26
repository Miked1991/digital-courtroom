"""
Document analysis tools for PDF reports using Gemini's document understanding.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
import PyPDF2
from docling.document_converter import DocumentConverter
import google.generativeai as genai
from dotenv import load_dotenv

from ..state import Evidence

load_dotenv()


class DocAnalystTools:
    """Production-grade tools for PDF report forensic analysis."""
    
    def __init__(self, gemini_model: str = "gemini-1.5-pro"):
        """Initialize with Gemini model for document understanding."""
        self.gemini_model = gemini_model
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(gemini_model)
        
    def extract_text_from_pdf(self, pdf_path: str) -> Evidence:
        """
        Extract text content from PDF using PyPDF2 and docling.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Evidence with extracted text
        """
        try:
            path = Path(pdf_path)
            if not path.exists():
                return Evidence(
                    goal="Extract text from PDF",
                    found=False,
                    content=None,
                    location=pdf_path,
                    rationale=f"PDF file not found: {pdf_path}",
                    confidence=1.0,
                    artifact_type="documentation"
                )
            
            # Try docling first for better extraction
            try:
                converter = DocumentConverter()
                result = converter.convert(str(path))
                text_content = result.document.export_to_text()
            except:
                # Fallback to PyPDF2
                text_content = []
                with open(path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    for page in reader.pages:
                        text_content.append(page.extract_text())
                text_content = "\n".join(text_content)
            
            # Extract metadata
            metadata = {
                "file_name": path.name,
                "file_size": path.stat().st_size,
                "page_count": len(reader.pages) if 'reader' in locals() else 0
            }
            
            content = {
                "metadata": metadata,
                "text": text_content[:5000]  # Limit for storage
            }
            
            return Evidence(
                goal="Extract text from PDF",
                found=True,
                content=str(content),
                location=pdf_path,
                rationale=f"Successfully extracted text from {path.name}",
                confidence=0.95,
                artifact_type="documentation"
            )
            
        except Exception as e:
            return Evidence(
                goal="Extract text from PDF",
                found=False,
                content=None,
                location=pdf_path,
                rationale=f"Error extracting PDF: {str(e)}",
                confidence=0.7,
                artifact_type="documentation"
            )
    
    def analyze_theoretical_depth(self, pdf_path: str) -> Evidence:
        """
        Analyze PDF for theoretical concepts using Gemini.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Evidence with theoretical depth analysis
        """
        try:
            # First extract text
            text_evidence = self.extract_text_from_pdf(pdf_path)
            if not text_evidence.found:
                return text_evidence
            
            # Parse the content
            import ast
            content_dict = ast.literal_eval(text_evidence.content)
            text_content = content_dict.get("text", "")
            
            # Define concepts to look for
            concepts = [
                "Dialectical Synthesis",
                "Fan-In",
                "Fan-Out",
                "Metacognition",
                "State Synchronization",
                "Forensic Analysis",
                "Multi-Agent System"
            ]
            
            # Use Gemini to analyze theoretical depth
            prompt = f"""
            Analyze the following text from an architectural report for theoretical depth.
            
            Concepts to check for:
            {', '.join(concepts)}
            
            Text:
            {text_content[:10000]}  # Limit context
            
            Provide analysis in this format:
            1. For each concept: is it mentioned? In what context? Is it explained or just a buzzword?
            2. Overall theoretical depth score (1-5)
            3. Evidence of deep understanding vs. keyword dropping
            
            Format your response as a JSON object with keys:
            - concept_analysis: dict mapping concept names to {"mentioned": bool, "explained": bool, "context": str}
            - depth_score: int
            - reasoning: str
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse response
            try:
                import json
                # Try to extract JSON from response
                response_text = response.text
                # Find JSON in response
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    analysis = json.loads(json_str)
                else:
                    analysis = {"raw": response_text}
            except:
                analysis = {"raw": response.text}
            
            return Evidence(
                goal="Analyze theoretical depth",
                found=True,
                content=str(analysis),
                location=pdf_path,
                rationale=f"Theoretical depth analysis completed. Score: {analysis.get('depth_score', 'N/A')}",
                confidence=0.85,
                artifact_type="documentation"
            )
            
        except Exception as e:
            return Evidence(
                goal="Analyze theoretical depth",
                found=False,
                content=None,
                location=pdf_path,
                rationale=f"Error analyzing theoretical depth: {str(e)}",
                confidence=0.6,
                artifact_type="documentation"
            )
    
    def cross_reference_claims(self, pdf_path: str, repo_evidence: Dict[str, Any]) -> Evidence:
        """
        Cross-reference claims in PDF with actual code evidence.
        
        Args:
            pdf_path: Path to PDF file
            repo_evidence: Evidence collected from repository
            
        Returns:
            Evidence with cross-reference results
        """
        try:
            # Extract claims from PDF
            text_evidence = self.extract_text_from_pdf(pdf_path)
            if not text_evidence.found:
                return text_evidence
            
            import ast
            content_dict = ast.literal_eval(text_evidence.content)
            text_content = content_dict.get("text", "")
            
            # Use Gemini to extract file path claims
            prompt = f"""
            Extract all claims about file paths, code locations, and specific implementations from this text.
            
            Text:
            {text_content[:8000]}
            
            List each claim in this JSON format:
            {{
                "claims": [
                    {{
                        "claim_text": "exact text of claim",
                        "claimed_file_path": "file path if mentioned",
                        "claimed_feature": "feature being claimed",
                        "confidence": 0.0-1.0
                    }}
                ]
            }}
            
            Only include claims that reference specific files or code locations.
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse claims
            try:
                response_text = response.text
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    claims_data = json.loads(json_str)
                    claims = claims_data.get("claims", [])
                else:
                    claims = []
            except:
                claims = []
            
            # Cross-reference with repo evidence
            verified_claims = []
            hallucinated_claims = []
            
            # Get all file paths from repo evidence
            repo_files = set()
            if repo_evidence:
                for evidence in repo_evidence.values():
                    if hasattr(evidence, 'location') and evidence.location != "N/A":
                        repo_files.add(evidence.location)
            
            for claim in claims:
                claimed_path = claim.get("claimed_file_path", "")
                if claimed_path and any(claimed_path in f for f in repo_files):
                    verified_claims.append(claim)
                else:
                    hallucinated_claims.append(claim)
            
            result = {
                "total_claims": len(claims),
                "verified_claims": verified_claims,
                "hallucinated_claims": hallucinated_claims,
                "verification_rate": len(verified_claims) / max(len(claims), 1)
            }
            
            return Evidence(
                goal="Cross-reference claims with code",
                found=True,
                content=str(result),
                location=pdf_path,
                rationale=f"Cross-referenced {len(claims)} claims. "
                         f"{len(verified_claims)} verified, {len(hallucinated_claims)} hallucinated.",
                confidence=0.9,
                artifact_type="documentation"
            )
            
        except Exception as e:
            return Evidence(
                goal="Cross-reference claims with code",
                found=False,
                content=None,
                location=pdf_path,
                rationale=f"Error cross-referencing claims: {str(e)}",
                confidence=0.6,
                artifact_type="documentation"
            )