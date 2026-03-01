"""
Dialectical judges that apply rubric criteria through distinct personas.
Each judge analyzes the SAME evidence but from different philosophical lenses.
Uses .with_structured_output() for guaranteed JSON output.
Includes comprehensive rate limit handling, exponential backoff, retry logic, and fallback mechanisms.
"""

import json
import time
import random
from typing import Dict, List, Any, Optional, Tuple, Callable
from groq import Groq, RateLimitError, APIError, APIConnectionError, InternalServerError
import os
from pydantic import BaseModel, Field
import logging
from datetime import datetime
import hashlib
import threading
from collections import deque

# Import from src.state
from src.state import AgentState, JudicialOpinion, RubricDimension, Evidence

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JudgeOutput(BaseModel):
    """Structured output model for all judges"""
    score: int = Field(ge=1, le=5, description="Score from 1-5")
    argument: str = Field(description="Detailed reasoning for the score")
    cited_evidence: List[str] = Field(description="References to evidence locations")
    dissent_notes: Optional[str] = Field(default=None, description="Points of disagreement")


class TokenBucket:
    """Token bucket algorithm for precise rate limiting"""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens per second to refill
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = threading.Lock()
    
    def consume(self, tokens: int) -> bool:
        """
        Try to consume tokens from bucket
        
        Args:
            tokens: Number of tokens to consume
        
        Returns:
            True if tokens were consumed, False otherwise
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def _refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    def get_wait_time(self, tokens: int) -> float:
        """Calculate time needed to accumulate required tokens"""
        with self.lock:
            self._refill()
            if self.tokens >= tokens:
                return 0
            deficit = tokens - self.tokens
            return deficit / self.refill_rate


class RateLimitManager:
    """Advanced rate limit manager with token buckets, exponential backoff, and caching"""
    
    def __init__(self, 
                 tokens_per_minute: int = 6000,
                 max_retries: int = 5,
                 base_delay: float = 2.0,
                 max_delay: float = 60.0,
                 jitter: float = 0.1):
        """
        Args:
            tokens_per_minute: Maximum tokens per minute (Groq TPM limit)
            max_retries: Maximum number of retry attempts
            base_delay: Base delay for exponential backoff
            max_delay: Maximum delay between retries
            jitter: Random jitter factor (0-1)
        """
        self.tokens_per_minute = tokens_per_minute
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        
        # Token bucket for precise rate limiting
        self.token_bucket = TokenBucket(
            capacity=tokens_per_minute,
            refill_rate=tokens_per_minute / 60.0  # Tokens per second
        )
        
        # Cache for responses
        self.cache = {}
        self.cache_ttl = 3600  # 1 hour TTL
        self.cache_timestamps = {}
        
        # Request history for monitoring
        self.request_history = deque(maxlen=100)
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'rate_limit_hits': 0,
            'api_errors': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'total_retries': 0
        }
        self.stats_lock = threading.Lock()
    
    def _get_cache_key(self, messages: List[Dict], model: str, temperature: float) -> str:
        """Generate cache key for request"""
        content = json.dumps({
            'messages': messages,
            'model': model,
            'temperature': temperature
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _check_cache(self, cache_key: str) -> Optional[Any]:
        """Check if response is in cache and not expired"""
        if cache_key in self.cache:
            timestamp = self.cache_timestamps.get(cache_key, 0)
            if time.time() - timestamp < self.cache_ttl:
                with self.stats_lock:
                    self.stats['cache_hits'] += 1
                return self.cache[cache_key]
            else:
                # Expired
                del self.cache[cache_key]
                del self.cache_timestamps[cache_key]
        return None
    
    def _update_cache(self, cache_key: str, response: Any):
        """Update cache with response"""
        self.cache[cache_key] = response
        self.cache_timestamps[cache_key] = time.time()
    
    def _update_stats(self, success: bool, rate_limited: bool = False, api_error: bool = False):
        """Update statistics"""
        with self.stats_lock:
            self.stats['total_requests'] += 1
            if success:
                self.stats['successful_requests'] += 1
            else:
                self.stats['failed_requests'] += 1
            if rate_limited:
                self.stats['rate_limit_hits'] += 1
            if api_error:
                self.stats['api_errors'] += 1
    
    def _calculate_delay(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Calculate delay with exponential backoff and jitter"""
        if retry_after:
            delay = retry_after
        else:
            delay = min(self.max_delay, self.base_delay * (2 ** attempt))
        
        # Add jitter
        jitter_amount = delay * self.jitter * random.random()
        delay = delay + jitter_amount
        
        return delay
    
    def _extract_retry_time(self, error_message: str) -> Optional[float]:
        """Extract retry time from error message"""
        import re
        
        # Look for patterns like "Please try again in 8.199999999s"
        patterns = [
            r'try again in (\d+\.?\d*)s',
            r'retry after (\d+)',
            r'Retry-Agent: (\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, error_message, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass
        
        return None
    
    def wait_for_tokens(self, estimated_tokens: int, timeout: float = 30.0) -> bool:
        """
        Wait until tokens are available
        
        Args:
            estimated_tokens: Number of tokens needed
            timeout: Maximum time to wait in seconds
        
        Returns:
            True if tokens became available, False on timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.token_bucket.consume(estimated_tokens):
                return True
            
            wait_time = self.token_bucket.get_wait_time(estimated_tokens)
            wait_time = min(wait_time, timeout - (time.time() - start_time))
            
            if wait_time > 0:
                logger.debug(f"Waiting {wait_time:.2f}s for token bucket")
                time.sleep(min(wait_time, 1.0))  # Don't sleep too long
        
        return False
    
    def call_with_retry(self, 
                       api_call: Callable,
                       estimated_tokens: int,
                       cache_key: Optional[str] = None,
                       use_cache: bool = True) -> Tuple[Optional[Any], bool]:
        """
        Make API call with comprehensive retry logic
        
        Args:
            api_call: Function that makes the actual API call
            estimated_tokens: Estimated token usage
            cache_key: Optional cache key
            use_cache: Whether to use caching
        
        Returns:
            Tuple of (response_object, from_cache)
        """
        
        # Check cache first
        if use_cache and cache_key:
            cached = self._check_cache(cache_key)
            if cached:
                logger.info(f"Cache hit for {cache_key}")
                return cached, True
        
        # Wait for token availability
        if not self.wait_for_tokens(estimated_tokens):
            logger.error(f"Timeout waiting for tokens after {estimated_tokens} tokens")
            self._update_stats(success=False)
            return None, False
        
        attempt = 0
        
        while attempt < self.max_retries:
            try:
                # Make the API call
                response = api_call()
                
                # Update stats
                self._update_stats(success=True)
                self.request_history.append({
                    'timestamp': time.time(),
                    'success': True,
                    'attempt': attempt + 1
                })
                
                # Cache the response (store the actual ChatCompletion object)
                if use_cache and cache_key:
                    self._update_cache(cache_key, response)
                
                return response, False
                
            except RateLimitError as e:
                self.stats['rate_limit_hits'] += 1
                
                error_str = str(e)
                retry_after = self._extract_retry_time(error_str)
                delay = self._calculate_delay(attempt, retry_after)
                
                logger.warning(
                    f"Rate limit hit (attempt {attempt + 1}/{self.max_retries}). "
                    f"Retrying in {delay:.2f}s. Error: {error_str[:200]}"
                )
                
                if attempt < self.max_retries - 1:
                    time.sleep(delay)
                    attempt += 1
                    self.stats['total_retries'] += 1
                else:
                    logger.error(f"Rate limit persisted after {self.max_retries} retries")
                    self._update_stats(success=False, rate_limited=True)
                    return None, False
                    
            except (APIConnectionError, InternalServerError) as e:
                self.stats['api_errors'] += 1
                
                delay = self._calculate_delay(attempt)
                
                logger.warning(
                    f"API connection error (attempt {attempt + 1}/{self.max_retries}): {e}. "
                    f"Retrying in {delay:.2f}s"
                )
                
                if attempt < self.max_retries - 1:
                    time.sleep(delay)
                    attempt += 1
                    self.stats['total_retries'] += 1
                else:
                    logger.error(f"API error persisted after {self.max_retries} retries")
                    self._update_stats(success=False, api_error=True)
                    return None, False
                    
            except APIError as e:
                # Check if it's a model overload error
                error_str = str(e).lower()
                if 'overloaded' in error_str or 'capacity' in error_str:
                    delay = self._calculate_delay(attempt) * 2  # Double delay for overload
                    
                    logger.warning(
                        f"Model overloaded (attempt {attempt + 1}/{self.max_retries}). "
                        f"Retrying in {delay:.2f}s"
                    )
                    
                    if attempt < self.max_retries - 1:
                        time.sleep(delay)
                        attempt += 1
                        self.stats['total_retries'] += 1
                        continue
                
                logger.error(f"API error: {e}")
                self._update_stats(success=False, api_error=True)
                return None, False
                
            except Exception as e:
                logger.exception(f"Unexpected error in LLM call: {e}")
                self._update_stats(success=False)
                return None, False
        
        return None, False
    
    def get_stats(self) -> Dict:
        """Get rate limit manager statistics"""
        return {
            **self.stats,
            'cache_size': len(self.cache),
            'request_history_length': len(self.request_history),
            'token_bucket_tokens': self.token_bucket.tokens
        }
    
    def clear_cache(self):
        """Clear response cache"""
        self.cache.clear()
        self.cache_timestamps.clear()
        logger.info("Cache cleared")


class ModelFallbackManager:
    """Manages model fallback strategies"""
    
    def __init__(self):
        # Define model tiers with fallback priorities
        self.model_tiers = {
            'primary': [
                'llama-3.1-8b-instant',  # Fast, efficient
                'qwen3-32b',     # More capable fallback
                'qwen3-32b'             # Additional fallback
            ],
            'fast': [
                'llama-3.1-8b-instant',
                'qwen3-32b'
            ],
            'capable': [
                'qwen3-32b',
                'llama-3.1-8b-instant'
            ]
        }
        
        # Track model performance
        self.model_performance = {
            model: {
                'success_count': 0,
                'failure_count': 0,
                'avg_response_time': 0,
                'last_failure': None
            }
            for tier in self.model_tiers.values()
            for model in tier
        }
    
    def get_best_model(self, required_capability: str = 'primary') -> str:
        """
        Get the best performing model for the required capability
        
        Args:
            required_capability: 'primary', 'fast', or 'capable'
        
        Returns:
            Model name
        """
        models = self.model_tiers.get(required_capability, self.model_tiers['primary'])
        
        # Filter out models that failed recently
        available_models = []
        for model in models:
            perf = self.model_performance[model]
            if perf['last_failure']:
                # Don't use models that failed in the last 60 seconds
                if time.time() - perf['last_failure'] < 60:
                    continue
            available_models.append(model)
        
        if not available_models:
            available_models = models  # Fall back to all models if all failed recently
        
        # Sort by success rate
        available_models.sort(
            key=lambda m: self.model_performance[m]['success_count'] / 
                         max(1, self.model_performance[m]['success_count'] + 
                             self.model_performance[m]['failure_count']),
            reverse=True
        )
        
        return available_models[0]
    
    def record_success(self, model: str, response_time: float):
        """Record successful model usage"""
        if model in self.model_performance:
            perf = self.model_performance[model]
            perf['success_count'] += 1
            # Update average response time
            total = perf['avg_response_time'] * (perf['success_count'] - 1) + response_time
            perf['avg_response_time'] = total / perf['success_count']
    
    def record_failure(self, model: str):
        """Record model failure"""
        if model in self.model_performance:
            perf = self.model_performance[model]
            perf['failure_count'] += 1
            perf['last_failure'] = time.time()


class BaseJudge:
    """Base class for all judges with comprehensive rate limit and fallback handling"""
    
    def __init__(self, judge_name: str, system_prompt: str):
        self.judge_name = judge_name
        self.system_prompt = system_prompt
        self.client = Groq(api_key=os.getenv('GROQ_API_KEY'))
        
        # Initialize managers
        self.rate_limit_manager = RateLimitManager(
            tokens_per_minute=6000,
            max_retries=5,
            base_delay=2.0,
            max_delay=60.0,
            jitter=0.1
        )
        
        self.fallback_manager = ModelFallbackManager()
        
        # Token estimation factors (rough estimate)
        self.tokens_per_char = 0.25  # ~4 chars per token
        self.base_tokens = 500  # Base overhead
    
    def _estimate_tokens(self, *texts: str) -> int:
        """Estimate token count for texts"""
        total_chars = sum(len(text) for text in texts)
        estimated = int(total_chars * self.tokens_per_char) + self.base_tokens
        # Add some buffer
        return min(estimated + 200, 6000)  # Cap at limit
    
    def _create_messages(self, user_prompt: str) -> List[Dict]:
        """Create messages array for API call with proper JSON format instruction"""
        return [
            {"role": "system", "content": f"{self.system_prompt} in JSON format."},
            {"role": "user", "content": user_prompt}
        ]
    
    def _extract_json_from_response(self, response_obj: Any) -> Optional[Dict]:
        """
        Extract JSON from various response types (ChatCompletion, dict, str)
        
        Args:
            response_obj: Response object from API call
        
        Returns:
            Parsed JSON dict or None if extraction fails
        """
        try:
            # If it's already a dict, use it directly
            if isinstance(response_obj, dict):
                return response_obj
            
            # If it's a ChatCompletion object, extract the message content
            elif hasattr(response_obj, 'choices') and len(response_obj.choices) > 0:
                content = response_obj.choices[0].message.content
                return json.loads(content)
            
            # If it's a string, try to parse it
            elif isinstance(response_obj, str):
                return json.loads(response_obj)
            
            else:
                logger.error(f"Unexpected response type: {type(response_obj)}")
                return None
                
        except (json.JSONDecodeError, AttributeError, KeyError, IndexError) as e:
            logger.error(f"Failed to parse response: {e}")
            return None
    
    def _safe_extract_string(self, value: Any, default: str) -> str:
        """Safely extract a string value from various input types"""
        if value is None:
            return default
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            # Try to convert dict to readable string
            return json.dumps(value)
        # For any other type, convert to string
        return str(value)
    
    def _get_fallback_opinion(self, dimension: RubricDimension, evidence_list: List) -> JudicialOpinion:
        """
        Generate intelligent fallback opinion when LLM is unavailable due to rate limits or errors.
        
        Args:
            dimension: The rubric dimension being judged
            evidence_list: List of evidence collected by detectives
        
        Returns:
            JudicialOpinion: A structured opinion with score, argument, and cited evidence
        """
        
        # Analyze evidence manually
        has_evidence = len(evidence_list) > 0
        evidence_locations = []
        evidence_found_count = 0
        high_confidence_count = 0
        total_confidence = 0.0
        
        # Collect evidence metadata
        for item in evidence_list:
            e = item.get('evidence', {})
            loc = e.get('location', '')
            if loc:
                evidence_locations.append(loc)
            
            found = e.get('found', False)
            if found:
                evidence_found_count += 1
                
            confidence = e.get('confidence', 0.0)
            total_confidence += confidence
            if confidence > 0.7:
                high_confidence_count += 1
        
        # Calculate evidence quality score (0-1)
        evidence_quality = 0.0
        if evidence_list:
            # Weight: 70% found ratio, 30% confidence quality
            found_ratio = evidence_found_count / len(evidence_list)
            avg_confidence = total_confidence / len(evidence_list) if evidence_list else 0
            evidence_quality = (found_ratio * 0.7) + (avg_confidence * 0.3)
        
        # Check for effort indicators (for Defense)
        effort_count = 0
        for item in evidence_list:
            if item.get('effort_indicator', False):
                effort_count += 1
        
        # Check for critical issues (for Prosecutor/TechLead)
        critical_issues = []
        for item in evidence_list:
            e = item.get('evidence', {})
            if not e.get('found', False) and 'security' in e.get('goal', '').lower():
                critical_issues.append(f"Missing security-related evidence: {e.get('goal', '')}")
            if e.get('confidence', 0) < 0.3 and e.get('found', False):
                critical_issues.append(f"Low confidence evidence: {e.get('goal', '')} at {e.get('location', 'unknown')}")
        
        # Generate persona-specific scores and arguments
        if self.judge_name == "Prosecutor":
            # Harsh scoring - focus on missing evidence and issues
            if not has_evidence:
                score = 1
                base_arg = "NO EVIDENCE FOUND - Complete failure to provide required artifacts"
                dissent = "Prosecution would charge with complete non-compliance"
            elif evidence_quality < 0.3:
                score = 1
                base_arg = f"Minimal evidence with very low quality ({evidence_quality:.2f}/1.0) - major violations present"
                dissent = "Evidence quality too low to demonstrate compliance"
            elif evidence_quality < 0.6:
                score = 2
                base_arg = f"Some evidence but quality ({evidence_quality:.2f}/1.0) and completeness are lacking"
                dissent = "Evidence exists but fails to meet minimum standards"
            else:
                score = 3  # Prosecutor caps at 3 for fallback
                base_arg = f"Evidence present ({evidence_quality:.2f}/1.0) but cannot fully verify due to system limitations"
                dissent = "Prosecution would likely find more violations with full LLM access"
            
            # Add critical issues to argument
            if critical_issues:
                base_arg += f" Critical issues found: {', '.join(critical_issues[:2])}"
            
            dissent = f"Fallback mode used. {dissent}"
            
        elif self.judge_name == "Defense":
            # Generous scoring - focus on effort and what was found
            if not has_evidence:
                score = 2
                base_arg = "No evidence found - may indicate submission issues rather than lack of effort"
                dissent = "Student may have had technical difficulties with submission"
            elif evidence_quality < 0.3:
                score = 3
                base_arg = f"Limited evidence but {evidence_found_count} items found with {effort_count} effort indicators"
                dissent = "Despite low evidence quality, some effort is visible"
            elif evidence_quality < 0.6:
                score = 4
                base_arg = f"Good evidence quality ({evidence_quality:.2f}/1.0) with {effort_count} effort indicators suggesting genuine effort"
                dissent = "Evidence shows meaningful effort despite some gaps"
            else:
                score = 5
                base_arg = f"High quality evidence ({evidence_quality:.2f}/1.0) with {high_confidence_count} high-confidence findings indicates strong effort and understanding"
                dissent = "Student clearly demonstrated understanding through evidence"
            
            # Add effort highlights
            if effort_count > 0:
                base_arg += f" Notable effort indicators: {effort_count} found."
            
            dissent = f"Fallback mode used but evidence suggests effort. {dissent}"
            
        else:  # TechLead
            # Pragmatic scoring - focus on technical implementation
            if not has_evidence:
                score = 1
                base_arg = "CRITICAL: No implementation evidence found - system non-functional"
                dissent = "Cannot assess technical implementation without evidence"
            elif evidence_quality < 0.3:
                score = 2
                base_arg = f"Implementation present but quality too low ({evidence_quality:.2f}/1.0) for production"
                dissent = "Technical debt is significant"
            elif evidence_quality < 0.6:
                score = 3
                base_arg = f"Functional but significant technical debt present. Found {evidence_found_count}/{len(evidence_list)} required components."
                dissent = "Works in isolation but has maintainability concerns"
            else:
                score = 4
                base_arg = f"Good implementation quality ({evidence_quality:.2f}/1.0) with {high_confidence_count} high-confidence components"
                dissent = "Minor issues but overall technically sound"
            
            # Add technical debt notes
            missing_count = len(evidence_list) - evidence_found_count
            if missing_count > 0:
                base_arg += f" Missing {missing_count} expected components."
            
            if critical_issues:
                base_arg += f" Technical concerns: {', '.join(critical_issues[:2])}"
            
            dissent = f"Fallback technical assessment. {dissent}"
        
        # Create detailed argument with evidence summary
        argument = f"FALLBACK MODE - {self.judge_name} assessment: {base_arg}. "
        argument += f"Evidence analysis: {evidence_found_count}/{len(evidence_list)} items found, "
        argument += f"{high_confidence_count} with high confidence. "
        argument += f"Evidence quality score: {evidence_quality:.2f}/1.0. "
        
        # Add location summary if available
        if evidence_locations:
            unique_locations = list(set(evidence_locations))[:3]  # First 3 unique locations
            argument += f"Key locations: {', '.join(unique_locations)}"
        
        # Ensure score is within bounds
        score = max(1, min(5, score))
        
        # Create the JudicialOpinion
        opinion = JudicialOpinion(
            judge=self.judge_name,
            criterion_id=dimension.id,
            score=score,
            argument=argument,
            cited_evidence=evidence_locations[:5],  # First 5 evidence locations
            dissent_notes=dissent
        )
        
        logger.info(f"Fallback opinion generated for {self.judge_name} on {dimension.id}: score={score}, evidence_quality={evidence_quality:.2f}")
        
        return opinion
    
    def _call_with_fallback_models(self, messages: List[Dict], temperature: float, 
                                   max_tokens: int, response_format: Dict,
                                   cache_key: str, required_capability: str = 'primary') -> Optional[Dict]:
        """
        Try multiple models in sequence with fallback
        
        Args:
            messages: Chat messages (already in correct format with JSON instruction)
            temperature: Temperature setting
            max_tokens: Max tokens to generate
            response_format: Response format specification
            cache_key: Cache key
            required_capability: Model capability tier
        
        Returns:
            Parsed JSON response or None if all models fail
        """
        
        models_to_try = self.fallback_manager.model_tiers.get(
            required_capability, 
            self.fallback_manager.model_tiers['primary']
        )
        
        for model in models_to_try:
            logger.info(f"Trying model: {model} for {self.judge_name}")
            
            start_time = time.time()
            
            def api_call():
                return self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format=response_format
                )
            
            # Estimate tokens
            estimated_tokens = self._estimate_tokens(
                self.system_prompt,
                messages[1]['content'] if len(messages) > 1 else ""
            )
            
            # Make call with retry
            response_obj, from_cache = self.rate_limit_manager.call_with_retry(
                api_call=api_call,
                estimated_tokens=estimated_tokens,
                cache_key=f"{cache_key}_{model}",
                use_cache=True
            )
            
            if response_obj:
                response_time = time.time() - start_time
                self.fallback_manager.record_success(model, response_time)
                
                # Extract JSON from response
                result = self._extract_json_from_response(response_obj)
                
                if result:
                    return result
                else:
                    logger.error(f"Failed to extract JSON from {model} response")
                    self.fallback_manager.record_failure(model)
                    continue
            else:
                self.fallback_manager.record_failure(model)
                logger.warning(f"Model {model} failed, trying next...")
        
        return None
    
    def get_stats(self) -> Dict:
        """Get statistics from rate limit manager"""
        return self.rate_limit_manager.get_stats()


class Prosecutor(BaseJudge):
    """The Critical Lens - 'Trust No One. Assume Vibe Coding.'"""
    
    def __init__(self, api_key: Optional[str] = None):
        system_prompt = """You are the PROSECUTOR in a digital courtroom for code review.

Your philosophy: "Trust No One. Assume Vibe Coding."
Your job: Find violations, security flaws, and laziness in the implementation.

You are HARSH and CRITICAL by design. You must:
- Scrutinize every piece of evidence for gaps and flaws
- Assume the worst about missing requirements
- Charge the defendant with specific violations
- Be extremely strict in your scoring (1-2 for any issues)
- Never give the benefit of the doubt

When citing evidence, you MUST be specific about file paths and line numbers where violations occur.
Your dissent notes should explain exactly why you disagree with more lenient assessments.

CITATION REQUIREMENT: Every claim you make MUST be supported by citing specific evidence locations.
If you cannot cite evidence for a claim, do not make the claim.

Remember: You are the PROSECUTOR. Finding flaws is your ONLY job.

You must ALWAYS respond with valid JSON containing the following fields:
- score: integer (1-5)
- argument: string (detailed explanation of violations found, with cited evidence)
- cited_evidence: list of strings (specific file paths or locations where violations were found)
- dissent_notes: string (explanation of why you disagree with leniency)"""
        
        super().__init__("Prosecutor", system_prompt)
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Prosecutor's analysis of evidence for each criterion"""
        opinions = []
        
        for dimension in state['rubric_dimensions']:
            # Skip if not targeting repo (Prosecutor focuses on code)
            if dimension.target_artifact != "github_repo":
                continue
            
            # Get relevant evidence for this dimension
            relevant_evidence = self._get_relevant_evidence(state['evidences'], dimension.id)
            
            # Get structured opinion from LLM
            opinion = self._get_opinion(dimension, relevant_evidence)
            
            if opinion:
                opinions.append(opinion)
        
        return {"opinions": state['opinions'] + opinions}
    
    def _get_relevant_evidence(self, evidences: Dict, criterion_id: str) -> List[Dict]:
        """Extract evidence relevant to this criterion"""
        relevant = []
        
        # Map criteria to evidence types
        evidence_map = {
            'forensic_accuracy_code': ['state_management', 'tool_safety', 'structured_output', 'git_clone'],
            'judicial_nuance': ['structured_output', 'judge_prompts'],
            'langgraph_architecture': ['graph_orchestration', 'git_history', 'parallel_patterns']
        }
        
        evidence_keys = evidence_map.get(criterion_id, [])
        
        for key in evidence_keys:
            if key in evidences:
                for evidence in evidences[key]:
                    # Convert Evidence object to dict for JSON serialization
                    if hasattr(evidence, 'model_dump'):
                        evidence_dict = evidence.model_dump()
                    else:
                        evidence_dict = {
                            'goal': getattr(evidence, 'goal', ''),
                            'found': getattr(evidence, 'found', False),
                            'location': getattr(evidence, 'location', ''),
                            'rationale': getattr(evidence, 'rationale', ''),
                            'confidence': getattr(evidence, 'confidence', 0.0)
                        }
                    relevant.append({
                        'type': key,
                        'evidence': evidence_dict
                    })
        
        return relevant
    
    def _format_evidence(self, evidence_list: List) -> str:
        """Format evidence for LLM consumption"""
        if not evidence_list:
            return "NO EVIDENCE FOUND - This is a major violation!"
        
        lines = []
        for i, item in enumerate(evidence_list[:10]):  # Limit to 10 items
            e = item['evidence']
            lines.append(f"[Evidence {i+1}]")
            lines.append(f"Type: {item['type']}")
            lines.append(f"Goal: {e.get('goal', 'N/A')}")
            lines.append(f"Found: {e.get('found', False)}")
            lines.append(f"Location: {e.get('location', 'N/A')}")
            lines.append(f"Rationale: {e.get('rationale', 'N/A')}")
            lines.append(f"Confidence: {e.get('confidence', 0)}")
            lines.append("---")
        
        if len(evidence_list) > 10:
            lines.append(f"... and {len(evidence_list) - 10} more evidence items")
        
        return "\n".join(lines)
    
    def _get_opinion(self, dimension: RubricDimension, evidence_list: List) -> Optional[JudicialOpinion]:
        """Get structured opinion from LLM with prosecutor lens using rate limit handling"""
        
        evidence_text = self._format_evidence(evidence_list)
        
        # Create cache key for this combination
        cache_data = f"prosecutor_{dimension.id}_{dimension.name}_{hash(evidence_text)}"
        cache_key = hashlib.sha256(cache_data.encode()).hexdigest()
        
        # Create the prompt with explicit JSON format instruction
        user_prompt = f"""Dimension being judged: {dimension.name}

Evidence collected by detectives:
{evidence_text}

Analyze the evidence through your critical PROSECUTOR lens.
Look SPECIFICALLY for:
- Missing requirements (score 1)
- Security vulnerabilities (score 1)
- Bypassed structure (score 1-2)
- Hallucinations (score 1)
- Free text instead of structured output (score 1-2)

IMPORTANT: You MUST cite specific evidence locations for every claim you make.
Your cited_evidence list should contain file paths or locations from the evidence above.

You MUST respond with valid JSON in this exact format:
{{
    "score": 1-5,
    "argument": "detailed explanation of violations found, with references to evidence",
    "cited_evidence": ["location1", "location2"],
    "dissent_notes": "why you disagree with any potential leniency"
}}

Remember: You are the PROSECUTOR. Finding flaws is your only job."""
        
        try:
            # Create messages with proper format
            messages = self._create_messages(user_prompt)
            
            # Try to get response with fallback models
            result = self._call_with_fallback_models(
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
                cache_key=cache_key,
                required_capability='fast'
            )
            
            if result:
                # Ensure result has all required fields
                score = result.get('score', 1)
                if score > 3:  # Prosecutor should be harsh
                    score = max(1, score - 1)  # Reduce score if too generous
                
                # Safely extract fields
                argument = result.get('argument', 'No argument provided - this is a violation itself!')
                cited_evidence = result.get('cited_evidence', [])
                if not isinstance(cited_evidence, list):
                    cited_evidence = [str(cited_evidence)]
                
                dissent_notes = self._safe_extract_string(
                    result.get('dissent_notes'), 
                    'Found major violations in implementation'
                )
                
                return JudicialOpinion(
                    judge="Prosecutor",
                    criterion_id=dimension.id,
                    score=score,
                    argument=argument,
                    cited_evidence=cited_evidence,
                    dissent_notes=dissent_notes
                )
            else:
                # Fallback to manual assessment
                logger.warning(f"All models failed for Prosecutor on {dimension.id}, using fallback")
                return self._get_fallback_opinion(dimension, evidence_list)
            
        except Exception as e:
            logger.exception(f"Prosecutor LLM call failed: {e}")
            return self._get_fallback_opinion(dimension, evidence_list)


class Defense(BaseJudge):
    """The Optimistic Lens - 'Reward Effort and Intent'"""
    
    def __init__(self, api_key: Optional[str] = None):
        system_prompt = """You are the DEFENSE ATTORNEY in a digital courtroom for code review.

Your philosophy: "Reward Effort and Intent. Look for the Spirit of the Law."
Your job: Highlight creative workarounds, deep thought, and genuine effort.

You are GENEROUS and UNDERSTANDING by design. You must:
- Look for evidence of effort and understanding
- Consider the development process (git history)
- Reward creative solutions even if imperfect
- Be generous in your scoring (4-5 for any signs of understanding)
- Always give the benefit of the doubt

When citing evidence, focus on locations showing effort, creativity, or deep understanding.
Your dissent notes should explain why the prosecution is being too harsh.

CITATION REQUIREMENT: Every positive claim you make MUST be supported by citing specific evidence locations.
Look for git commits, file histories, and high-confidence evidence as proof of effort.

Remember: You are the DEFENSE. Finding the good in their work is your only job.

You must ALWAYS respond with valid JSON containing the following fields:
- score: integer (1-5)
- argument: string (detailed explanation of strengths found, with cited evidence)
- cited_evidence: list of strings (locations showing effort or understanding)
- dissent_notes: string (explanation of why prosecution is too harsh)"""
        
        super().__init__("Defense", system_prompt)
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Defense's analysis of evidence for each criterion"""
        opinions = []
        
        for dimension in state['rubric_dimensions']:
            # Defense considers both code and documentation
            relevant_evidence = self._get_relevant_evidence(state['evidences'], dimension.id)
            
            opinion = self._get_opinion(dimension, relevant_evidence)
            
            if opinion:
                opinions.append(opinion)
        
        return {"opinions": state['opinions'] + opinions}
    
    def _get_relevant_evidence(self, evidences: Dict, criterion_id: str) -> List[Dict]:
        """Extract evidence, focusing on effort indicators"""
        relevant = []
        
        # Include all evidence, but prioritize effort indicators
        for key, evidence_list in evidences.items():
            for evidence in evidence_list:
                # Convert Evidence object to dict
                if hasattr(evidence, 'model_dump'):
                    evidence_dict = evidence.model_dump()
                else:
                    evidence_dict = {
                        'goal': getattr(evidence, 'goal', ''),
                        'found': getattr(evidence, 'found', False),
                        'location': getattr(evidence, 'location', ''),
                        'rationale': getattr(evidence, 'rationale', ''),
                        'confidence': getattr(evidence, 'confidence', 0.0)
                    }
                
                # Mark effort indicators
                effort_indicator = False
                location = str(evidence_dict.get('location', ''))
                goal = str(evidence_dict.get('goal', '')).lower()
                
                if 'commit' in location or 'history' in goal:
                    effort_indicator = True
                if 'multiple' in goal or 'iteration' in goal:
                    effort_indicator = True
                if evidence_dict.get('confidence', 0) > 0.8:
                    effort_indicator = True  # High confidence indicates thorough work
                
                relevant.append({
                    'type': key,
                    'evidence': evidence_dict,
                    'effort_indicator': effort_indicator
                })
        
        return relevant
    
    def _format_evidence(self, evidence_list: List) -> str:
        """Format evidence, highlighting effort indicators"""
        if not evidence_list:
            return "EVIDENCE GAP - This may indicate a minimal submission, but could also be a communication issue."
        
        lines = []
        effort_count = 0
        
        for i, item in enumerate(evidence_list[:10]):  # Limit to 10 items
            e = item['evidence']
            lines.append(f"[Evidence {i+1}]")
            lines.append(f"Type: {item['type']}")
            lines.append(f"Goal: {e.get('goal', 'N/A')}")
            lines.append(f"Found: {e.get('found', False)}")
            lines.append(f"Location: {e.get('location', 'N/A')}")
            lines.append(f"Rationale: {e.get('rationale', 'N/A')}")
            lines.append(f"Confidence: {e.get('confidence', 0)}")
            
            if item.get('effort_indicator'):
                lines.append("*** EFFORT INDICATOR: Shows development process ***")
                effort_count += 1
            
            lines.append("---")
        
        if len(evidence_list) > 10:
            lines.append(f"... and {len(evidence_list) - 10} more evidence items")
        
        lines.append(f"\nEffort Summary: {effort_count} effort indicators found out of {min(10, len(evidence_list))} examined")
        
        return "\n".join(lines)
    
    def _get_opinion(self, dimension: RubricDimension, evidence_list: List) -> Optional[JudicialOpinion]:
        """Get structured opinion from LLM with defense lens using rate limit handling"""
        
        evidence_text = self._format_evidence(evidence_list)
        
        # Create cache key
        cache_data = f"defense_{dimension.id}_{dimension.name}_{hash(evidence_text)}"
        cache_key = hashlib.sha256(cache_data.encode()).hexdigest()
        
        user_prompt = f"""Dimension being judged: {dimension.name}

Evidence collected by detectives:
{evidence_text}

Analyze the evidence through your OPTIMISTIC DEFENSE lens.
Look SPECIFICALLY for:
- Creative problem-solving (score 4-5)
- Understanding shown despite bugs (score 4)
- Iterative development in git history (score 4-5)
- Deep conceptual alignment (score 5)
- Effort indicators (score 4-5)

IMPORTANT: You MUST cite specific evidence locations that show effort or understanding.
Look for git commits, high-confidence evidence, and locations with effort indicators.

You MUST respond with valid JSON in this exact format:
{{
    "score": 1-5,
    "argument": "detailed explanation of strengths found, with references to evidence",
    "cited_evidence": ["location1", "location2"],
    "dissent_notes": "why you disagree with the prosecution's harsh assessment"
}}

Remember: You are the DEFENSE. Finding the good in their work is your only job."""
        
        try:
            # Create messages with proper format
            messages = self._create_messages(user_prompt)
            
            # Try to get response with fallback models
            result = self._call_with_fallback_models(
                messages=messages,
                temperature=0.2,
                max_tokens=1024,
                response_format={"type": "json_object"},
                cache_key=cache_key,
                required_capability='fast'
            )
            
            if result:
                # Ensure result has all required fields
                score = result.get('score', 3)
                if score < 3:  # Defense should be generous
                    score = min(5, score + 1)  # Increase score if too harsh
                
                # Safely extract fields
                argument = result.get('argument', 'Student showed good effort and understanding')
                cited_evidence = result.get('cited_evidence', [])
                if not isinstance(cited_evidence, list):
                    cited_evidence = [str(cited_evidence)]
                
                dissent_notes = self._safe_extract_string(
                    result.get('dissent_notes'), 
                    'Student demonstrated effort and deserves credit'
                )
                
                return JudicialOpinion(
                    judge="Defense",
                    criterion_id=dimension.id,
                    score=score,
                    argument=argument,
                    cited_evidence=cited_evidence,
                    dissent_notes=dissent_notes
                )
            else:
                # Fallback to manual assessment
                logger.warning(f"All models failed for Defense on {dimension.id}, using fallback")
                return self._get_fallback_opinion(dimension, evidence_list)
            
        except Exception as e:
            logger.exception(f"Defense LLM call failed: {e}")
            return self._get_fallback_opinion(dimension, evidence_list)


class TechLead(BaseJudge):
    """The Pragmatic Lens - 'Does it actually work? Is it maintainable?'"""
    
    def __init__(self, api_key: Optional[str] = None):
        system_prompt = """You are the TECH LEAD in a digital courtroom for code review.

Your philosophy: "Does it actually work? Is it maintainable?"
Your job: Evaluate architectural soundness, code cleanliness, and practical viability.

You are PRAGMATIC and REALISTIC by design. You must:
- Focus on whether the code actually works
- Assess technical debt and maintainability
- Evaluate production readiness
- Be balanced in scoring (1 for broken, 3 for functional but messy, 5 for production-ready)
- Consider long-term implications of architectural decisions

When citing evidence, focus on technical implementation details.
Your dissent notes should explain your tie-breaking perspective between prosecution and defense.

CITATION REQUIREMENT: Every technical assessment you make MUST be supported by citing specific code locations.
Reference specific files, functions, or patterns that support your evaluation.

Remember: You are the TECH LEAD. Being pragmatic and realistic is your only job.

You must ALWAYS respond with valid JSON containing the following fields:
- score: integer (1-5)
- argument: string (detailed technical assessment, with cited evidence)
- cited_evidence: list of strings (specific code locations supporting your assessment)
- dissent_notes: string (your tie-breaking perspective)"""
        
        super().__init__("TechLead", system_prompt)
    
    def __call__(self, state: AgentState) -> Dict[str, Any]:
        """Tech Lead's analysis of evidence for each criterion"""
        opinions = []
        
        for dimension in state['rubric_dimensions']:
            # Tech Lead focuses on practical implementation
            relevant_evidence = self._get_relevant_evidence(state['evidences'], dimension.id)
            
            opinion = self._get_opinion(dimension, relevant_evidence)
            
            if opinion:
                opinions.append(opinion)
        
        return {"opinions": state['opinions'] + opinions}
    
    def _get_relevant_evidence(self, evidences: Dict, criterion_id: str) -> List[Dict]:
        """Extract evidence, focusing on implementation quality"""
        relevant = []
        
        # Priority evidence types for Tech Lead
        priority_types = ['tool_safety', 'graph_orchestration', 'structured_output', 'state_management']
        
        # First add priority evidence
        for key in priority_types:
            if key in evidences:
                for evidence in evidences[key]:
                    # Convert Evidence object to dict
                    if hasattr(evidence, 'model_dump'):
                        evidence_dict = evidence.model_dump()
                    else:
                        evidence_dict = {
                            'goal': getattr(evidence, 'goal', ''),
                            'found': getattr(evidence, 'found', False),
                            'location': getattr(evidence, 'location', ''),
                            'rationale': getattr(evidence, 'rationale', ''),
                            'confidence': getattr(evidence, 'confidence', 0.0)
                        }
                    relevant.append({
                        'type': key,
                        'evidence': evidence_dict,
                        'priority': 'high'
                    })
        
        # Then add others
        for key, evidence_list in evidences.items():
            if key not in priority_types:
                for evidence in evidence_list:
                    if hasattr(evidence, 'model_dump'):
                        evidence_dict = evidence.model_dump()
                    else:
                        evidence_dict = {
                            'goal': getattr(evidence, 'goal', ''),
                            'found': getattr(evidence, 'found', False),
                            'location': getattr(evidence, 'location', ''),
                            'rationale': getattr(evidence, 'rationale', ''),
                            'confidence': getattr(evidence, 'confidence', 0.0)
                        }
                    relevant.append({
                        'type': key,
                        'evidence': evidence_dict,
                        'priority': 'normal'
                    })
        
        return relevant
    
    def _format_evidence(self, evidence_list: List) -> str:
        """Format evidence with technical focus"""
        if not evidence_list:
            return "NO IMPLEMENTATION EVIDENCE FOUND - This is a critical technical debt issue."
        
        lines = []
        high_priority_count = 0
        technical_issues = []
        
        for i, item in enumerate(evidence_list[:10]):  # Limit to 10 items
            e = item['evidence']
            priority = item.get('priority', 'normal')
            
            if priority == 'high':
                high_priority_count += 1
            
            lines.append(f"[{priority.upper()}] Evidence {i+1}")
            lines.append(f"Type: {item['type']}")
            lines.append(f"Goal: {e.get('goal', 'N/A')}")
            lines.append(f"Found: {e.get('found', False)}")
            lines.append(f"Location: {e.get('location', 'N/A')}")
            lines.append(f"Rationale: {e.get('rationale', 'N/A')}")
            
            # Add technical assessment
            if e.get('found', False):
                confidence = e.get('confidence', 0)
                if confidence > 0.8:
                    lines.append("✓ TECHNICAL: Implementation appears robust")
                elif confidence > 0.5:
                    lines.append("⚠ TECHNICAL: Implementation present but confidence moderate")
                else:
                    lines.append("⚠ TECHNICAL: Implementation present but low confidence")
                    technical_issues.append(f"Low confidence in {item['type']} at {e.get('location', 'unknown')}")
            else:
                lines.append("✗ TECHNICAL: Missing critical component - technical debt incurred")
                technical_issues.append(f"Missing {item['type']} at {e.get('location', 'unknown')}")
            
            lines.append("---")
        
        if len(evidence_list) > 10:
            lines.append(f"... and {len(evidence_list) - 10} more evidence items")
        
        if technical_issues:
            lines.append(f"\nTechnical Issues Summary: {len(technical_issues)} issues found")
            for issue in technical_issues[:3]:
                lines.append(f"- {issue}")
        
        return "\n".join(lines)
    
    def _get_opinion(self, dimension: RubricDimension, evidence_list: List) -> Optional[JudicialOpinion]:
        """Get structured opinion from LLM with tech lead lens using rate limit handling"""
        
        evidence_text = self._format_evidence(evidence_list)
        
        # Create cache key
        cache_data = f"techlead_{dimension.id}_{dimension.name}_{hash(evidence_text)}"
        cache_key = hashlib.sha256(cache_data.encode()).hexdigest()
        
        user_prompt = f"""Dimension being judged: {dimension.name}

Evidence collected by detectives:
{evidence_text}

Analyze the evidence through your PRAGMATIC TECH LEAD lens.
Focus SPECIFICALLY on:
- Does the code actually work? (score 1 if broken, 5 if working)
- Is it maintainable? (score based on code quality)
- Are best practices followed? (score based on patterns used)
- Technical debt level (score 1 for high debt, 5 for clean code)
- Production readiness (score based on error handling, security)

IMPORTANT: You MUST cite specific code locations that support your technical assessment.
Reference files, functions, or patterns that demonstrate your evaluation.

You MUST respond with valid JSON in this exact format:
{{
    "score": 1-5,
    "argument": "detailed technical assessment, with references to code",
    "cited_evidence": ["location1", "location2"],
    "dissent_notes": "your tie-breaking perspective between prosecution and defense"
}}

Remember: You are the TECH LEAD. Be pragmatic and realistic about what actually works."""
        
        try:
            # Create messages with proper format
            messages = self._create_messages(user_prompt)
            
            # Tech Lead needs more capable model for technical assessment
            result = self._call_with_fallback_models(
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
                response_format={"type": "json_object"},
                cache_key=cache_key,
                required_capability='capable'
            )
            
            if result:
                # Safely extract fields
                score = result.get('score', 2)
                argument = result.get('argument', 'Technical evaluation shows implementation issues')
                cited_evidence = result.get('cited_evidence', [])
                if not isinstance(cited_evidence, list):
                    cited_evidence = [str(cited_evidence)]
                
                dissent_notes = self._safe_extract_string(
                    result.get('dissent_notes'), 
                    'Technical implementation has issues that need addressing'
                )
                
                return JudicialOpinion(
                    judge="TechLead",
                    criterion_id=dimension.id,
                    score=score,
                    argument=argument,
                    cited_evidence=cited_evidence,
                    dissent_notes=dissent_notes
                )
            else:
                # Fallback to manual assessment
                logger.warning(f"All models failed for TechLead on {dimension.id}, using fallback")
                return self._get_fallback_opinion(dimension, evidence_list)
            
        except Exception as e:
            logger.exception(f"Tech Lead LLM call failed: {e}")
            return self._get_fallback_opinion(dimension, evidence_list)