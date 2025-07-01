from fastapi import HTTPException

class BaseCustomError(HTTPException):
    """Base class for custom API exceptions."""
    def __init__(self, status_code: int, detail: str = None):
        super().__init__(status_code=status_code, detail=detail)

class UpstreamServiceDownError(BaseCustomError):
    """Custom exception for when the upstream service is confirmed to be down."""
    def __init__(self, detail: str = "The upstream service is temporarily down. Please try again later."):
        super().__init__(status_code=503, detail=detail)

class UpstreamTimeoutError(BaseCustomError):
    """Custom exception for when a request to the upstream service times out."""
    def __init__(self, detail: str = "The request to the upstream service timed out. Please try again later."):
        super().__init__(status_code=504, detail=detail)

class NetworkProblemError(BaseCustomError):
    """Custom exception for general network problems connecting to the upstream service."""
    # This could indicate issues on our end or between us and the upstream.
    # 503 might be more appropriate than 502 if it's a network issue preventing access.
    def __init__(self, detail: str = "A network problem occurred while trying to reach the upstream service. Please check your connection or try again later."):
        super().__init__(status_code=503, detail=detail)

class UpstreamResponseError(BaseCustomError):
    """Custom exception for unexpected error responses from the upstream service."""
    def __init__(self, upstream_status_code: int, upstream_detail: str = None):
        detail_message = f"The upstream service returned an unexpected error (HTTP {upstream_status_code})."
        if upstream_detail:
            detail_message += f" Detail: {upstream_detail}"
        # We might want to return a 502 Bad Gateway, as our service is acting as a gateway.
        super().__init__(status_code=502, detail=detail_message)

class InvalidAPIKeyError(BaseCustomError):
    """Custom exception for invalid or missing API Key."""
    def __init__(self, detail: str = "API Key is required or invalid."):
        super().__init__(status_code=401, detail=detail)

class RateLimitExceededError(BaseCustomError):
    """Custom exception for when rate limit is exceeded.
       Note: slowapi handles this by default with a 429, but if we want custom text.
    """
    def __init__(self, detail: str = "Rate limit exceeded. Please try again later."):
        super().__init__(status_code=429, detail=detail)

# Example of how these might be used:
# raise UpstreamTimeoutError()
# raise UpstreamResponseError(upstream_status_code=500, upstream_detail="Internal Server Error at Liara")

# We can also have specific handlers in main.py if we don't want them to directly be HTTPExceptions
# but rather translate them into specific JSON responses, e.g. for WebSockets.
# For now, inheriting HTTPException is the most straightforward for HTTP endpoints.
# For WebSockets, these exceptions won't be auto-handled by FastAPI;
# they'd need to be caught and their details sent as JSON messages over the WebSocket.
# The descriptions in the plan already account for this (send JSON error messages).
# The `InvalidAPIKeyError` and `RateLimitExceededError` are examples of how we might
# centralize other common HTTP errors if desired, though FastAPI and SlowAPI handle these well.
# I'll stick to the upstream-focused errors for now as per the request.
# The InvalidAPIKeyError is actually already handled by raising HTTPException(401, ...) in main.py.
# I will remove InvalidAPIKeyError and RateLimitExceededError for now to keep focus.
# Let's re-evaluate the provided custom errors.
# BaseCustomError is good.
# UpstreamServiceDownError (503) - "The service is temporarily down" - Good.
# UpstreamTimeoutError (504) - "The upstream service is taking too long / network problem" - Good.
# NetworkProblemError (503) - for other connection issues. The user prompt: "if the upstream service is taking too long, it says that there is a network problem". This suggests UpstreamTimeoutError should have the "network problem" phrasing.
# Let's refine:
# UpstreamTimeoutError -> "The request to the upstream service timed out, which might indicate a network problem. Please try again."
# UpstreamServiceDownError -> "The upstream service appears to be temporarily down. Please try again later."
# UpstreamResponseError -> for "another problem ... on the web or system" (meaning non-200 from Liara). This is 502.

# Revised definitions:
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
    def __init__(self, liara_status_code: int, liara_detail: str = None):
        custom_detail = f"The AI service returned an unexpected error (status: {liara_status_code})."
        if liara_detail:
            custom_detail += f" Details: {liara_detail}"
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
