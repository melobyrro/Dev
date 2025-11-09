"""
Google Gemini API Client
Wrapper for Google Generative AI with rate limiting, error handling, and retry logic
"""
import os
import time
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta

try:
    import google.generativeai as genai
except ImportError:
    genai = None

logger = logging.getLogger(__name__)


class GeminiClient:
    """
    Google Gemini API client with automatic retries and rate limiting

    Features:
    - Automatic API key configuration from environment
    - Exponential backoff for rate limits
    - Streaming and non-streaming responses
    - Token counting and cost estimation
    - Model configuration (temperature, top_p, etc.)
    """

    # Rate limiting constants
    MAX_REQUESTS_PER_MINUTE = 60
    MAX_TOKENS_PER_MINUTE = 1_000_000
    RETRY_MAX_ATTEMPTS = 3
    RETRY_DELAY_BASE = 2  # seconds

    # Cost per 1M tokens (Gemini 1.5 Flash pricing)
    COST_INPUT_PER_1M = 0.075  # USD
    COST_OUTPUT_PER_1M = 0.30  # USD

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        temperature: float = 0.7,
        top_p: float = 0.95,
        top_k: int = 40,
        max_output_tokens: int = 2048
    ):
        """
        Initialize Gemini client

        Args:
            api_key: Google Gemini API key (defaults to GEMINI_API_KEY env var)
            model_name: Model to use (defaults to GEMINI_MODEL env var or gemini-2.5-flash)
            temperature: Sampling temperature (0.0 to 1.0)
            top_p: Nucleus sampling parameter
            top_k: Top-k sampling parameter
            max_output_tokens: Maximum tokens in response
        """
        if genai is None:
            raise ImportError(
                "google-generativeai package not installed. "
                "Install with: pip install google-generativeai"
            )

        # Get API key
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Gemini API key not found. Set GEMINI_API_KEY environment variable "
                "or pass api_key parameter"
            )

        # Configure Gemini
        genai.configure(api_key=self.api_key)

        # Model configuration - read from env var with fallback to gemini-2.5-flash
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        self.generation_config = {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_output_tokens": max_output_tokens,
        }

        # Safety settings - less restrictive for sermon content
        from google.generativeai.types import HarmCategory, HarmBlockThreshold

        safety_settings = {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
        }

        # Initialize model with safety settings
        self.model = genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
            safety_settings=safety_settings
        )

        # Rate limiting tracking
        self._request_timestamps: List[datetime] = []
        self._token_counts: List[tuple[datetime, int]] = []

        # Usage tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0

        logger.info(f"Gemini client initialized with model: {self.model_name}")

    def _check_rate_limits(self):
        """Check if we're within rate limits, sleep if necessary"""
        now = datetime.now()
        one_minute_ago = now - timedelta(minutes=1)

        # Clean old timestamps
        self._request_timestamps = [
            ts for ts in self._request_timestamps if ts > one_minute_ago
        ]
        self._token_counts = [
            (ts, count) for ts, count in self._token_counts if ts > one_minute_ago
        ]

        # Check request limit
        if len(self._request_timestamps) >= self.MAX_REQUESTS_PER_MINUTE:
            sleep_time = 60 - (now - self._request_timestamps[0]).total_seconds()
            if sleep_time > 0:
                logger.warning(f"Rate limit reached. Sleeping for {sleep_time:.1f}s")
                time.sleep(sleep_time)
                self._request_timestamps = []

        # Check token limit
        total_tokens = sum(count for _, count in self._token_counts)
        if total_tokens >= self.MAX_TOKENS_PER_MINUTE:
            sleep_time = 60 - (now - self._token_counts[0][0]).total_seconds()
            if sleep_time > 0:
                logger.warning(f"Token limit reached. Sleeping for {sleep_time:.1f}s")
                time.sleep(sleep_time)
                self._token_counts = []

    def _track_request(self, input_tokens: int, output_tokens: int):
        """Track request for rate limiting and cost estimation"""
        now = datetime.now()
        self._request_timestamps.append(now)

        total_tokens = input_tokens + output_tokens
        self._token_counts.append((now, total_tokens))

        # Update totals
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        # Calculate cost
        input_cost = (input_tokens / 1_000_000) * self.COST_INPUT_PER_1M
        output_cost = (output_tokens / 1_000_000) * self.COST_OUTPUT_PER_1M
        self.total_cost += input_cost + output_cost

    def generate_content(
        self,
        prompt: str,
        stream: bool = False,
        retry_on_error: bool = True
    ) -> str:
        """
        Generate content using Gemini API

        Args:
            prompt: Input prompt
            stream: Whether to stream the response (not implemented for simplicity)
            retry_on_error: Whether to retry on errors

        Returns:
            Generated text response

        Raises:
            Exception: If all retry attempts fail
        """
        for attempt in range(self.RETRY_MAX_ATTEMPTS if retry_on_error else 1):
            try:
                # Check rate limits
                self._check_rate_limits()

                # Generate content
                response = self.model.generate_content(prompt)

                # Check for safety blocking first
                if response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        finish_reason = candidate.finish_reason
                        logger.info(f"Gemini finish_reason: {finish_reason}")

                        # Check for safety blocking
                        if finish_reason and 'SAFETY' in str(finish_reason):
                            logger.warning(f"Content blocked by safety filters: {finish_reason}")
                            if hasattr(candidate, 'safety_ratings'):
                                logger.warning(f"Safety ratings: {candidate.safety_ratings}")
                            # Raise error for safety blocking
                            raise ValueError(f"Content blocked by safety filters: {finish_reason}")

                # Extract text from response - handle both simple and multi-part responses
                # Gemini 2.5+ returns multi-part responses, need to access parts correctly
                try:
                    # Try simple text accessor first
                    text = response.text
                except (ValueError, AttributeError) as e:
                    # Multi-part response - extract text from all parts
                    if not response.candidates or not response.candidates[0].content.parts:
                        logger.warning(f"Empty response structure: candidates={bool(response.candidates)}")
                        raise ValueError("Empty response from Gemini API")

                    # Concatenate all text parts
                    parts = response.candidates[0].content.parts
                    text = "".join(part.text for part in parts if hasattr(part, 'text'))

                    if not text or not text.strip():
                        logger.warning(f"Empty text after extraction. Parts count: {len(parts)}")
                        # Log part types to debug
                        part_types = [type(part).__name__ for part in parts]
                        logger.warning(f"Part types: {part_types}")
                        raise ValueError("Empty text extracted from multi-part Gemini response")

                # Track usage (estimate tokens since API doesn't always return counts)
                input_tokens = self._estimate_tokens(prompt)
                output_tokens = self._estimate_tokens(text)
                self._track_request(input_tokens, output_tokens)

                logger.debug(
                    f"Generated {output_tokens} tokens from {input_tokens} input tokens"
                )

                return text

            except Exception as e:
                logger.error(f"Gemini API error (attempt {attempt + 1}/{self.RETRY_MAX_ATTEMPTS}): {e}")

                if attempt < self.RETRY_MAX_ATTEMPTS - 1:
                    # Exponential backoff
                    delay = self.RETRY_DELAY_BASE ** attempt
                    logger.info(f"Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise

    def generate_embeddings(self, text: str) -> List[float]:
        """
        Generate text embeddings using Gemini

        Args:
            text: Text to embed

        Returns:
            768-dimensional embedding vector
        """
        try:
            self._check_rate_limits()

            # Use embedding model
            result = genai.embed_content(
                model="models/embedding-001",
                content=text,
                task_type="retrieval_document"
            )

            # Track as minimal token usage
            input_tokens = self._estimate_tokens(text)
            self._track_request(input_tokens, 0)

            return result['embedding']

        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            raise

    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text using Gemini's tokenizer

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        try:
            result = self.model.count_tokens(text)
            return result.total_tokens
        except Exception:
            # Fallback to estimation if API call fails
            return self._estimate_tokens(text)

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation)

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # Rough estimate: 1 token ≈ 4 characters (varies by language)
        # Portuguese tends to be slightly more efficient than English
        return max(1, len(text) // 4)

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics

        Returns:
            Dictionary with usage metrics
        """
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": round(self.total_cost, 4),
            "model": self.model_name
        }

    def reset_usage_stats(self):
        """Reset usage tracking counters"""
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost = 0.0
        logger.info("Usage stats reset")


# Singleton instance (lazy-loaded)
_gemini_instance: Optional[GeminiClient] = None


def get_gemini_client() -> GeminiClient:
    """
    Get singleton Gemini client instance

    Returns:
        Configured GeminiClient instance
    """
    global _gemini_instance

    if _gemini_instance is None:
        # Read configuration from environment
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        temperature = float(os.getenv("GEMINI_TEMPERATURE", "0.7"))

        _gemini_instance = GeminiClient(
            model_name=model_name,
            temperature=temperature
        )

        logger.info("Gemini singleton instance created")

    return _gemini_instance
