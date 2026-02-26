"""
Vision analysis tools for diagram inspection using Gemini Vision.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF
from PIL import Image
import io
import base64
import google.generativeai as genai
from dotenv import load_dotenv

from ..state import Evidence

load_dotenv()


class VisionInspectorTools:
    """Production-grade tools for diagram forensic analysis using Gemini Vision."""
    
    def __init__(self, gemini_model: str = "gemini-1.5-pro"):
        """Initialize with Gemini Vision model."""
        self.gemini_model = gemini_model
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel(gemini_model)
        
    def extract_images_from_pdf(self, pdf_path: str, max_images: int = 5) -> List[Image.Image]:
        """
        Extract images from PDF using PyMuPDF.
        
        Args:
            pdf_path: Path to PDF file
            max_images: Maximum number of images to extract
            
        Returns:
            List of PIL Image objects
        """
        images = []
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                if len(images) >= max_images:
                    break
                    
                page = doc[page_num]
                image_list = page.get_images()
                
                for img_index, img in enumerate(image_list):
                    if len(images) >= max_images:
                        break
                        
                    xref = img[0]
                    pix = fitz.Pixmap(doc, xref)
                    
                    if pix.n - pix.alpha < 4:  # Can be converted to RGB
                        img_data = pix.tobytes("ppm")
                        pil_image = Image.open(io.BytesIO(img_data))
                        images.append(pil_image)
                    
                    pix = None  # Free memory
            
            doc.close()
            
        except Exception as e:
            print(f"Error extracting images: {e}")
            
        return images
    
    def analyze_diagram(self, pdf_path: str) -> Evidence:
        """
        Analyze diagrams in PDF for architectural patterns.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Evidence with diagram analysis
        """
        try:
            # Extract images from PDF
            images = self.extract_images_from_pdf(pdf_path, max_images=3)
            
            if not images:
                return Evidence(
                    goal="Analyze architectural diagrams",
                    found=False,
                    content=None,
                    location=pdf_path,
                    rationale="No diagrams found in PDF",
                    confidence=0.8,
                    artifact_type="diagram"
                )
            
            # Analyze each image with Gemini Vision
            diagram_analyses = []
            
            for i, image in enumerate(images):
                # Convert PIL Image to bytes
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                
                # Create prompt for diagram analysis
                prompt = """
                Analyze this architectural diagram for the following:
                
                1. Diagram Type: Is it a LangGraph State Machine diagram, sequence diagram, or generic flowchart?
                2. Key Components: Identify nodes representing Detectives, Judges, Chief Justice
                3. Flow Pattern: Is it parallel (fan-out/fan-in) or linear?
                4. Accuracy: Does it match the Digital Courtroom architecture?
                5. Critical Elements: Look for:
                   - Parallel Detective branches
                   - Evidence Aggregation node
                   - Parallel Judicial bench (Prosecutor, Defense, TechLead)
                   - Chief Justice synthesis
                
                Provide analysis in this JSON format:
                {
                    "diagram_type": "string",
                    "has_parallel_flow": boolean,
                    "components_found": ["list", "of", "components"],
                    "missing_components": ["list"],
                    "accuracy_score": 1-5,
                    "structural_description": "string",
                    "flow_description": "string"
                }
                """
                
                response = self.model.generate_content([prompt, image])
                
                # Parse response
                try:
                    response_text = response.text
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}') + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = response_text[start_idx:end_idx]
                        analysis = json.loads(json_str)
                    else:
                        analysis = {"raw": response_text}
                except:
                    analysis = {"raw": response.text}
                
                diagram_analyses.append({
                    "image_index": i,
                    "analysis": analysis
                })
            
            # Synthesize findings
            has_parallel = any(a.get("analysis", {}).get("has_parallel_flow", False) 
                              for a in diagram_analyses if isinstance(a.get("analysis"), dict))
            
            avg_accuracy = 0
            count = 0
            for a in diagram_analyses:
                if isinstance(a.get("analysis"), dict):
                    score = a["analysis"].get("accuracy_score", 0)
                    if score:
                        avg_accuracy += score
                        count += 1
            
            if count > 0:
                avg_accuracy /= count
            
            result = {
                "diagrams_analyzed": len(diagram_analyses),
                "analyses": diagram_analyses,
                "summary": {
                    "has_parallel_flow": has_parallel,
                    "average_accuracy": avg_accuracy,
                    "overall_findings": "Parallel flow detected" if has_parallel else "Linear flow only"
                }
            }
            
            return Evidence(
                goal="Analyze architectural diagrams",
                found=True,
                content=str(result),
                location=pdf_path,
                rationale=f"Analyzed {len(diagram_analyses)} diagrams. "
                         f"Parallel flow: {has_parallel}. Avg accuracy: {avg_accuracy:.1f}/5",
                confidence=0.85,
                artifact_type="diagram"
            )
            
        except Exception as e:
            return Evidence(
                goal="Analyze architectural diagrams",
                found=False,
                content=None,
                location=pdf_path,
                rationale=f"Error analyzing diagrams: {str(e)}",
                confidence=0.6,
                artifact_type="diagram"
            )
    
    def classify_diagram_type(self, pdf_path: str) -> Evidence:
        """
        Specifically classify diagram types without detailed analysis.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Evidence with diagram classification
        """
        try:
            images = self.extract_images_from_pdf(pdf_path, max_images=3)
            
            if not images:
                return Evidence(
                    goal="Classify diagram types",
                    found=False,
                    content=None,
                    location=pdf_path,
                    rationale="No diagrams found in PDF",
                    confidence=0.8,
                    artifact_type="diagram"
                )
            
            classifications = []
            
            for i, image in enumerate(images):
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                
                prompt = """
                Classify this diagram into exactly one category:
                - LangGraph State Machine: Shows nodes, edges, state flow
                - Sequence Diagram: Shows message passing between components
                - Generic Flowchart: Simple boxes and arrows
                - Component Diagram: Shows system architecture without flow
                
                Also indicate if it shows parallel execution paths.
                
                Return as JSON: {"type": "string", "has_parallel": boolean, "confidence": 0.0-1.0}
                """
                
                response = self.model.generate_content([prompt, image])
                
                try:
                    response_text = response.text
                    start_idx = response_text.find('{')
                    end_idx = response_text.rfind('}') + 1
                    if start_idx >= 0 and end_idx > start_idx:
                        json_str = response_text[start_idx:end_idx]
                        classification = json.loads(json_str)
                    else:
                        classification = {"type": "unknown", "has_parallel": False}
                except:
                    classification = {"type": "unknown", "has_parallel": False}
                
                classifications.append(classification)
            
            # Count types
            type_counts = {}
            has_parallel_any = False
            for c in classifications:
                type_name = c.get("type", "unknown")
                type_counts[type_name] = type_counts.get(type_name, 0) + 1
                if c.get("has_parallel", False):
                    has_parallel_any = True
            
            most_common_type = max(type_counts, key=type_counts.get) if type_counts else "unknown"
            
            result = {
                "classifications": classifications,
                "summary": {
                    "most_common_type": most_common_type,
                    "type_distribution": type_counts,
                    "has_parallel_detected": has_parallel_any
                }
            }
            
            return Evidence(
                goal="Classify diagram types",
                found=True,
                content=str(result),
                location=pdf_path,
                rationale=f"Classified {len(classifications)} diagrams. "
                         f"Most common: {most_common_type}. Parallel: {has_parallel_any}",
                confidence=0.9,
                artifact_type="diagram"
            )
            
        except Exception as e:
            return Evidence(
                goal="Classify diagram types",
                found=False,
                content=None,
                location=pdf_path,
                rationale=f"Error classifying diagrams: {str(e)}",
                confidence=0.6,
                artifact_type="diagram"
            )