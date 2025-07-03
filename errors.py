# errors.py
from fastapi import HTTPException

class UpstreamServiceError(HTTPException):
    """Base class for errors related to the upstream service."""
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)

class UpstreamServiceDownError(UpstreamServiceError):
    """Raised when the upstream service is consistently unavailable."""
    def __init__(self, detail: str = "The AI service is temporarily down. Please try again later."):
        super().__init__(status_code=503, detail=detail) # 503 Service Unavailable

class UpstreamTimeoutError(UpstreamServiceError):
    """Raised when a request to the upstream service times out."""
    def __init__(self, detail: str = "The AI service took too long to respond, possibly due to a network problem. Please try again."):
        super().__init__(status_code=504, detail=detail) # 504 Gateway Timeout

class UpstreamResponseError(UpstreamServiceError):
    """Raised when the upstream service returns an unexpected error response."""
    def __init__(self, upstream_status_code: int, upstream_detail: str = None):
        custom_detail = f"The AI service returned an unexpected error (status: {upstream_status_code})."
        if upstream_detail:
            custom_detail += f" Details: {upstream_detail}"
        # 502 Bad Gateway is appropriate as this app is a gateway.
        super().__init__(status_code=502, detail=custom_detail)

class GeneralProxyError(UpstreamServiceError):
    """For other web or system problems not fitting the above."""
    def __init__(self, detail: str = "An unexpected problem occurred with the AI proxy service. Please try again later."):
        super().__init__(status_code=500, detail=detail) # Internal Server Error for the proxy itself

# The user also mentioned "if there is another problem, it should be the same and say that it is on the web or system."
# This could be a generic 500 error from the proxy itself if it's not an upstream issue.
# The `GeneralProxyError` can cover this. `NetworkProblemError` might be too specific if we can't distinguish it from a timeout or service down.
# Let's keep these four: UpstreamServiceDownError, UpstreamTimeoutError, UpstreamResponseError, GeneralProxyError.
# The `main.py` code currently has a generic "All upstream servers are unavailable" (HTTPException 502). This should map to UpstreamServiceDownError.
# `httpx.ConnectError` could map to `UpstreamServiceDownError` or `NetworkProblemError`. If it happens for all servers, it's `UpstreamServiceDownError`.
# `httpx.TimeoutException` maps to `UpstreamTimeoutError`.
# Non-200s from Liara map to `UpstreamResponseError`.
# Unhandled exceptions in `main.py` are already caught by LoggingMiddleware and return a generic 500. We could raise `GeneralProxyError` explicitly for some cases.
# This looks like a good set.
