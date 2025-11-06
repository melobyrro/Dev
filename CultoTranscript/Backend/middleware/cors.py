"""
CORS Middleware Configuration

Configures Cross-Origin Resource Sharing (CORS) for the FastAPI application.
Allows the React frontend (running on localhost:5173) to communicate with the backend.
"""
import logging
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger(__name__)


def setup_cors(
    app: FastAPI,
    allowed_origins: List[str] = None,
    allow_credentials: bool = True,
    allow_methods: List[str] = None,
    allow_headers: List[str] = None,
) -> None:
    """
    Configure CORS middleware for FastAPI application.

    Args:
        app: FastAPI application instance
        allowed_origins: List of allowed origins (default: localhost:5173 for React dev)
        allow_credentials: Allow cookies and authentication headers
        allow_methods: Allowed HTTP methods (default: GET, POST, PUT, DELETE, OPTIONS)
        allow_headers: Allowed HTTP headers (default: all)

    Example:
        ```python
        from fastapi import FastAPI
        from Backend.middleware import setup_cors

        app = FastAPI()
        setup_cors(app)
        ```
    """
    if allowed_origins is None:
        allowed_origins = [
            "http://localhost:5173",  # React dev server (Vite)
            "http://localhost:3000",  # Alternative React dev port
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ]

    if allow_methods is None:
        allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"]

    if allow_headers is None:
        allow_headers = ["*"]

    logger.info(f"Setting up CORS with origins: {allowed_origins}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=allow_credentials,
        allow_methods=allow_methods,
        allow_headers=allow_headers,
        expose_headers=["X-CSRF-Token"],  # Expose CSRF token header
        max_age=3600,  # Cache preflight requests for 1 hour
    )

    logger.info("CORS middleware configured successfully")


def setup_production_cors(app: FastAPI, production_domain: str) -> None:
    """
    Configure CORS for production environment.

    Args:
        app: FastAPI application instance
        production_domain: Production domain (e.g., "https://church.byrroserver.com")

    Example:
        ```python
        from fastapi import FastAPI
        from Backend.middleware import setup_production_cors

        app = FastAPI()
        setup_production_cors(app, "https://church.byrroserver.com")
        ```
    """
    allowed_origins = [production_domain]

    logger.info(f"Setting up production CORS for domain: {production_domain}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
        allow_headers=["*"],
        expose_headers=["X-CSRF-Token"],
        max_age=3600,
    )

    logger.info("Production CORS middleware configured successfully")
