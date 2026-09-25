"""One id per request, in the logs and in the response, so a complaint can be traced to its run.

A thumbs down on a review (#51) is only useful if it leads back to what produced the review: the
prompt version, the model that answered, the articles it read, what it cost. All of that is in the
log events of the request. The id binds them together and travels back to the client in the
`X-Request-ID` header and in the body of every review and answer, so the client can send it with
its feedback.

The id is generated here, never taken from the caller: a client-chosen id would let a caller write
arbitrary values into the logs, or collide with someone else's request on purpose.
"""

from uuid import uuid4

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = str(uuid4())
        request.state.request_id = request_id
        # Bound before the endpoint runs: the task that runs it copies this context, so every event
        # of the request carries the id without anyone passing it along.
        structlog.contextvars.bind_contextvars(request_id=request_id)
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def request_id_of(request: Request) -> str | None:
    """The id of this request, for the response body; None only for an app built without the middleware."""
    return getattr(request.state, "request_id", None)
