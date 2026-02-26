"""
Multimodal analysis tools for diagram inspection using Groq's vision models.
"""

import base64
import os
from typing import List, Dict, Optional
from groq import Groq
from PIL import Image
import io


class VisionForensics:
    """Diagram analysis using multimodal LLMs"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.client = Groq(api_key=api_key or os.getenv('GROQ_API_KEY'))
        
        # Use Gemini 2.0 Flash via Groq for vision
        self.vision_model = "gemma2-9b-it"  # Groq's vision-capable model
    
    def encode_image(self, image_path: str) -> str:
        """Convert image to base64 for API"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def analyze_diagram(self, image_path: str, question: str) -> Dict:
        """
        Analyze diagram with specific forensic questions.
        Returns structured analysis.
        """
        try:
            base64_image = self.encode_image(image_path)
            
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": f"""Analyze this architecture diagram. Answer: {question}
                                
                                Provide structured output:
                                1. Diagram Type (LangGraph State Machine / Sequence Diagram / Generic Flowchart)
                                2. Key Components identified
                                3. Flow pattern (Parallel/Fan-out detected? Yes/No - explain)
                                4. Synchronization points visible
                                5. Structural description"""
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                temperature=0.1,  # Low temp for forensic accuracy
                max_tokens=1024
            )
            
            # Parse response into structured format
            analysis = self._parse_analysis(response.choices[0].message.content)
            return analysis
            
        except Exception as e:
            return {
                'error': str(e),
                'diagram_type': 'Unknown',
                'parallel_detected': False,
                'components': [],
                'description': 'Analysis failed'
            }
    
    def _parse_analysis(self, content: str) -> Dict:
        """Parse LLM response into structured format"""
        lines = content.split('\n')
        
        result = {
            'diagram_type': 'Unknown',
            'components': [],
            'parallel_detected': False,
            'synchronization_points': [],
            'description': ''
        }
        
        for line in lines:
            lower = line.lower()
            
            # Extract diagram type
            if 'diagram type' in lower or '1.' in line:
                if 'langgraph' in lower or 'state machine' in lower:
                    result['diagram_type'] = 'LangGraph State Machine'
                elif 'sequence' in lower:
                    result['diagram_type'] = 'Sequence Diagram'
                elif 'flowchart' in lower:
                    result['diagram_type'] = 'Generic Flowchart'
            
            # Check for parallel detection
            if 'parallel' in lower or 'fan-out' in lower:
                if 'yes' in lower or 'detected' in lower:
                    result['parallel_detected'] = True
            
            # Collect description
            if 'description' in lower or '5.' in line:
                result['description'] = line.split(':', 1)[-1].strip() if ':' in line else line
        
        return result
    
    def classify_diagram_type(self, image_path: str) -> str:
        """Quick classification of diagram type"""
        result = self.analyze_diagram(
            image_path, 
            "Is this a LangGraph state machine diagram, a sequence diagram, or a generic flowchart?"
        )
        return result.get('diagram_type', 'Unknown')
    
    def verify_parallel_flow(self, image_path: str) -> Dict:
        """Specifically verify if diagram shows parallel execution"""
        result = self.analyze_diagram(
            image_path,
            "Does this diagram show parallel execution paths (fan-out from a single node to multiple nodes)? Explain the flow pattern."
        )
        return {
            'has_parallel': result.get('parallel_detected', False),
            'details': result.get('description', ''),
            'confidence': 0.8  # Could be refined
        }