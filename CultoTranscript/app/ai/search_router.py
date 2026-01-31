"""
Search Router - stub implementation
Routes queries to appropriate search strategies
"""
from typing import Optional


class SearchRouter:
    """Routes search queries. Stub implementation."""

    def route(self, query: str, **kwargs) -> str:
        """Route a query. Returns default strategy."""
        return "hybrid"


_router_instance: Optional[SearchRouter] = None


def get_router() -> SearchRouter:
    """Get singleton router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = SearchRouter()
    return _router_instance
