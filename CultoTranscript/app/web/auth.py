"""
Simple instance password authentication for CultoTranscript
"""
import os
from fastapi import HTTPException, status, Depends, Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

INSTANCE_PASSWORD = os.getenv("INSTANCE_PASSWORD", "admin123")


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to check instance password - blog-style with public viewing"""

    async def dispatch(self, request: Request, call_next):
        # Always public paths (no auth required)
        public_paths = ["/login", "/static", "/health", "/api/v2/events", "/api/websub"]

        # Public view paths (GET only)
        public_view_paths = ["/", "/videos", "/channels", "/reports"]

        # Public API GET endpoints
        public_api_gets = [
            "/api/videos",
            "/api/channels",
            "/api/jobs",
            "/api/videos/",  # Detail routes like /api/videos/{id}/transcript
            "/api/v2/videos",  # Backend v2 videos API
        ]

        # Public chatbot endpoints (POST allowed for public chat)
        if "/chat" in request.url.path and request.method == "POST":
            return await call_next(request)

        # Check if path is always public
        if any(request.url.path.startswith(path) for path in public_paths):
            return await call_next(request)

        # Check if endpoint has self-authentication (password verification in endpoint)
        # These endpoints verify password in request body or via require_auth dependency
        if "/reprocess" in request.url.path or \
           "/speaker" in request.url.path or \
           (request.method == "DELETE" and request.url.path.startswith("/api/videos/")):
            # Reprocess endpoint has password verification in body
            # Speaker endpoint allows public updates (CSRF protected)
            # DELETE endpoints use require_auth dependency for verification
            return await call_next(request)

        # Check if this is a public view (GET request on viewing pages)
        is_view_request = request.method == "GET"
        is_public_view = any(request.url.path.startswith(path) for path in public_view_paths)
        is_public_api_get = is_view_request and any(request.url.path.startswith(path) for path in public_api_gets)

        if is_view_request and (is_public_view or is_public_api_get):
            # Public viewing allowed
            return await call_next(request)

        # For write operations (POST, PUT, DELETE), require authentication
        is_authenticated = request.session.get("authenticated", False)

        if not is_authenticated:
            # Redirect to login page
            if request.url.path.startswith("/api"):
                # For API endpoints, return 401
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Não autenticado - operação requer login"
                )
            else:
                # For web pages, redirect to login
                return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

        # Authenticated, continue
        return await call_next(request)


def verify_password(password: str) -> bool:
    """
    Verify instance password

    Args:
        password: Password to verify

    Returns:
        True if password matches
    """
    return password == INSTANCE_PASSWORD


def get_current_user(request: Request):
    """
    Dependency to get current authenticated user (optional for blog-style viewing)

    Returns:
        "admin" for authenticated sessions, None for anonymous users
    """
    is_authenticated = request.session.get("authenticated", False)

    if not is_authenticated:
        return None

    # For v1, all authenticated users are "admin"
    return "admin"


def require_auth(request: Request):
    """
    Dependency to require authentication (raises 401 if not authenticated)

    Use this for admin operations that must be protected
    """
    user = get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Não autenticado - operação requer login"
        )
    return user
