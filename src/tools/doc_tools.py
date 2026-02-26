"""
PDF analysis tools using Docling for production-grade parsing.
"""

import os
import tempfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import fitz  # PyMuPDF for image extraction
#from docling.document_parser import DocumentParser
from docling.document_converter import DocumentConverter
import json


class PDFForensics:
    """Advanced PDF analysis with RAG-lite capabilities"""
    
    def __init__(self):
        self.parser = DocumentConverter()
        self.document = None
        self.chunks = []
    
    def load_pdf(self, pdf_path: str) -> bool:
        """Load and parse PDF document"""
        try:
            # Use Docling for structured parsing
            self.document = self.parser.convert(pdf_path)
            
            # Extract text chunks with metadata
            self.chunks = self._chunk_document()
            
            return True
        except Exception as e:
            return False
    
    def _chunk_document(self, chunk_size: int = 1000) -> List[Dict]:
        """Split document into semantic chunks for RAG-lite"""
        chunks = []
        
        if not self.document:
            return chunks
        
        # Extract text by sections
        current_chunk = ""
        current_page = 1
        
        for element in self.document.elements:
            # Add element text to current chunk
            if hasattr(element, 'text'):
                if len(current_chunk) + len(element.text) > chunk_size:
                    # Save current chunk
                    if current_chunk:
                        chunks.append({
                            'text': current_chunk,
                            'page': current_page,
                            'type': element.__class__.__name__
                        })
                    current_chunk = element.text
                else:
                    current_chunk += " " + element.text if current_chunk else element.text
            
            # Update page number
            if hasattr(element, 'page'):
                current_page = element.page
        
        # Add final chunk
        if current_chunk:
            chunks.append({
                'text': current_chunk,
                'page': current_page,
                'type': 'final'
            })
        
        return chunks
    
    def query(self, question: str, top_k: int = 3) -> List[Dict]:
        """
        RAG-lite query against document chunks.
        Returns most relevant chunks for the question.
        """
        if not self.chunks:
            return []
        
        # Simple keyword matching (in production, use embeddings)
        keywords = question.lower().split()
        scored_chunks = []
        
        for chunk in self.chunks:
            score = 0
            chunk_text = chunk['text'].lower()
            
            for keyword in keywords:
                if keyword in chunk_text:
                    score += 1
            
            scored_chunks.append((score, chunk))
        
        # Sort by relevance
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        return [chunk for score, chunk in scored_chunks[:top_k] if score > 0]
    
    def extract_images(self, pdf_path: str) -> List[Dict]:
        """Extract images from PDF for multimodal analysis"""
        images = []
        
        try:
            pdf_document = fitz.open(pdf_path)
            
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    pix = fitz.Pixmap(pdf_document, xref)
                    
                    # Save to temp file
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                        pix.save(tmp.name)
                        images.append({
                            'page': page_num + 1,
                            'index': img_index,
                            'path': tmp.name,
                            'size': (pix.width, pix.height)
                        })
                    
                    pix = None
            
            pdf_document.close()
            
        except Exception as e:
            pass
        
        return images
    
    def extract_key_terms(self, terms: List[str]) -> Dict[str, List[Dict]]:
        """Extract specific terms with context"""
        results = {}
        
        for term in terms:
            contexts = []
            for chunk in self.chunks:
                if term.lower() in chunk['text'].lower():
                    # Extract sentence containing term
                    sentences = chunk['text'].split('.')
                    for sentence in sentences:
                        if term.lower() in sentence.lower():
                            contexts.append({
                                'context': sentence.strip(),
                                'page': chunk['page']
                            })
            if contexts:
                results[term] = contexts
        
        return results
    
    def cross_reference_claims(self, claims: List[str]) -> List[Dict]:
        """
        Verify claims made in PDF against actual content.
        Returns verification results.
        """
        results = []
        
        for claim in claims:
            # Search for claim in chunks
            found = False
            evidence = []
            
            for chunk in self.chunks:
                if claim.lower() in chunk['text'].lower():
                    found = True
                    evidence.append({
                        'text': chunk['text'][:200] + '...',  # Truncate
                        'page': chunk['page']
                    })
            
            results.append({
                'claim': claim,
                'verified': found,
                'evidence': evidence if found else None,
                'confidence': 0.9 if found else 0.1
            })
        
        return results