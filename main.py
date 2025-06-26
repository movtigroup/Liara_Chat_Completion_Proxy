import os
import json
import uuid
import time
import asyncio
from functools import lru_cache
from typing import List, Union, Literal, Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from loguru import logger
import httpx
import cachetools
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware
from link import LIARA_BASE_URLS
from schemas import (
    TextContent,
    ImageURL,
    Message,
    Tool,
    CompletionRequest,
    ChatCompletionResponse
)
from utils import generate_cache_key, get_headers

app = FastAPI(
    title="AI Proxy API",
    description="پروکسی پیشرفته برای مدل‌های هوش مصنوعی",
    version="2.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# تنظیمات لاگ
os.makedirs("logs", exist_ok=True)
logger.add("logs/app.log", rotation="10 MB", retention="10 days", level="DEBUG", enqueue=True, backtrace=True, diagnose=True)
logger.configure(handlers=[{"sink": "logs/app.log", "level": "DEBUG"}, {"sink": "stderr", "level": "INFO"}])

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

    def disconnect(self, connection_id: str):
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
                status_code=500,
                content={"detail": "Internal server error"}
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

@app.post("/api/v1/chat/completions")
@limiter.limit("100/minute")
async def chat_completions(request: Request, body: CompletionRequest):
    """پایان‌پوینت اصلی برای چت"""
    api_key = request.headers.get("Authorization")
    if not api_key or not api_key.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="API Key is required in Authorization header"
        )
    
    api_key = api_key.replace("Bearer ", "").strip()
    request_data = body.dict(exclude_unset=True)
    
    # بررسی کش
    cache_key = generate_cache_key(request_data)
    if cache_key in cache:
        logger.info("Cache hit")
        return JSONResponse(content=cache[cache_key])
    
    # فوروارد به لیارا
    for url in LIARA_BASE_URLS:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{url}/chat/completions",
                    headers=get_headers(api_key),
                    json=request_data
                )
                
                if response.status_code == 200:
                    # ذخیره در کش
                    response_data = response.json()
                    cache[cache_key] = response_data
                    return JSONResponse(content=response_data, status_code=200)
                else:
                    logger.error(f"Liara error: {response.status_code} - {response.text}")
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            logger.warning(f"Connection failed to {url}: {str(e)}")
            continue
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from Liara: {e.response.status_code}")
            return JSONResponse(
                status_code=e.response.status_code,
                content={"detail": "Upstream service error"}
            )
    
    raise HTTPException(
        status_code=502,
        detail="All upstream servers are unavailable"
    )

@app.websocket("/ws/v1/chat/completions")
async def websocket_chat(websocket: WebSocket):
    """WebSocket برای چت استریمینگ"""
    connection_id = str(uuid.uuid4())
    await manager.connect(websocket, connection_id)
    
    try:
        # دریافت API Key
        auth_data = await websocket.receive_json()
        api_key = auth_data.get("api_key")
        if not api_key:
            await websocket.send_json({"error": "API Key is required"})
            return
        
        # دریافت تنظیمات مدل
        config = await websocket.receive_json()
        request_data = {
            "model": config.get("model", "openai/gpt-4o-mini"),
            "messages": config.get("messages", []),
            "stream": True,
            **{k: v for k, v in config.items() if k not in ["model", "messages"]}
        }
        
        # فوروارد به لیارا
        success = False
        for url in LIARA_BASE_URLS:
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    async with client.stream(
                        "POST",
                        f"{url}/chat/completions",
                        headers=get_headers(api_key),
                        json=request_data
                    ) as response:
                        if response.status_code != 200:
                            await websocket.send_json({
                                "error": f"Upstream error: {response.status_code}"
                            })
                            break
                        
                        async for chunk in response.aiter_text():
                            if chunk.strip():
                                await manager.send_message(connection_id, chunk)
                        success = True
                        break
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                logger.warning(f"Connection failed to {url}: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                await websocket.send_json({
                    "error": f"Connection error: {str(e)}"
                })
                break
        
        if not success:
            await websocket.send_json({
                "error": "All upstream servers failed"
            })
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
    except json.JSONDecodeError:
        await websocket.send_json({"error": "Invalid JSON format"})
    except Exception as e:
        logger.exception(f"WebSocket error: {str(e)}")
        await websocket.send_json({
            "error": "Internal server error"
        })
    finally:
        manager.disconnect(connection_id)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8100,
        reload=True,
        ws_ping_interval=30,
        ws_ping_timeout=60
    )
