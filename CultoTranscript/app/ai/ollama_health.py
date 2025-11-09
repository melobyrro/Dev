"""Ollama health check and model management utilities.

This module provides functions to:
1. Check if Ollama service is running and healthy
2. Verify that the required model (phi3:mini) is available
3. Download models on-demand if they're missing

Used during application startup and for monitoring Ollama availability.
"""

import requests
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def check_ollama_health(ollama_url: str = "http://ollama:11434") -> bool:
    """Check if Ollama is running and the required model is available.

    Args:
        ollama_url: Ollama API endpoint URL

    Returns:
        True if Ollama is healthy and phi3:mini model is available, False otherwise

    Example:
        >>> if check_ollama_health():
        ...     print("Ollama is ready!")
        ... else:
        ...     print("Ollama unavailable")
    """
    try:
        # Check if Ollama is running
        logger.debug(f"Checking Ollama health at {ollama_url}/api/tags")
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)

        if response.status_code != 200:
            logger.warning(f"⚠️ Ollama returned status {response.status_code}")
            return False

        # Check if phi3:mini is available
        models = response.json().get("models", [])
        model_names = [m.get("name", "") for m in models]

        logger.debug(f"Available models: {model_names}")

        # Check for phi3:mini or just phi3
        if any("phi3" in name.lower() for name in model_names):
            logger.info(f"✅ Ollama is healthy with phi3 model available")
            return True
        else:
            logger.warning(f"⚠️ Ollama running but phi3:mini not found. Available: {model_names}")
            return False

    except requests.exceptions.Timeout:
        logger.error(f"❌ Ollama health check timed out")
        return False
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Cannot connect to Ollama at {ollama_url}")
        return False
    except Exception as e:
        logger.error(f"❌ Ollama health check failed: {e}")
        return False


def get_available_models(ollama_url: str = "http://ollama:11434") -> List[Dict]:
    """Get list of available Ollama models.

    Args:
        ollama_url: Ollama API endpoint URL

    Returns:
        List of model dictionaries containing name, size, and modified date

    Example:
        >>> models = get_available_models()
        >>> for model in models:
        ...     print(f"{model['name']}: {model['size']} bytes")
    """
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        response.raise_for_status()

        models = response.json().get("models", [])
        logger.info(f"📋 Found {len(models)} available models")
        return models

    except Exception as e:
        logger.error(f"❌ Failed to get available models: {e}")
        return []


def download_model(
    model_name: str = "phi3:mini",
    ollama_url: str = "http://ollama:11434",
    timeout: int = 600
) -> bool:
    """Download an Ollama model if not already present.

    This is a blocking operation that can take several minutes depending
    on the model size and network speed.

    Args:
        model_name: Name of the model to download (e.g., "phi3:mini")
        ollama_url: Ollama API endpoint URL
        timeout: Maximum time to wait for download in seconds (default: 10 min)

    Returns:
        True if download succeeded, False otherwise

    Example:
        >>> if not check_ollama_health():
        ...     download_model("phi3:mini")
    """
    try:
        logger.info(f"📥 Downloading Ollama model: {model_name}")
        logger.info(f"⏳ This may take several minutes...")

        response = requests.post(
            f"{ollama_url}/api/pull",
            json={"name": model_name},
            timeout=timeout,
            stream=True
        )

        if response.status_code == 200:
            # Stream the response to show progress
            for line in response.iter_lines():
                if line:
                    logger.debug(f"Download progress: {line.decode('utf-8')}")

            logger.info(f"✅ Model {model_name} downloaded successfully")
            return True
        else:
            logger.error(f"❌ Failed to download {model_name}: HTTP {response.status_code}")
            return False

    except requests.exceptions.Timeout:
        logger.error(f"❌ Download timeout for {model_name} after {timeout}s")
        return False
    except Exception as e:
        logger.error(f"❌ Failed to download {model_name}: {e}")
        return False


def ensure_model_available(
    model_name: str = "phi3:mini",
    ollama_url: str = "http://ollama:11434"
) -> bool:
    """Ensure that the specified model is available, downloading if necessary.

    This is a convenience function that checks for the model and downloads
    it if it's not present.

    Args:
        model_name: Name of the model to ensure is available
        ollama_url: Ollama API endpoint URL

    Returns:
        True if model is available or was successfully downloaded, False otherwise

    Example:
        >>> ensure_model_available("phi3:mini")
        True
    """
    # First check if model is already available
    models = get_available_models(ollama_url)
    model_names = [m.get("name", "") for m in models]

    # Check if our model is already downloaded
    if any(model_name in name for name in model_names):
        logger.info(f"✅ Model {model_name} already available")
        return True

    # Model not found, try to download it
    logger.warning(f"⚠️ Model {model_name} not found, attempting download...")
    return download_model(model_name, ollama_url)


def get_ollama_info(ollama_url: str = "http://ollama:11434") -> Optional[Dict]:
    """Get Ollama service information and status.

    Args:
        ollama_url: Ollama API endpoint URL

    Returns:
        Dictionary with service info, or None if unavailable

    Example:
        >>> info = get_ollama_info()
        >>> if info:
        ...     print(f"Available models: {len(info['models'])}")
    """
    try:
        models = get_available_models(ollama_url)

        return {
            "url": ollama_url,
            "healthy": check_ollama_health(ollama_url),
            "models": models,
            "model_count": len(models)
        }

    except Exception as e:
        logger.error(f"❌ Failed to get Ollama info: {e}")
        return None


if __name__ == "__main__":
    # Simple CLI for testing
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    ollama_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:11434"

    print(f"\n🔍 Checking Ollama at {ollama_url}\n")

    # Get service info
    info = get_ollama_info(ollama_url)
    if info:
        print(f"✅ Ollama is {'healthy' if info['healthy'] else 'unhealthy'}")
        print(f"📋 Available models: {info['model_count']}")
        for model in info['models']:
            print(f"   - {model.get('name', 'unknown')}")
    else:
        print("❌ Ollama is not available")

    # Try to ensure phi3:mini is available
    print(f"\n🔄 Ensuring phi3:mini is available...")
    if ensure_model_available("phi3:mini", ollama_url):
        print("✅ phi3:mini is ready!")
    else:
        print("❌ Failed to ensure phi3:mini availability")
