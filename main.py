import os
import json
import uuid
import time
import asyncio
from typing import Dict, Literal, Tuple, Callable
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, APIRouter, Security
from fastapi.security.api_key import APIKeyHeader
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import httpx
import cachetools
import psutil

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

# --- Resource-Aware Configuration Functions ---
def get_sync_initial_cache_maxsize() -> int:
    """Determines cache maxsize based on available system memory."""
    try:
        mem_total_gb = psutil.virtual_memory().total / (1024 ** 3)
        if mem_total_gb > 7: return 2000
        elif mem_total_gb > 3.5: return 1000
        else: return 500
    except Exception as e:
        logger.warning(f"Could not determine system memory for cache sizing, defaulting to 500. Error: {e}")
        return 500

def get_sync_dynamic_customer_limit_str() -> str:
    """Generates a dynamic rate limit string for v1 customers."""
    try:
        num_cpus = os.cpu_count() or 1
        base_rate_per_core = 50
        limit = max(100, num_cpus * base_rate_per_core)
        if psutil.cpu_percent(interval=0.1) > 90: limit = max(50, int(limit * 0.75))
        return f"{limit}/minute"
    except Exception as e:
        logger.warning(f"Could not determine dynamic rate limit for v1, defaulting to 100/minute. Error: {e}")
        return "100/minute"

def get_sync_dynamic_business_limit_str() -> str:
    """Generates a dynamic rate limit string for v2 business tier."""
    try:
        num_cpus = os.cpu_count() or 1
        base_rate_per_core = 500
        limit = max(1000, num_cpus * base_rate_per_core)
        if psutil.cpu_percent(interval=0.1) > 90: limit = max(500, int(limit * 0.75))
        return f"{limit}/minute"
    except Exception as e:
        logger.warning(f"Could not determine dynamic rate limit for v2, defaulting to 1000/minute. Error: {e}")
        return "1000/minute"

def get_sync_dynamic_default_limit_str() -> str:
    """Generates a dynamic rate limit string for the global default limiter."""
    try:
        num_cpus = os.cpu_count() or 1
        base_rate_per_core = 50
        limit = max(100, num_cpus * base_rate_per_core)
        if psutil.cpu_percent(interval=0.1) > 85: limit = max(50, int(limit * 0.8))
        return f"{limit}/minute"
    except Exception as e:
        logger.warning(f"Could not determine dynamic default rate limit, defaulting to 100/minute. Error: {e}")
        return "100/minute"
# --- End Resource-Aware Configuration Functions ---

API_KEY_NAME = "Authorization"
api_key_header_scheme = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
APIKeyDetails = Tuple[str, Literal["v1_customer", "v2_business"]]

async def get_api_key_details(api_key_header: str = Security(api_key_header_scheme)) -> APIKeyDetails:
    if not api_key_header or not api_key_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header is missing or not a Bearer token.")
    api_key = api_key_header.replace("Bearer ", "").strip()
    if not api_key:
        raise HTTPException(status_code=401, detail="API Key is empty after stripping Bearer prefix.")
    if api_key.startswith("biz-valid-") and len(api_key) > len("biz-valid-"): return api_key, "v2_business"
    elif api_key.startswith("cust-valid-") and len(api_key) > len("cust-valid-"): return api_key, "v1_customer"
    elif api_key == "test-api-key": return api_key, "v1_customer"
    raise HTTPException(status_code=403, detail="Invalid API Key or tier.")

# Rate Limiters. The default_limits here are fallbacks if routes are not decorated.
# For decorated routes, the limit_value in the decorator takes precedence.
limiter_v1 = Limiter(key_func=get_remote_address, strategy="fixed-window")
limiter_v2 = Limiter(key_func=get_remote_address, strategy="fixed-window")

app = FastAPI(
    title="AI Proxy API",
    description="پروکسی پیشرفته برای مدل‌های هوش مصنوعی, now with v1 (Customer) and v2 (Business) tiers.",
    version="2.1",
)

# Global limiter, its default_limits will apply to routes not specifically decorated by other limiters
limiter = Limiter(key_func=get_remote_address, default_limits=[get_sync_dynamic_default_limit_str])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

router_v1 = APIRouter(prefix="/api/v1")
router_v2 = APIRouter(prefix="/api/v2")
ws_router_v1 = APIRouter(prefix="/ws/v1")
ws_router_v2 = APIRouter(prefix="/ws/v2")

app.mount("/static", StaticFiles(directory="static"), name="static")

os.makedirs("logs", exist_ok=True)
logger.add(
    "logs/app.log", rotation="10 MB", retention="10 days", level="DEBUG",
    enqueue=True, backtrace=True, diagnose=True,
)
logger.configure(handlers=[
    {"sink": "logs/app.log", "level": "DEBUG"}, {"sink": "stderr", "level": "INFO"},
])

cache = cachetools.TTLCache(maxsize=get_sync_initial_cache_maxsize(), ttl=300)
logger.info(f"Cache initialized with maxsize: {get_sync_initial_cache_maxsize()}")

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.lock = asyncio.Lock()
    async def connect(self, websocket: WebSocket, connection_id: str):
        await websocket.accept()
        async with self.lock: self.active_connections[connection_id] = websocket
    async def disconnect(self, connection_id: str):
        async with self.lock:
            if connection_id in self.active_connections: del self.active_connections[connection_id]
    async def send_message(self, connection_id: str, message: str):
        async with self.lock:
            if connection_id in self.active_connections:
                try: await self.active_connections[connection_id].send_text(message)
                except Exception as e: logger.error(f"Error sending message to {connection_id}: {e}")
manager = ConnectionManager()

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info(f"Request: {request.method} {request.url}")
        start_time = time.time()
        try: response = await call_next(request)
        except Exception as e:
            logger.exception(f"Unhandled exception: {e}")
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        process_time = (time.time() - start_time) * 1000
        logger.info(f"Response: {response.status_code} ({process_time:.2f}ms)")
        return response
app.add_middleware(LoggingMiddleware)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTPException: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

@app.get("/", include_in_schema=False)
async def serve_documentation():
    try:
        with open("static/index.html", "r") as f: content = f.read()
        return HTMLResponse(content=content, status_code=200)
    except FileNotFoundError:
        logger.error("static/index.html not found")
        return HTMLResponse(content="Documentation not found.", status_code=404)

async def _handle_chat_completions_request(api_key_details: APIKeyDetails, body: CompletionRequest):
    api_key, tier = api_key_details
    request_data = body.model_dump(exclude_unset=True)
    cache_key = generate_cache_key(request_data)
    if cache_key in cache:
        logger.info(f"Cache hit for key: {cache_key}")
        return JSONResponse(content=cache[cache_key])
    logger.info(f"Cache miss for key: {cache_key}")
    last_exception = None
    for url in LIARA_BASE_URLS:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(f"{url}/chat/completions", headers=get_headers(api_key), json=request_data)
                if response.status_code == 200:
                    response_data = response.json()
                    cache[cache_key] = response_data
                    logger.info(f"Successfully fetched from {url} and cached key: {cache_key}")
                    return JSONResponse(content=response_data, status_code=200)
                else:
                    logger.warning(f"Upstream service at {url} returned error: {response.status_code} - {response.text}")
                    last_exception = UpstreamResponseError(response.status_code, response.text)
                    continue
        except httpx.TimeoutException as e:
            logger.warning(f"Request to upstream service at {url} timed out: {str(e)}"); last_exception = UpstreamTimeoutError(); continue
        except httpx.ConnectError as e:
            logger.warning(f"Could not connect to upstream service at {url}: {str(e)}"); last_exception = UpstreamServiceDownError(f"Could not connect to AI service endpoint: {url}. It may be temporarily down."); continue
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTPStatusError from upstream service {url}: {e.response.status_code} - {e.response.text}"); last_exception = UpstreamResponseError(e.response.status_code, e.response.text); continue
        except Exception as e:
            logger.error(f"Unexpected error connecting to upstream service {url}: {str(e)}", exc_info=True); last_exception = GeneralProxyError(f"An unexpected error occurred while contacting AI service: {url}."); continue
    if last_exception: raise last_exception
    raise UpstreamServiceDownError("All AI service endpoints are currently unavailable or failed.")

# --- V1 API Endpoints ---
@router_v1.post("/chat/completions", response_model=None)
@limiter_v1.limit(get_sync_dynamic_customer_limit_str) # Pass the callable here
async def v1_chat_completions(request: Request, body: CompletionRequest, api_key_details: APIKeyDetails = Security(get_api_key_details)):
    _, tier = api_key_details
    if tier != "v1_customer": raise HTTPException(status_code=403, detail="This API key is not authorized for v1 (Customer) access.")
    return await _handle_chat_completions_request(api_key_details, body)

# --- V2 API Endpoints ---
@router_v2.post("/chat/completions", response_model=None)
@limiter_v2.limit(get_sync_dynamic_business_limit_str) # Pass the callable here
async def v2_chat_completions(request: Request, body: CompletionRequest, api_key_details: APIKeyDetails = Security(get_api_key_details)):
    _, tier = api_key_details
    if tier != "v2_business": raise HTTPException(status_code=403, detail="This API key is not authorized for v2 (Business) access.")
    return await _handle_chat_completions_request(api_key_details, body)

async def _handle_websocket_chat(websocket: WebSocket, raw_api_key: str, tier_for_logging: str):
    connection_id = str(uuid.uuid4())
    await manager.connect(websocket, connection_id)
    logger.info(f"WebSocket connection {connection_id} established for tier: {tier_for_logging}")
    try:
        config = await websocket.receive_json()
        request_data = {"model": config.get("model", "openai/gpt-4o-mini"), "messages": config.get("messages", []), "stream": True, **{k: v for k, v in config.items() if k not in ["model", "messages"]}}
        success = False; last_error_payload = None
        for url in LIARA_BASE_URLS:
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    async with client.stream("POST", f"{url}/chat/completions", headers=get_headers(raw_api_key), json=request_data) as response:
                        if response.status_code == 200:
                            async for chunk in response.aiter_text():
                                if chunk.strip(): await manager.send_message(connection_id, chunk)
                            success = True; break
                        else:
                            err_text = await response.aread(); err = UpstreamResponseError(response.status_code, err_text.decode(errors='ignore'))
                            logger.warning(f"WS: Upstream service at {url.split('/')[2]} returned error: {response.status_code} - {err.detail}"); last_error_payload = {"error": err.detail}; continue
            except httpx.TimeoutException as e: err = UpstreamTimeoutError(); logger.warning(f"WS: Request to AI service at {url.split('/')[2]} timed out: {str(e)}"); last_error_payload = {"error": err.detail}; continue
            except httpx.ConnectError as e: err = UpstreamServiceDownError(f"Could not connect to AI service endpoint: {url.split('/')[2]}. It may be temporarily down."); logger.warning(f"WS: Could not connect to AI service at {url.split('/')[2]}: {str(e)}"); last_error_payload = {"error": err.detail}; continue
            except Exception as e:
                err = GeneralProxyError(f"An unexpected problem occurred while streaming from AI service: {url.split('/')[2]}.")
                logger.error(f"WS: Unexpected error with AI service at {url.split('/')[2]} during stream: {str(e)}", exc_info=True)
                current_error_detail = getattr(e, 'detail', str(e))
                if isinstance(e, UpstreamResponseError) and hasattr(e, 'upstream_error_message') and e.upstream_error_message: current_error_detail = e.upstream_error_message
                last_error_payload = {"error": current_error_detail}
                try: await websocket.send_json(last_error_payload)
                except Exception as send_exc: logger.error(f"WS: Failed to send error to client {connection_id}: {send_exc}")
                return
        if not success:
            if last_error_payload: await websocket.send_json(last_error_payload)
            else: err = UpstreamServiceDownError("No AI service endpoints are configured or all failed to respond."); await websocket.send_json({"error": err.detail})
    except WebSocketDisconnect: logger.info(f"WebSocket disconnected: {connection_id}")
    except json.JSONDecodeError:
        logger.warning(f"WebSocket {connection_id}: Invalid JSON message format received from client.")
        try: await websocket.send_json({"error": "Invalid JSON message format received from client."})
        except Exception: pass
    except Exception as e:
        logger.exception(f"General WebSocket error for {connection_id}: {str(e)}")
        err = GeneralProxyError("An internal server error occurred in the WebSocket service.")
        try: await websocket.send_json({"error": err.detail})
        except Exception: logger.error(f"Failed to send error to already closed WebSocket {connection_id}")
    finally: await manager.disconnect(connection_id)

@ws_router_v1.websocket("/chat/completions")
async def ws_v1_chat_completions(websocket: WebSocket):
    raw_api_key_from_ws = ""
    try:
        auth_data = await websocket.receive_json()
        api_key_header_sim = auth_data.get("api_key")
        if not api_key_header_sim: await websocket.send_json({"error": "API key is required as first message: {\"api_key\": \"Bearer <YOUR_KEY>\"}"}); await websocket.close(); return
        if not api_key_header_sim.startswith("Bearer "): await websocket.send_json({"error": "Invalid API Key format. Expected Bearer token."}); await websocket.close(); return
        raw_api_key_from_ws = api_key_header_sim.replace("Bearer ", "").strip()
        if not raw_api_key_from_ws: await websocket.send_json({"error": "API Key is empty."}); await websocket.close(); return
        tier = "invalid"
        if raw_api_key_from_ws.startswith("cust-valid-") and len(raw_api_key_from_ws) > len("cust-valid-"): tier = "v1_customer"
        elif raw_api_key_from_ws == "test-api-key": tier = "v1_customer"
        if tier != "v1_customer": await websocket.send_json({"error": "This API key is not authorized for v1 (Customer) WebSocket access."}); await websocket.close(); return
        await _handle_websocket_chat(websocket, raw_api_key_from_ws, "v1_customer")
    except json.JSONDecodeError:
        logger.warning("WebSocket auth: Invalid JSON message format for authentication.")
        try: await websocket.send_json({"error": "Invalid JSON message format for authentication."}); await websocket.close()
        except Exception: await websocket.close()
    except Exception as e:
        logger.error(f"WebSocket auth error (v1): {e}", exc_info=True)
        try: await websocket.send_json({"error": "Authentication failed due to an internal error."}); await websocket.close()
        except: await websocket.close()

@ws_router_v2.websocket("/chat/completions")
async def ws_v2_chat_completions(websocket: WebSocket):
    raw_api_key_from_ws = ""
    try:
        auth_data = await websocket.receive_json()
        api_key_header_sim = auth_data.get("api_key")
        if not api_key_header_sim: await websocket.send_json({"error": "API key is required as first message: {\"api_key\": \"Bearer <YOUR_KEY>\"}"}); await websocket.close(); return
        if not api_key_header_sim.startswith("Bearer "): await websocket.send_json({"error": "Invalid API Key format. Expected Bearer token."}); await websocket.close(); return
        raw_api_key_from_ws = api_key_header_sim.replace("Bearer ", "").strip()
        if not raw_api_key_from_ws: await websocket.send_json({"error": "API Key is empty."}); await websocket.close(); return
        tier = "invalid"
        if raw_api_key_from_ws.startswith("biz-valid-") and len(raw_api_key_from_ws) > len("biz-valid-"): tier = "v2_business"
        if tier != "v2_business": await websocket.send_json({"error": "This API key is not authorized for v2 (Business) WebSocket access."}); await websocket.close(); return
        await _handle_websocket_chat(websocket, raw_api_key_from_ws, "v2_business")
    except json.JSONDecodeError:
        logger.warning("WebSocket auth: Invalid JSON message format for authentication.")
        try: await websocket.send_json({"error": "Invalid JSON message format for authentication."}); await websocket.close()
        except Exception: await websocket.close() # Ensure close on error
    except Exception as e:
        logger.error(f"WebSocket auth error (v2): {e}", exc_info=True)
        try: await websocket.send_json({"error": "Authentication failed due to an internal error."}); await websocket.close()
        except: await websocket.close() # Ensure close on error

app.include_router(router_v1); app.include_router(router_v2); app.include_router(ws_router_v1); app.include_router(ws_router_v2)

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Available CPUs: {os.cpu_count()}")
    logger.info(f"Initial cache maxsize: {get_sync_initial_cache_maxsize()}")
    logger.info(f"Initial v1 customer limit: {get_sync_dynamic_customer_limit_str()}")
    logger.info(f"Initial v2 business limit: {get_sync_dynamic_business_limit_str()}")
    logger.info(f"Initial default limit: {get_sync_dynamic_default_limit_str()}")
    uvicorn.run("main:app", host="0.0.0.0", port=8100, reload=True, ws_ping_interval=30, ws_ping_timeout=60)
