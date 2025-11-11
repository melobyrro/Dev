"""
LLM Status Router
API endpoints for monitoring LLM backend usage and health
"""
import logging
import os
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.ai.llm_client import get_llm_client
from app.common.database import get_db
import requests

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/status")
async def get_llm_status(db: Session = Depends(get_db)):
    """
    Get current LLM backend status and statistics

    Returns:
        Dict with backend configuration, active backend, and usage statistics
    """
    try:
        llm = get_llm_client()
        stats = llm.get_stats()

        # Calculate estimated Gemini cost (Gemini 1.5 Flash pricing: $0.15/1M tokens)
        gemini_cost_usd = stats["gemini_tokens"] * 0.15 / 1000000

        # Get cache statistics from Phase 1
        cache_stats = await get_cache_statistics(db)

        return {
            "primary_backend": os.getenv("PRIMARY_LLM", "gemini"),
            "fallback_backend": os.getenv("FALLBACK_LLM", "ollama"),
            "active_backend": llm.get_active_backend(),
            "ollama_healthy": check_ollama_health(),
            "statistics": {
                "gemini": {
                    "total_calls": stats["gemini_calls"],
                    "total_tokens": stats["gemini_tokens"],
                    "error_count": stats["gemini_errors"],
                    "estimated_cost_usd": round(gemini_cost_usd, 4)
                },
                "ollama": {
                    "total_calls": stats["ollama_calls"],
                    "total_tokens": stats["ollama_tokens"],
                    "error_count": stats["ollama_errors"],
                    "cost_usd": 0.0  # Always free
                },
                "fallback_count": stats["fallback_count"]
            },
            "cache_stats": cache_stats
        }
    except Exception as e:
        logger.error(f"Error fetching LLM status: {e}", exc_info=True)
        return {
            "error": str(e),
            "primary_backend": os.getenv("PRIMARY_LLM", "gemini"),
            "fallback_backend": os.getenv("FALLBACK_LLM", "ollama")
        }


@router.get("/health")
async def check_backends_health():
    """
    Health check for both LLM backends

    Returns:
        Dict with health status for Gemini and Ollama
    """
    results = {
        "gemini": {"status": "unknown", "error": None},
        "ollama": {"status": "unknown", "error": None},
        "overall_status": "unknown"
    }

    # Check Gemini
    gemini_healthy = False
    gemini_error = None
    try:
        from google.generativeai import configure, GenerativeModel

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            gemini_error = "GEMINI_API_KEY not configured"
        else:
            configure(api_key=api_key)
            model = GenerativeModel("gemini-1.5-flash")
            test_response = model.generate_content(
                "Say 'OK'",
                generation_config={"max_output_tokens": 10}
            )

            # Handle both simple and multi-part responses
            try:
                response_text = test_response.text
            except ValueError:
                # Multi-part response - extract text from all parts
                if test_response.candidates:
                    parts = test_response.candidates[0].content.parts
                    response_text = "".join(part.text for part in parts if hasattr(part, 'text'))
                else:
                    response_text = ""

            gemini_healthy = "OK" in response_text.upper()

            if not gemini_healthy:
                gemini_error = "Unexpected response from Gemini"
    except Exception as e:
        gemini_error = str(e)
        logger.warning(f"Gemini health check failed: {e}")

    results["gemini"]["status"] = "healthy" if gemini_healthy else "unhealthy"
    results["gemini"]["error"] = gemini_error

    # Check Ollama
    ollama_healthy = check_ollama_health()
    results["ollama"]["status"] = "healthy" if ollama_healthy else "unhealthy"

    if not ollama_healthy:
        results["ollama"]["error"] = "Cannot connect to Ollama service"

    # Overall status
    if gemini_healthy or ollama_healthy:
        results["overall_status"] = "healthy"
    elif gemini_healthy and ollama_healthy:
        results["overall_status"] = "optimal"
    else:
        results["overall_status"] = "degraded"

    return results


def check_ollama_health() -> bool:
    """
    Check if Ollama service is reachable

    Returns:
        True if Ollama is healthy, False otherwise
    """
    ollama_url = os.getenv("OLLAMA_URL", "http://ollama:11434")

    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception as e:
        logger.debug(f"Ollama health check failed: {e}")
        return False


async def get_cache_statistics(db: Session) -> dict:
    """
    Get cache statistics from Phase 1 caching system

    Args:
        db: Database session

    Returns:
        Dict with cache hit/miss rates and cost savings
    """
    try:
        # Query cache performance from gemini_cache_responses table
        query = text("""
            SELECT
                COUNT(*) as total_cached_responses,
                SUM(hit_count) as total_cache_hits,
                AVG(EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600) as avg_age_hours
            FROM gemini_cache_responses
            WHERE created_at > NOW() - INTERVAL '30 days'
        """)

        result = db.execute(query).first()

        if result and result[0] > 0:
            total_cached = result[0]
            total_hits = result[1] or 0
            avg_age_hours = result[2] or 0

            # Estimate cost savings (assuming 500 tokens per cached response @ $0.15/1M)
            estimated_savings_usd = (total_hits * 500 * 0.15) / 1000000

            return {
                "enabled": True,
                "total_cached_responses": total_cached,
                "total_cache_hits": total_hits,
                "avg_cache_age_hours": round(avg_age_hours, 1),
                "estimated_savings_usd": round(estimated_savings_usd, 2)
            }
        else:
            return {
                "enabled": True,
                "total_cached_responses": 0,
                "total_cache_hits": 0,
                "avg_cache_age_hours": 0,
                "estimated_savings_usd": 0.0
            }
    except Exception as e:
        logger.error(f"Error fetching cache statistics: {e}")
        return {
            "enabled": False,
            "error": str(e)
        }
