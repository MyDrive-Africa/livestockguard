"""
Prometheus metrics for the API Gateway.

Tracks:
- Request count by method, path, status
- Request latency histogram
- Active WebSocket connections
- Database query count

Exposes /metrics endpoint for Prometheus scraping.
"""

import time
from typing import Callable

from fastapi import FastAPI, Request, Response
from fastapi.routing import APIRoute


# ─── In-Memory Metrics Store ─────────────────────────
# (In production, replace with prometheus_client library)

class Metrics:
    """Simple in-memory metrics collector."""

    def __init__(self):
        self.request_count: dict[str, int] = {}
        self.request_latency_sum: dict[str, float] = {}
        self.request_latency_count: dict[str, int] = {}
        self.active_ws_connections: int = 0
        self.total_alerts_dispatched: int = 0
        self.total_positions_ingested: int = 0

    def record_request(self, method: str, path: str, status: int, latency: float):
        key = f'{method}:{path}:{status}'
        self.request_count[key] = self.request_count.get(key, 0) + 1
        self.request_latency_sum[key] = self.request_latency_sum.get(key, 0) + latency
        self.request_latency_count[key] = self.request_latency_count.get(key, 0) + 1

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = [
            "# HELP livestockguard_http_requests_total Total HTTP requests",
            "# TYPE livestockguard_http_requests_total counter",
        ]
        for key, count in self.request_count.items():
            method, path, status = key.split(':')
            lines.append(
                f'livestockguard_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}'
            )

        lines.extend([
            "",
            "# HELP livestockguard_http_request_duration_seconds HTTP request latency",
            "# TYPE livestockguard_http_request_duration_seconds summary",
        ])
        for key, total in self.request_latency_sum.items():
            method, path, status = key.split(':')
            count = self.request_latency_count[key]
            avg = total / count if count > 0 else 0
            lines.append(
                f'livestockguard_http_request_duration_seconds_sum{{method="{method}",path="{path}",status="{status}"}} {total:.4f}'
            )
            lines.append(
                f'livestockguard_http_request_duration_seconds_count{{method="{method}",path="{path}",status="{status}"}} {count}'
            )

        lines.extend([
            "",
            "# HELP livestockguard_ws_connections Active WebSocket connections",
            "# TYPE livestockguard_ws_connections gauge",
            f"livestockguard_ws_connections {self.active_ws_connections}",
            "",
            "# HELP livestockguard_alerts_dispatched_total Total alerts dispatched",
            "# TYPE livestockguard_alerts_dispatched_total counter",
            f"livestockguard_alerts_dispatched_total {self.total_alerts_dispatched}",
            "",
            "# HELP livestockguard_positions_ingested_total Total positions ingested",
            "# TYPE livestockguard_positions_ingested_total counter",
            f"livestockguard_positions_ingested_total {self.total_positions_ingested}",
        ])

        return "\n".join(lines) + "\n"


# Global metrics instance
metrics = Metrics()


def add_metrics_middleware(app: FastAPI):
    """Add request metrics middleware to the FastAPI app."""

    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next: Callable) -> Response:
        # Skip metrics endpoint itself
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        response = await call_next(request)
        latency = time.perf_counter() - start

        # Normalize path (remove UUIDs for cardinality control)
        path = _normalize_path(request.url.path)
        metrics.record_request(
            method=request.method,
            path=path,
            status=response.status_code,
            latency=latency,
        )

        # Add latency header for debugging
        response.headers["X-Response-Time"] = f"{latency*1000:.1f}ms"
        return response


def _normalize_path(path: str) -> str:
    """Replace UUIDs in paths with :id to reduce metric cardinality."""
    import re
    return re.sub(
        r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
        ':id',
        path,
    )
