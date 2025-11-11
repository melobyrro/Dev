"""Unified LLM client with automatic Gemini -> Ollama fallback.

This module provides a single interface for LLM operations that:
1. Tries Gemini first (if configured as PRIMARY_LLM)
2. Automatically falls back to local Ollama on quota errors (429 status)
3. Provides consistent interface for both backends
4. Tracks usage statistics for monitoring

Designed for Phase 2 of the local LLM fallback system.
"""

from enum import Enum
from typing import Optional, Dict, Any, List
import os
import requests
import logging
from google.generativeai import GenerativeModel, configure
from google.api_core.exceptions import ResourceExhausted, GoogleAPIError

logger = logging.getLogger(__name__)


class LLMBackend(Enum):
    """Available LLM backends."""
    GEMINI = "gemini"
    OLLAMA = "ollama"


class LLMClient:
    """Unified LLM client with automatic fallback from Gemini to Ollama.

    This client provides a consistent interface for both Gemini and Ollama,
    automatically falling back to Ollama when Gemini quota is exhausted.

    Usage:
        >>> client = get_llm_client()
        >>> response = client.generate("Summarize this text: ...")
        >>> print(response["text"])
        >>> print(f"Backend used: {response['backend']}")
    """

    def __init__(self):
        """Initialize the LLM client with both Gemini and Ollama backends."""
        self.primary_backend = os.getenv("PRIMARY_LLM", "gemini")
        self.fallback_backend = os.getenv("FALLBACK_LLM", "ollama")
        self.ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "phi3:mini")

        # Initialize Gemini if API key is available
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        if gemini_api_key:
            try:
                configure(api_key=gemini_api_key)
                gemini_model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
                self.gemini_model = GenerativeModel(gemini_model_name)
                logger.info(f"✅ Gemini client initialized with model: {gemini_model_name}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to initialize Gemini: {e}")
                self.gemini_model = None
        else:
            logger.warning("⚠️ GEMINI_API_KEY not set, Gemini will not be available")
            self.gemini_model = None

        # Usage statistics
        self.stats = {
            "gemini_calls": 0,
            "ollama_calls": 0,
            "gemini_tokens": 0,
            "ollama_tokens": 0,
            "fallback_count": 0,
            "gemini_errors": 0,
            "ollama_errors": 0
        }

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        max_tokens: int = 2000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """Generate text with automatic fallback.

        Args:
            prompt: The input prompt for text generation
            system_instruction: Optional system instruction (prepended to prompt)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            Dict containing:
                - text: Generated text
                - backend: Which backend was used ("gemini" or "ollama")
                - tokens_used: Number of tokens consumed

        Raises:
            Exception: If both Gemini and Ollama fail
        """

        # Try Gemini first if configured as primary
        if self.primary_backend == "gemini" and self.gemini_model is not None:
            try:
                response = self._call_gemini(prompt, system_instruction, max_tokens, temperature)
                self.stats["gemini_calls"] += 1
                self.stats["gemini_tokens"] += response.get("tokens_used", 0)
                logger.info(f"✅ Gemini response generated ({response.get('tokens_used', 0)} tokens)")
                return {
                    "text": response["text"],
                    "backend": "gemini",
                    "tokens_used": response.get("tokens_used", 0)
                }
            except ResourceExhausted as e:
                logger.warning(f"⚠️ Gemini quota exceeded: {e}. Falling back to Ollama.")
                self.stats["fallback_count"] += 1
                self.stats["gemini_errors"] += 1
                return self._call_ollama(prompt, system_instruction, max_tokens, temperature)
            except GoogleAPIError as e:
                logger.warning(f"⚠️ Gemini API error: {e}. Falling back to Ollama.")
                self.stats["fallback_count"] += 1
                self.stats["gemini_errors"] += 1
                return self._call_ollama(prompt, system_instruction, max_tokens, temperature)
            except Exception as e:
                logger.error(f"❌ Unexpected Gemini error: {e}. Falling back to Ollama.")
                self.stats["fallback_count"] += 1
                self.stats["gemini_errors"] += 1
                return self._call_ollama(prompt, system_instruction, max_tokens, temperature)
        else:
            # Use Ollama directly if it's the primary backend or Gemini is unavailable
            return self._call_ollama(prompt, system_instruction, max_tokens, temperature)

    def _call_gemini(
        self,
        prompt: str,
        system_instruction: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Call Gemini API.

        Args:
            prompt: The input prompt
            system_instruction: Optional system instruction
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Dict containing text and tokens_used

        Raises:
            ResourceExhausted: If quota is exceeded
            GoogleAPIError: If API call fails
        """
        full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt

        gemini_model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        logger.info(f"🔵 Calling Gemini API - model: {gemini_model}, prompt_length: {len(full_prompt)}, max_tokens: {max_tokens}, temp: {temperature}")
        logger.debug(f"Prompt preview: {full_prompt[:200]}...")

        content = [
            {
                "role": "user",
                "parts": [
                    {"text": full_prompt}
                ]
            }
        ]

        generation_config = {
            "temperature": temperature
        }

        response = self.gemini_model.generate_content(
            content,
            generation_config=generation_config
        )

        logger.info(f"✅ Gemini API response received")
        logger.debug(f"Response structure - candidates: {len(response.candidates) if hasattr(response, 'candidates') and response.candidates else 0}")

        tokens_used = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            tokens_used = response.usage_metadata.total_token_count
            logger.debug(f"Tokens used: {tokens_used}")

        # Handle both simple and multi-part responses
        try:
            text = response.text
            logger.info(f"✅ Simple response.text accessed successfully - length: {len(text)}")
        except ValueError as e:
            logger.warning(f"⚠️ ValueError accessing response.text: {str(e)}")
            # Multi-part response - extract ALL text from ALL parts
            if response.candidates:
                parts = response.candidates[0].content.parts
                logger.info(f"📦 Extracting from {len(parts)} parts in multi-part response")
                text = "".join(part.text for part in parts if hasattr(part, 'text'))
                logger.info(f"✅ Extracted {len(text)} chars from parts")
            else:
                logger.error("❌ No candidates in response!")
                text = ""

        logger.info(f"🎯 Final extracted text length: {len(text)} chars")
        if len(text) < 200:
            logger.warning(f"⚠️ Short response: '{text}'")

        if not text.strip():
            raise ValueError("Gemini returned empty response")

        return {
            "text": text,
            "tokens_used": tokens_used
        }

    def _call_ollama(
        self,
        prompt: str,
        system_instruction: Optional[str],
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Call Ollama API.

        Args:
            prompt: The input prompt
            system_instruction: Optional system instruction
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature

        Returns:
            Dict containing text, backend, and tokens_used

        Raises:
            requests.exceptions.RequestException: If Ollama is unavailable
        """
        full_prompt = f"{system_instruction}\n\n{prompt}" if system_instruction else prompt

        payload = {
            "model": self.ollama_model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature
            }
        }

        try:
            logger.info(f"🤖 Calling Ollama ({self.ollama_model}) at {self.ollama_url}...")
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json=payload,
                timeout=120  # 2 minutes timeout for local inference
            )
            response.raise_for_status()
            result = response.json()

            tokens_used = result.get("eval_count", 0)
            self.stats["ollama_calls"] += 1
            self.stats["ollama_tokens"] += tokens_used

            logger.info(f"✅ Ollama response generated ({tokens_used} tokens)")

            return {
                "text": result["response"],
                "backend": "ollama",
                "tokens_used": tokens_used
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Ollama API error: {e}")
            self.stats["ollama_errors"] += 1
            raise

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embeddings using Gemini embedding-001 model.

        Note: Ollama does not currently support embeddings in this implementation.
        Always uses Gemini for embeddings.

        Args:
            text: Text to embed

        Returns:
            List of embedding values (768-dimensional vector)

        Raises:
            Exception: If Gemini is not available or API call fails
        """
        if self.gemini_model is None:
            raise ValueError("Gemini not available for embeddings. GEMINI_API_KEY not set.")

        try:
            from google.generativeai import embed_content

            response = embed_content(
                model="models/embedding-001",
                content=text,
                task_type="retrieval_document"
            )

            logger.info("✅ Embedding generated via Gemini")
            return response['embedding']
        except Exception as e:
            logger.error(f"❌ Failed to generate embedding: {e}")
            raise

    def get_stats(self) -> Dict[str, int]:
        """Get usage statistics.

        Returns:
            Dict containing call counts, token usage, and error counts
        """
        return self.stats.copy()

    def get_active_backend(self) -> str:
        """Get currently configured primary backend.

        Returns:
            Backend name ("gemini" or "ollama")
        """
        return self.primary_backend

    def reset_stats(self):
        """Reset usage statistics to zero."""
        self.stats = {
            "gemini_calls": 0,
            "ollama_calls": 0,
            "gemini_tokens": 0,
            "ollama_tokens": 0,
            "fallback_count": 0,
            "gemini_errors": 0,
            "ollama_errors": 0
        }
        logger.info("📊 Statistics reset")


# Singleton instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get singleton LLM client instance.

    This ensures only one client is created per process, maintaining
    consistent statistics tracking.

    Returns:
        LLMClient: The singleton instance
    """
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
        logger.info("🚀 LLM client initialized")
    return _llm_client


def reset_llm_client() -> None:
    """Reset the singleton LLM client instance.

    This forces the client to be re-initialized on the next call to get_llm_client(),
    picking up any changes to environment variables (like GEMINI_API_KEY).

    Use this after updating API configuration to apply changes immediately without restarting.
    """
    global _llm_client
    _llm_client = None
    logger.info("🔄 LLM client reset - will reinitialize on next use")
