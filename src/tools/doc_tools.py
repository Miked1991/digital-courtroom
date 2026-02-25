 """
Document analysis tools using Docling and RAG-lite approach
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
import re

from docling.document_loader import DocumentLoader
from docling.pipeline import DocumentPipeline
from docling.datamodel import Document
import PyPDF2
from PIL import Image
import io
import fitz  # PyMuPDF for image extraction

from ..state import Evidence

logger = logging.getLogger(__name__)


class DocAnalyst:
    """Document detective for PDF report analysis"""
    
    def __init__(self):
        self.doc: Optional[Document] = None
        self.chunks: List[Dict[str, Any]] = []
        self.images: List[Image.Image] = []
        self.pdf_path: Optional[str] = None
        
    def ingest_pdf(self, pdf_path: str) -> Tuple[bool, str]:
        """
        Ingest PDF using Docling with chunking
        """
        self.pdf_path = pdf_path
        try:
            # Load document
            loader = DocumentLoader()
            self.doc = loader.load(pdf_path)
            
            # Process with pipeline
            pipeline = DocumentPipeline()
            self.doc = pipeline.process(self.doc)
            
            # Extract text chunks
            self._chunk_document()
            
            # Extract images
            self._extract_images(pdf_path)
            
            return True, f"Successfully ingested PDF: {len(self.chunks)} chunks, {len(self.images)} images"
            
        except Exception as e:
            logger.error(f"Failed to ingest PDF: {e}")
            return False, str(e)
    
    def _chunk_document(self, chunk_size: int = 500, overlap: int = 50):
        """Split document into overlapping chunks for RAG-lite"""
        if not self.doc or not self.doc.text:
            return
            
        text = self.doc.text
        words = text.split()
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = ' '.join(chunk_words)
            
            # Get page number approximation
            page_num = self._estimate_page(i, len(words))
            
            self.chunks.append({
                "text": chunk_text,
                "start_idx": i,
                "end_idx": i + len(chunk_words),
                "page": page_num
            })
    
    def _estimate_page(self, word_idx: int, total_words: int) -> int:
        """Estimate page number based on word position"""
        if not self.doc or not self.doc.pages:
            return 1
            
        words_per_page = total_words / len(self.doc.pages)
        return int(word_idx / words_per_page) + 1
    
    def _extract_images(self, pdf_path: str):
        """Extract images from PDF using PyMuPDF"""
        try:
            pdf_document = fitz.open(pdf_path)
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    base_image = pdf_document.extract_image(xref)
                    image_bytes = base_image["image"]
                    
                    # Convert to PIL Image
                    image = Image.open(io.BytesIO(image_bytes))
                    self.images.append({
                        "image": image,
                        "page": page_num + 1,
                        "index": img_index
                    })
            
            pdf_document.close()
        except Exception as e:
            logger.error(f"Failed to extract images: {e}")
    
    def query_keywords(self, keywords: List[str]) -> Evidence:
        """Query document for keyword presence and context"""
        if not self.chunks:
            return Evidence(
                goal="Theoretical Depth Analysis",
                found=False,
                content="No document content available",
                location=self.pdf_path or "N/A",
                rationale="Document not ingested or empty",
                confidence=0.0,
                artifact_type="doc"
            )
        
        findings = []
        for keyword in keywords:
            keyword_lower = keyword.lower()
            for chunk in self.chunks:
                if keyword_lower in chunk["text"].lower():
                    # Extract context around keyword
                    text = chunk["text"]
                    words = text.split()
                    for i, word in enumerate(words):
                        if keyword_lower in word.lower():
                            start = max(0, i - 10)
                            end = min(len(words), i + 11)
                            context = ' '.join(words[start:end])
                            findings.append({
                                "keyword": keyword,
                                "context": context,
                                "page": chunk["page"]
                            })
                            break
        
        # Determine if keywords are explained or just buzzwords
        is_deep = self._analyze_depth(findings)
        
        content = f"Found {len(findings)} keyword occurrences\n"
        content += f"Deep explanation: {'Yes' if is_deep else 'No'}\n\n"
        for f in findings[:5]:  # Limit to first 5
            content += f"- {f['keyword']} (page {f['page']}): {f['context']}\n"
        
        return Evidence(
            goal="Theoretical Depth Analysis",
            found=len(findings) > 0,
            content=content,
            location=self.pdf_path or "N/A",
            rationale=f"Found {len(findings)} keyword instances. Deep analysis: {is_deep}",
            confidence=0.8 if is_deep else 0.4,
            artifact_type="doc"
        )
    
    def _analyze_depth(self, findings: List[Dict]) -> bool:
        """Analyze if keywords are deeply explained vs buzzwords"""
        if len(findings) < 3:
            return False
            
        # Check for explanatory language around keywords
        explanatory_indicators = [
            "because", "therefore", "thus", "hence",
            "implements", "executes", "achieves",
            "architecture", "design", "pattern",
            "specific", "detail", "example"
        ]
        
        deep_count = 0
        for f in findings:
            context_lower = f["context"].lower()
            if any(indicator in context_lower for indicator in explanatory_indicators):
                deep_count += 1
        
        return deep_count >= len(findings) * 0.5
    
    def cross_reference_claims(self, repo_evidence: Dict[str, List[Evidence]]) -> Evidence:
        """Cross-reference claims in PDF with actual code evidence"""
        if not self.chunks:
            return self._create_not_found_evidence("Host Analysis Accuracy")
        
        # Extract file paths mentioned in PDF
        mentioned_paths = self._extract_file_paths()
        
        # Verify against repo evidence
        verified_paths = []
        hallucinated_paths = []
        
        for path in mentioned_paths:
            # Check if any evidence has this path
            found = False
            for evidence_list in repo_evidence.values():
                for evidence in evidence_list:
                    if path in evidence.location:
                        found = True
                        break
                if found:
                    break
            
            if found:
                verified_paths.append(path)
            else:
                hallucinated_paths.append(path)
        
        content = f"Verified Paths ({len(verified_paths)}):\n"
        for p in verified_paths[:5]:
            content += f"- {p}\n"
        content += f"\nHallucinated Paths ({len(hallucinated_paths)}):\n"
        for p in hallucinated_paths[:5]:
            content += f"- {p}\n"
        
        return Evidence(
            goal="Host Analysis Accuracy",
            found=len(hallucinated_paths) == 0,
            content=content,
            location=self.pdf_path or "N/A",
            rationale=f"Verified {len(verified_paths)} paths, hallucinated {len(hallucinated_paths)}",
            confidence=1.0 - (len(hallucinated_paths) / max(1, len(mentioned_paths))),
            artifact_type="doc"
        )
    
    def _extract_file_paths(self) -> List[str]:
        """Extract file paths mentioned in the PDF"""
        paths = []
        path_pattern = r'[\w/]+\.(py|md|txt|json|yaml|yml)'
        
        for chunk in self.chunks:
            found_paths = re.findall(path_pattern, chunk["text"])
            paths.extend(found_paths)
        
        return list(set(paths))
    
    def analyze_concept_verification(self) -> Evidence:
        """Analyze deep understanding of key concepts"""
        concepts = {
            "Dialectical Synthesis": [
                "thesis", "antithesis", "synthesis", "dialectic",
                "conflict", "resolution", "debate", "argument"
            ],
            "Fan-In/Fan-Out": [
                "parallel", "concurrent", "branch", "merge",
                "aggregate", "synchronize", "split", "join"
            ],
            "Metacognition": [
                "self", "reflect", "evaluate", "judge",
                "meta", "think about thinking", "introspect"
            ],
            "State Synchronization": [
                "reducer", "state", "merge", "conflict",
                "update", "sync", "coordinate"
            ]
        }
        
        if not self.chunks:
            return self._create_not_found_evidence("Concept Verification")
        
        concept_findings = {}
        for concept, indicators in concepts.items():
            concept_findings[concept] = {
                "found": False,
                "contexts": [],
                "deep": False
            }
            
            for chunk in self.chunks:
                chunk_lower = chunk["text"].lower()
                for indicator in indicators:
                    if indicator in chunk_lower:
                        concept_findings[concept]["found"] = True
                        # Extract context
                        words = chunk["text"].split()
                        for i, word in enumerate(words):
                            if indicator in word.lower():
                                start = max(0, i - 5)
                                end = min(len(words), i + 6)
                                context = ' '.join(words[start:end])
                                concept_findings[concept]["contexts"].append({
                                    "context": context,
                                    "page": chunk["page"]
                                })
                                break
            
            # Check if deep explanation
            if concept_findings[concept]["found"]:
                # Count contexts with explanatory language
                deep_contexts = 0
                for ctx in concept_findings[concept]["contexts"]:
                    if any(ind in ctx["context"].lower() for ind in ["because", "therefore", "implement", "achieve"]):
                        deep_contexts += 1
                concept_findings[concept]["deep"] = deep_contexts >= len(concept_findings[concept]["contexts"]) * 0.3
        
        # Build evidence content
        content = "Concept Verification Analysis:\n\n"
        found_count = 0
        deep_count = 0
        
        for concept, findings in concept_findings.items():
            if findings["found"]:
                found_count += 1
                status = "✅ DEEP" if findings["deep"] else "⚠️ BUZZWORD"
                deep_count += 1 if findings["deep"] else 0
                content += f"{status}: {concept}\n"
                for ctx in findings["contexts"][:2]:  # Limit to first 2 contexts
                    content += f"  - Page {ctx['page']}: {ctx['context']}...\n"
                content += "\n"
            else:
                content += f"❌ MISSING: {concept}\n"
        
        overall_found = found_count >= 2
        overall_deep = deep_count >= 2
        
        return Evidence(
            goal="Concept Verification",
            found=overall_found,
            content=content,
            location=self.pdf_path or "N/A",
            rationale=f"Found {found_count}/4 concepts, deep explanation in {deep_count}",
            confidence=0.9 if overall_deep else 0.5 if overall_found else 0.2,
            artifact_type="doc"
        )
    
    def _create_not_found_evidence(self, goal: str) -> Evidence:
        """Create evidence for not found artifacts"""
        return Evidence(
            goal=goal,
            found=False,
            content="No document content available",
            location=self.pdf_path or "N/A",
            rationale="Document not ingested or empty",
            confidence=0.0,
            artifact_type="doc"
        )