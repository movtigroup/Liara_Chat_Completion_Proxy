import os
import json
import uuid
import time
import asyncio
from typing import Dict, Literal
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, APIRouter, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import httpx
import cachetools
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from link import LIARA_BASE_URLS
from schemas import CompletionRequest
from utils import generate_cache_key, get_headers
from errors import (
    UpstreamServiceDownError,
    UpstreamTimeoutError,
    UpstreamResponseError,
    GeneralProxyError,
)

# API Key Authentication
from typing import Dict, Literal, Tuple # Added Tuple

API_KEY_NAME = "Authorization"
api_key_header_scheme = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

APIKeyDetails = Tuple[str, Literal["v1_customer", "v2_business"]]

async def get_api_key_details(api_key_header: str = Security(api_key_header_scheme)) -> APIKeyDetails:
    if not api_key_header or not api_key_header.startswith("Bearer "):
        # This specific check might be better handled by auto_error=True on APIKeyHeader if we only want bearer
        # but custom message is also fine.
        raise HTTPException(status_code=401, detail="Authorization header is missing or not a Bearer token.")

    api_key = api_key_header.replace("Bearer ", "").strip()

    if not api_key:
        raise HTTPException(status_code=401, detail="API Key is empty after stripping Bearer prefix.")

    # Placeholder logic for tier differentiation & validation
    # In a real system, this would involve checking against a database or secure configuration.
    if api_key.startswith("biz-valid-") and len(api_key) > len("biz-valid-"): # Ensure there's something after prefix
        return api_key, "v2_business"
    elif api_key.startswith("cust-valid-") and len(api_key) > len("cust-valid-"):
        return api_key, "v1_customer"
    elif api_key == "test-api-key": # Grandfathering old test key to v1 for existing tests
        return api_key, "v1_customer"

    # If key doesn't match any known valid format or tier
    raise HTTPException(status_code=403, detail="Invalid API Key or tier.")


# Rate Limiters
limiter = Limiter(key_func=get_remote_address) # Main limiter instance

# Specific limiters for different tiers - applied per route.
# These strings need to be registered if not using default_limits in the main Limiter.
# For simplicity, we can apply them directly in decorators if slowapi supports it,
# or have different limiter instances. Let's use different instances.

limiter_v1 = Limiter(key_func=get_remote_address, default_limits=["100/minute"], strategy="fixed-window")
limiter_v2 = Limiter(key_func=get_remote_address, default_limits=["1000/minute"], strategy="fixed-window")


app = FastAPI(
    title="AI Proxy API",
    description="پروکسی پیشرفته برای مدل‌های هوش مصنوعی, now with v1 (Customer) and v2 (Business) tiers.",
    version="2.1", # Version bump
)
app.state.limiter = limiter # Global limiter for non-tiered specific checks if any, or for slowapi state
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Routers
router_v1 = APIRouter(prefix="/api/v1")
router_v2 = APIRouter(prefix="/api/v2")
ws_router_v1 = APIRouter(prefix="/ws/v1")
ws_router_v2 = APIRouter(prefix="/ws/v2")


# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# تنظیمات لاگ
os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/app.log",
    rotation="10 MB",
    retention="10 days",
    level="DEBUG",
    enqueue=True,
    backtrace=True,
    diagnose=True,
)
logger.configure(
    handlers=[
        {"sink": "logs/app.log", "level": "DEBUG"},
        {"sink": "stderr", "level": "INFO"},
    ]
)

# Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# کش برای ذخیره پاسخ‌ها
cache = cachetools.TTLCache(maxsize=1000, ttl=300)  # 5 minutes


# WebSocket Manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        async with self.lock:
            self.active_connections[connection_id] = websocket

    async def disconnect(self, connection_id: str): # Made async
        async with self.lock:
            if connection_id in self.active_connections:
                del self.active_connections[connection_id]

    async def send_message(self, connection_id: str, message: str):
        async with self.lock:
            if connection_id in self.active_connections:
                try:
                    await self.active_connections[connection_id].send_text(message)
                except Exception as e:
                    logger.error(f"Error sending message to {connection_id}: {e}")


manager = ConnectionManager()


# Middleware برای لاگ‌گیری
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info(f"Request: {request.method} {request.url}")
        start_time = time.time()

        try:
            response = await call_next(request)
        except Exception as e:
            logger.exception(f"Unhandled exception: {e}")
            return JSONResponse(
                status_code=500, content={"detail": "Internal server error"}
            )

        process_time = (time.time() - start_time) * 1000
        logger.info(f"Response: {response.status_code} ({process_time:.2f}ms)")
        return response


app.add_middleware(LoggingMiddleware)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTPException: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
    )


@app.get("/", include_in_schema=False)
async def serve_documentation():
    return HTMLResponse(content=open("static/index.html", "r").read(), status_code=200)


# Shared logic for HTTP chat completions
async def _handle_chat_completions_request(
    api_key_details: APIKeyDetails, # Now expects the tuple from get_api_key_details
    body: CompletionRequest
):
    """Handles the core logic for chat completions, shared by v1 and v2."""
    api_key, tier = api_key_details # Unpack the key and tier

    # Tier could be used here in the future for tier-specific logic (e.g., different models, logging)
    # logger.info(f"Handling chat completion for tier: {tier} with key: {api_key[:10]}...")


    request_data = body.model_dump(exclude_unset=True)

    # بررسی کش
    cache_key = generate_cache_key(request_data)
    if cache_key in cache:
        logger.info("Cache hit")
        return JSONResponse(content=cache[cache_key])

    # فوروارد به لیارا
    last_exception = None
    for url in LIARA_BASE_URLS:
        try:
            async with httpx.AsyncClient(timeout=30) as client: # Standard timeout for a successful response
                response = await client.post(
                    f"{url}/chat/completions",
                    headers=get_headers(api_key),
                    json=request_data,
                )

                if response.status_code == 200:
                    response_data = response.json()
                    cache[cache_key] = response_data
                    return JSONResponse(content=response_data, status_code=200)
                else:
                    # This is an error response from Liara (e.g., 4xx, 5xx from Liara)
                    logger.warning(
                        f"Upstream service at {url} returned error: {response.status_code} - {response.text}"
                    )
                    # Store this as the reason for potential UpstreamResponseError if all servers fail this way
                    last_exception = UpstreamResponseError(
                        upstream_status_code=response.status_code,
                        upstream_error_message=response.text
                    )
                    # Continue to try other servers
                    continue

        except httpx.TimeoutException as e:
            logger.warning(f"Request to upstream service at {url} timed out: {str(e)}")
            last_exception = UpstreamTimeoutError()
            continue # Try next server

        except httpx.ConnectError as e:
            logger.warning(f"Could not connect to upstream service at {url}: {str(e)}")
            last_exception = UpstreamServiceDownError(detail=f"Could not connect to AI service endpoint: {url}. It may be temporarily down.")
            continue # Try next server

        except httpx.HTTPStatusError as e: # Should be less common with direct status code checking
            logger.error(f"HTTPStatusError from upstream service {url}: {e.response.status_code} - {e.response.text}")
            last_exception = UpstreamResponseError(
                upstream_status_code=e.response.status_code,
                upstream_error_message=e.response.text
            )
            # If an HTTPStatusError is critical enough to stop trying other servers, re-raise or handle.
            # For now, let's assume we try the next server.
            continue

        except Exception as e: # Catch any other httpx or unexpected errors during the request
            logger.error(f"Unexpected error connecting to upstream service {url}: {str(e)}", exc_info=True)
            last_exception = GeneralProxyError(detail=f"An unexpected error occurred while contacting AI service: {url}.")
            continue # Try next server

    # If loop completes without returning a successful response
    if last_exception:
        # If the last exception was an UpstreamResponseError from the final server,
        # it means all servers were tried and this was the "best" error we got.
        # Or if it was Timeout/ConnectError from the last one.
        raise last_exception
    
    # If LIARA_BASE_URLS was empty or all servers failed in a way that didn't set last_exception (should not happen with current logic)
    raise UpstreamServiceDownError(detail="All AI service endpoints are currently unavailable or failed.")

# --- V1 API Endpoints ---
@router_v1.post("/chat/completions", response_model=None) # response_model can be more specific if needed
@limiter_v1.limit("100/minute") # Apply v1 rate limit
async def v1_chat_completions(
    request: Request, # Required by slowapi
    body: CompletionRequest,
    api_key_details: APIKeyDetails = Security(get_api_key_details)
):
    """Customer Tier Chat Completions."""
    _, tier = api_key_details
    if tier != "v1_customer":
        # This check could also be part of get_api_key_details by passing expected_tier
        raise HTTPException(status_code=403, detail="This API key is not authorized for v1 (Customer) access.")

    # The first element of api_key_details is the actual key string
    return await _handle_chat_completions_request(api_key_details, body)

# --- V2 API Endpoints ---
@router_v2.post("/chat/completions", response_model=None)
@limiter_v2.limit("1000/minute") # Apply v2 rate limit
async def v2_chat_completions(
    request: Request, # Required by slowapi
    body: CompletionRequest,
    api_key_details: APIKeyDetails = Security(get_api_key_details)
):
    """Business Tier Chat Completions."""
    _, tier = api_key_details
    if tier != "v2_business":
        raise HTTPException(status_code=403, detail="This API key is not authorized for v2 (Business) access.")

    return await _handle_chat_completions_request(api_key_details, body)


# Shared logic for WebSocket chat
async def _handle_websocket_chat(websocket: WebSocket, raw_api_key: str, tier_for_logging: str):
    """Handles the core logic for WebSocket chat, shared by v1 and v2."""
    # `raw_api_key` is the plain key string.
    # `tier_for_logging` is "v1_customer" or "v2_business".

    connection_id = str(uuid.uuid4())
    await manager.connect(websocket, connection_id)
    logger.info(f"WebSocket connection {connection_id} established for tier: {tier_for_logging}")

    try:
        # API Key already validated by the endpoint decorator's dependency.
        # We have `raw_api_key` to use with `get_headers`.

        # دریافت تنظیمات مدل
        config = await websocket.receive_json() # First message after auth is config
        request_data = {
            "model": config.get("model", "openai/gpt-4o-mini"),
            "messages": config.get("messages", []),
            "stream": True,
            **{k: v for k, v in config.items() if k not in ["model", "messages"]},
        }

        # فوروارد به لیارا
        success = False
        last_error_payload = None # To store the error details from the last attempt

        for url in LIARA_BASE_URLS:
            try:
                async with httpx.AsyncClient(timeout=60) as client: # Keep a longer timeout for potential streaming
                    async with client.stream(
                        "POST",
                        f"{url}/chat/completions",
                        headers=get_headers(api_key),
                        json=request_data,
                    ) as response:
                        if response.status_code == 200:
                            async for chunk in response.aiter_text():
                                if chunk.strip(): # Ensure not sending empty keep-alive chunks if any
                                    await manager.send_message(connection_id, chunk)
                            success = True
                            break # Exit server loop on success
                        else:
                            # Upstream returned an error status code (e.g., 4xx, 5xx from Liara)
                            err = UpstreamResponseError(response.status_code, response.text)
                            logger.warning(f"WS: Upstream service at {url.split('/')[2]} returned error: {response.status_code} - {response.text}")
                            last_error_payload = {"error": err.detail}
                            continue # Try next server

            except httpx.TimeoutException as e:
                err = UpstreamTimeoutError()
                logger.warning(f"WS: Request to AI service at {url.split('/')[2]} timed out: {str(e)}")
                last_error_payload = {"error": err.detail}
                continue # Try next server

            except httpx.ConnectError as e:
                err = UpstreamServiceDownError(detail=f"Could not connect to AI service endpoint: {url.split('/')[2]}. It may be temporarily down.")
                logger.warning(f"WS: Could not connect to AI service at {url.split('/')[2]}: {str(e)}")
                last_error_payload = {"error": err.detail}
                continue # Try next server

            except Exception as e: # Catch any other httpx or unexpected errors during the request to a specific server
                                   # This is likely an error *during* active streaming if connection was successful
                err = GeneralProxyError(detail=f"An unexpected problem occurred while streaming from AI service: {url.split('/')[2]}.")
                logger.error(f"WS: Unexpected error with AI service at {url.split('/')[2]} during stream: {str(e)}", exc_info=True)
                if isinstance(e, UpstreamServiceError): # If it was already one of our custom types somehow
                    last_error_payload = {"error": e.detail}
                else:
                    last_error_payload = {"error": err.detail}
                # This kind of error is critical for an active stream, send error and terminate.
                await websocket.send_json(last_error_payload)
                return # Exit the main websocket_chat function as the stream failed mid-way

        if not success:
            if last_error_payload:
                await websocket.send_json(last_error_payload)
            else:
                # This case means LIARA_BASE_URLS was empty, or some other logic flaw
                err = UpstreamServiceDownError(detail="No AI service endpoints are configured or all failed to respond.")
                await websocket.send_json({"error": err.detail})
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except json.JSONDecodeError:
        # This error occurs if the client sends malformed JSON for API key or config
        await websocket.send_json({"error": "Invalid JSON message format received from client."})
    except Exception as e:
        # General unhandled error in the WebSocket logic itself
        logger.exception(f"General WebSocket error for {connection_id}: {str(e)}")
        err = GeneralProxyError(detail="An internal server error occurred in the WebSocket service.")
        try:
            await websocket.send_json({"error": err.detail})
        except Exception: # If sending itself fails (e.g., socket already closed abruptly)
            logger.error(f"Failed to send error to already closed WebSocket {connection_id}")
    finally:
        await manager.disconnect(connection_id) # Ensure disconnect is awaited

# --- V1 WebSocket Endpoints ---
@ws_router_v1.websocket("/chat/completions")
async def ws_v1_chat_completions(websocket: WebSocket):
    """Customer Tier WebSocket Chat Completions."""
    # Apply v1 rate limit conceptually here - slowapi doesn't directly decorate websockets easily.
    # This would typically be handled by checking request count against IP/key in ConnectionManager
    # or via a more complex setup if strict per-message rate limiting is needed.
    # For now, we acknowledge the design for different limits but don't implement WS rate limiting.

    # Manual API Key Auth for WebSocket
    try:
        auth_data = await websocket.receive_json()
        api_key_header_sim = auth_data.get("api_key") # Expecting format like "Bearer <key>"
        if not api_key_header_sim: # Basic check
             await websocket.send_json({"error": "API key is required as first message: {\"api_key\": \"Bearer <YOUR_KEY>\"}"})
             await websocket.close()
             return

        # Use a modified inline version of get_api_key_details logic
        if not api_key_header_sim.startswith("Bearer "):
            await websocket.send_json({"error": "Invalid API Key format. Expected Bearer token."})
            await websocket.close()
            return

        api_key = api_key_header_sim.replace("Bearer ", "").strip()
        if not api_key:
            await websocket.send_json({"error": "API Key is empty."})
            await websocket.close()
            return

        tier = "invalid"
        if api_key.startswith("cust-valid-") and len(api_key) > len("cust-valid-"):
            tier = "v1_customer"
        elif api_key == "test-api-key":
            tier = "v1_customer"

        if tier != "v1_customer":
            await websocket.send_json({"error": "This API key is not authorized for v1 (Customer) WebSocket access."})
            await websocket.close()
            return

        # If auth successful, proceed to shared handler
        await _handle_websocket_chat(websocket, api_key, "v1_customer")

    except json.JSONDecodeError:
        await websocket.send_json({"error": "Invalid JSON message format for authentication."})
        await websocket.close()
    except Exception as e: # Catch any other errors during auth phase
        logger.error(f"WebSocket auth error: {e}", exc_info=True)
        try:
            await websocket.send_json({"error": "Authentication failed."})
        except: pass # Ignore if sending fails
        await websocket.close()


# --- V2 WebSocket Endpoints ---
@ws_router_v2.websocket("/chat/completions")
async def ws_v2_chat_completions(websocket: WebSocket):
    """Business Tier WebSocket Chat Completions."""
    # Similar acknowledgement for v2 rate limiting for WebSockets.
    try:
        auth_data = await websocket.receive_json()
        api_key_header_sim = auth_data.get("api_key")
        if not api_key_header_sim:
             await websocket.send_json({"error": "API key is required as first message: {\"api_key\": \"Bearer <YOUR_KEY>\"}"})
             await websocket.close()
             return

        if not api_key_header_sim.startswith("Bearer "):
            await websocket.send_json({"error": "Invalid API Key format. Expected Bearer token."})
            await websocket.close()
            return

        api_key = api_key_header_sim.replace("Bearer ", "").strip()
        if not api_key:
            await websocket.send_json({"error": "API Key is empty."})
            await websocket.close()
            return

        tier = "invalid"
        if api_key.startswith("biz-valid-") and len(api_key) > len("biz-valid-"):
            tier = "v2_business"

        if tier != "v2_business":
            await websocket.send_json({"error": "This API key is not authorized for v2 (Business) WebSocket access."})
            await websocket.close()
            return

        await _handle_websocket_chat(websocket, api_key, "v2_business")

    except json.JSONDecodeError:
        await websocket.send_json({"error": "Invalid JSON message format for authentication."})
        await websocket.close()
    except Exception as e:
        logger.error(f"WebSocket auth error: {e}", exc_info=True)
        try:
            await websocket.send_json({"error": "Authentication failed."})
        except: pass
        await websocket.close()


# Include routers in the main app
app.include_router(router_v1)
app.include_router(router_v2)
app.include_router(ws_router_v1)
app.include_router(ws_router_v2)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8100,
        reload=True,
        ws_ping_interval=30,
        ws_ping_timeout=60,
    )
