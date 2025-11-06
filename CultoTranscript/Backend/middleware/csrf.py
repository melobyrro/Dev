"""
CSRF Protection Middleware

Implements Cross-Site Request Forgery (CSRF) protection for the FastAPI application.
Generates and validates CSRF tokens for state-changing requests (POST, PUT, DELETE, PATCH).
"""
import logging
import secrets
from typing import Callable, Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.datastructures import MutableHeaders

logger = logging.getLogger(__name__)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware.

    Generates CSRF tokens for GET requests and validates them for
    state-changing requests (POST, PUT, DELETE, PATCH).

    **How it works:**
    1. GET requests: Generate and send CSRF token in X-CSRF-Token header
    2. POST/PUT/DELETE/PATCH: Validate X-CSRF-Token header matches session token
    3. Store tokens in session (requires SessionMiddleware)

    **Usage:**
    ```python
    from fastapi import FastAPI
    from starlette.middleware.sessions import SessionMiddleware
    from Backend.middleware import CSRFMiddleware

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="your-secret-key")
    app.add_middleware(CSRFMiddleware)
    ```

    **Client-side usage:**
    ```javascript
    // 1. Get CSRF token from response header
    const response = await fetch('/api/endpoint');
    const csrfToken = response.headers.get('X-CSRF-Token');

    // 2. Include token in subsequent requests
    await fetch('/api/videos', {
        method: 'POST',
        headers: {
            'X-CSRF-Token': csrfToken,
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    });
    ```
    """

    def __init__(
        self,
        app,
        exempt_paths: Optional[list[str]] = None,
        token_length: int = 32,
    ):
        """
        Initialize CSRF middleware.

        Args:
            app: ASGI application
            exempt_paths: List of path prefixes exempt from CSRF validation
            token_length: Length of generated CSRF tokens in bytes
        """
        super().__init__(app)
        self.exempt_paths = exempt_paths or [
            "/api/v2/events/stream",  # SSE endpoint (GET only)
            "/health",  # Health check endpoints
            "/docs",  # API documentation
            "/openapi.json",  # OpenAPI schema
            "/static",  # Static files
        ]
        self.token_length = token_length
        logger.info(f"CSRF middleware initialized. Exempt paths: {self.exempt_paths}")

    def _is_exempt(self, path: str) -> bool:
        """Check if path is exempt from CSRF validation"""
        return any(path.startswith(exempt) for exempt in self.exempt_paths)

    def _generate_token(self) -> str:
        """Generate a new CSRF token"""
        return secrets.token_urlsafe(self.token_length)

    def _get_token_from_session(self, request: Request) -> Optional[str]:
        """Get CSRF token from session"""
        return request.session.get("csrf_token")

    def _set_token_in_session(self, request: Request, token: str) -> None:
        """Store CSRF token in session"""
        request.session["csrf_token"] = token

    def _get_token_from_header(self, request: Request) -> Optional[str]:
        """Get CSRF token from request header"""
        return request.headers.get("X-CSRF-Token")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and validate CSRF token.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware/handler in chain

        Returns:
            HTTP response
        """
        # Check if path is exempt
        if self._is_exempt(request.url.path):
            return await call_next(request)

        # GET requests: Generate/return CSRF token
        if request.method == "GET":
            # Get or generate CSRF token
            token = self._get_token_from_session(request)
            if not token:
                token = self._generate_token()
                self._set_token_in_session(request, token)
                logger.debug(f"Generated new CSRF token for session")

            # Process request
            response = await call_next(request)

            # Add CSRF token to response headers
            response.headers["X-CSRF-Token"] = token

            return response

        # State-changing requests: Validate CSRF token
        if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
            session_token = self._get_token_from_session(request)
            request_token = self._get_token_from_header(request)

            # Validate token presence
            if not session_token:
                logger.warning(f"CSRF validation failed: No session token for {request.method} {request.url.path}")
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "detail": "CSRF token missing from session. Please refresh the page.",
                        "error_code": "CSRF_SESSION_MISSING"
                    }
                )

            if not request_token:
                logger.warning(f"CSRF validation failed: No request token for {request.method} {request.url.path}")
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "detail": "CSRF token missing from request headers.",
                        "error_code": "CSRF_TOKEN_MISSING"
                    }
                )

            # Validate token match
            if not secrets.compare_digest(session_token, request_token):
                logger.warning(f"CSRF validation failed: Token mismatch for {request.method} {request.url.path}")
                return JSONResponse(
                    status_code=403,
                    content={
                        "success": False,
                        "detail": "CSRF token validation failed. Please refresh the page.",
                        "error_code": "CSRF_TOKEN_INVALID"
                    }
                )

            logger.debug(f"CSRF validation passed for {request.method} {request.url.path}")

        # Token validated or OPTIONS request - proceed
        return await call_next(request)


def get_csrf_token(request: Request) -> Optional[str]:
    """
    Helper function to get CSRF token from request session.

    Args:
        request: FastAPI request object

    Returns:
        CSRF token string or None
    """
    return request.session.get("csrf_token")


def generate_csrf_token(request: Request) -> str:
    """
    Helper function to generate and store a new CSRF token.

    Args:
        request: FastAPI request object

    Returns:
        Generated CSRF token
    """
    token = secrets.token_urlsafe(32)
    request.session["csrf_token"] = token
    return token
