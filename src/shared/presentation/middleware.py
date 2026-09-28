import logging
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Read this wherever a log line is written during a request: every line of one
# request carries the same id, so a single run is greppable end to end.
current_request_id: ContextVar[str] = ContextVar('current_request_id', default='-')

REQUEST_ID_LENGTH = 12
MILLISECONDS_PER_SECOND = 1000

logger = logging.getLogger('video_helper.request')


class LogContextMiddleware(BaseHTTPMiddleware):
    """Give every request an id and log how it ended."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Tag the request, time it, and log one line whether it answers or raises."""
        token = current_request_id.set(uuid4().hex[:REQUEST_ID_LENGTH])
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            self._log(request=request, status_code=500, started_at=started_at)
            current_request_id.reset(token)
            raise
        self._log(request=request, status_code=response.status_code, started_at=started_at)
        current_request_id.reset(token)
        return response

    @staticmethod
    def _log(*, request: Request, status_code: int, started_at: float) -> None:
        """Write the one line that says what happened to this request."""
        elapsed = (time.perf_counter() - started_at) * MILLISECONDS_PER_SECOND
        logger.info(
            '[%s] %s %s -> %s in %.0f ms',
            current_request_id.get(),
            request.method,
            request.url.path,
            status_code,
            elapsed,
        )
