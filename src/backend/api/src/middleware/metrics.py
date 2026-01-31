"""
Middleware for tracking API metrics
"""

import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging
from prometheus_client import Histogram, Counter

from config import settings

logger = logging.getLogger(__name__)

# Prometheus metrics for API request tracking
api_request_duration = Histogram(
    "api_request_duration_seconds",
    "API request duration",
    ["method", "endpoint", "status_code"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
)

api_requests_total = Counter(
    "api_requests_total",
    "Total API requests",
    ["method", "endpoint", "status_code"],
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track API request metrics"""

    async def dispatch(self, request: Request, call_next):
        # Start timer
        start_time = time.time()

        # Get endpoint path (simplified - remove path parameters for grouping)
        endpoint = request.url.path
        # Remove common path parameters for better grouping
        if endpoint.startswith(settings.api_base_path):
            # Keep the structure but simplify
            pass

        method = request.method

        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            status_code = 500
            raise
        finally:
            # Record metrics
            duration = time.time() - start_time

            # Normalize endpoint for better grouping (remove IDs)
            normalized_endpoint = self._normalize_endpoint(endpoint)

            api_request_duration.labels(
                method=method,
                endpoint=normalized_endpoint,
                status_code=str(status_code),
            ).observe(duration)

            api_requests_total.labels(
                method=method,
                endpoint=normalized_endpoint,
                status_code=str(status_code),
            ).inc()

        return response

    def _normalize_endpoint(self, endpoint: str) -> str:
        """Normalize endpoint by replacing IDs with placeholders"""
        import re

        # Replace numeric IDs with {id}
        normalized = re.sub(r"/\d+", "/{id}", endpoint)
        # Replace UUIDs with {uuid}
        normalized = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{uuid}",
            normalized,
            flags=re.IGNORECASE,
        )
        return normalized
