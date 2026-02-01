"""
Search Router - stub implementation
Routes queries to appropriate search strategies
"""
from typing import Optional, Tuple, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class SearchRouter:
    """Routes search queries. Stub implementation."""

    def route(self, query: str, **kwargs) -> str:
        """Route a query. Returns default strategy."""
        return "hybrid"

    def route_query(
        self,
        query: str,
        query_type: str,
        query_intent: str,
        channel_id: int,
        filters: Dict[str, Any] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Route a query to the appropriate search strategy.

        Returns:
            Tuple of (strategy_name, params_dict)
            Strategy can be: 'hybrid', 'semantic', 'direct_database'
        """
        filters = filters or {}

        # Default to hybrid search for most queries
        # This stub always uses hybrid to let the embedding service handle it
        strategy = "hybrid"
        params = {
            "query": query,
            "query_type": query_type,
            "query_intent": query_intent,
            "channel_id": channel_id,
            "filters": filters
        }

        logger.info(f"SearchRouter: routing to '{strategy}' strategy")
        return strategy, params

    def execute_direct_list_query(
        self,
        channel_id: int,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> List[Any]:
        """
        Execute a direct database query for listing videos.
        Stub - returns empty list (falls back to normal search).
        """
        logger.info(f"SearchRouter: execute_direct_list_query (stub) for channel {channel_id}")
        return []


_router_instance: Optional[SearchRouter] = None


def get_router() -> SearchRouter:
    """Get singleton router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = SearchRouter()
    return _router_instance
