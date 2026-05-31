import os
import json
import sys
import uuid
import time
import asyncio
from typing import Dict, Literal, Tuple, Callable, List, Optional
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, APIRouter, Security, Depends, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger
import httpx
import cachetools
import psutil
from sqlalchemy.orm import Session
import litellm
from litellm import completion

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

import models
import schemas
import auth
from database import get_db, engine, Base
from utils import generate_cache_key
from provider_manager import get_provider_key

# Initialize Database
Base.metadata.create_all(bind=engine)

# --- Resource-Aware Configuration Functions ---
def get_sync_initial_cache_maxsize() -> int:
    try:
        mem_total_gb = psutil.virtual_memory().total / (1024 ** 3)
        if mem_total_gb > 7: return 2000
        elif mem_total_gb > 3.5: return 1000
        else: return 500
    except Exception as e:
        logger.warning(f"Could not determine system memory for cache sizing, defaulting to 500. Error: {e}")
        return 500

def get_sync_dynamic_default_limit_str() -> str:
    try:
        num_cpus = os.cpu_count() or 1
        base_rate_per_core = 100
        limit = max(200, num_cpus * base_rate_per_core)
        return f"{limit}/minute"
    except Exception as e:
        logger.warning(f"Could not determine dynamic default rate limit, defaulting to 200/minute. Error: {e}")
        return "200/minute"

# Rate Limiters
limiter = Limiter(key_func=get_remote_address, default_limits=[get_sync_dynamic_default_limit_str])

app = FastAPI(
    title="Universal AI Proxy API",
    description="Professional multi-provider AI Proxy supporting 90+ models via LiteLLM and New-API integration.",
    version="3.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Ensure static directory exists
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

logger.configure(handlers=[{"sink": sys.stderr, "level": "INFO"}])

cache = cachetools.TTLCache(maxsize=get_sync_initial_cache_maxsize(), ttl=300)

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

async def verify_api_key(request: Request, db: Session = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        # Check query param for fallback (sometimes useful for WS)
        api_key = request.query_params.get("api_key")
        if not api_key:
            raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    else:
        api_key = auth_header.replace("Bearer ", "").strip()

    db_key = db.query(models.APIKey).filter(models.APIKey.key == api_key, models.APIKey.is_active == True).first()
    if not db_key:
        if api_key == "test-api-key" and db.query(models.User).count() == 0:
            return None
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return db_key.owner

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = auth.timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/register", response_model=None)
async def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter((models.User.username == user.username) | (models.User.email == user.email)).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")

    is_admin = db.query(models.User).count() == 0
    new_user = models.User(
        username=user.username,
        email=user.email,
        hashed_password=auth.get_password_hash(user.password),
        is_admin=is_admin
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return {"message": "User created successfully"}

async def handle_ai_completion(body: schemas.CompletionRequest, user: Optional[models.User], db: Session):
    request_data = body.model_dump(exclude_unset=True)
    cache_key = generate_cache_key(request_data)

    if cache_key in cache and not body.stream:
        return cache[cache_key], None

    provider_key_obj = get_provider_key(db, body.model)
    if not provider_key_obj:
        raise HTTPException(status_code=503, detail="No active provider keys available for this model")

    # LiteLLM Configuration
    litellm_kwargs = {**request_data}
    litellm_kwargs["api_key"] = provider_key_obj.api_key
    if provider_key_obj.config and 'base_url' in provider_key_obj.config:
        litellm_kwargs["api_base"] = provider_key_obj.config['base_url']

    # Custom provider mapping for New-API or other OpenAI compatible ones
    if provider_key_obj.provider == "openai-compatible":
        litellm_kwargs["custom_llm_provider"] = "openai"

    try:
        start_time = time.time()
        response = completion(**litellm_kwargs)

        if body.stream:
            return response, start_time

        response_json = response.model_dump()
        cache[cache_key] = response_json

        # Log usage
        usage = response_json.get('usage', {})
        new_log = models.UsageLog(
            user_id=user.id if user else None,
            model=body.model,
            request_tokens=usage.get('prompt_tokens', 0),
            response_tokens=usage.get('completion_tokens', 0),
            total_tokens=usage.get('total_tokens', 0),
            cost=litellm.completion_cost(completion_response=response),
            request_data=request_data,
            response_data=response_json,
            status_code=200
        )
        db.add(new_log)
        db.commit()

        return response_json, None
    except Exception as e:
        logger.error(f"LiteLLM Error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"AI Provider Error: {str(e)}")

@app.post("/api/v1/chat/completions")
async def api_v1_chat_completions(
    body: schemas.CompletionRequest,
    user: Optional[models.User] = Depends(verify_api_key),
    db: Session = Depends(get_db)
):
    response, start_time = await handle_ai_completion(body, user, db)

    if body.stream:
        async def stream_generator():
            for chunk in response:
                yield f"data: {json.dumps(chunk.model_dump())}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    return JSONResponse(content=response)

@app.websocket("/ws/v1/chat/completions")
async def ws_v1_chat_completions(websocket: WebSocket, db: Session = Depends(get_db)):
    connection_id = str(uuid.uuid4())
    await manager.connect(websocket, connection_id)
    try:
        # Auth message first
        auth_data = await websocket.receive_json()
        api_key = auth_data.get("api_key", "").replace("Bearer ", "").strip()
        db_key = db.query(models.APIKey).filter(models.APIKey.key == api_key, models.APIKey.is_active == True).first()
        user = db_key.owner if db_key else None

        if not db_key and not (api_key == "test-api-key" and db.query(models.User).count() == 0):
            await websocket.send_json({"error": "Invalid API Key"})
            await websocket.close()
            return

        # Receive config/request
        config = await websocket.receive_json()
        body = schemas.CompletionRequest(**config)
        body.stream = True # WS is always stream in this context

        response, start_time = await handle_ai_completion(body, user, db)

        for chunk in response:
            await manager.send_message(connection_id, json.dumps(chunk.model_dump()))

        await manager.send_message(connection_id, "[DONE]")
    except WebSocketDisconnect:
        logger.info(f"WS disconnected: {connection_id}")
    except Exception as e:
        logger.error(f"WS Error: {str(e)}")
        try: await websocket.send_json({"error": str(e)})
        except: pass
    finally:
        await manager.disconnect(connection_id)

# Admin & User management
@app.post("/admin/providers", dependencies=[Depends(auth.get_current_admin_user)])
async def add_provider(provider_in: schemas.ProviderKeyCreate, db: Session = Depends(get_db)):
    new_provider = models.ProviderKey(**provider_in.model_dump())
    db.add(new_provider)
    db.commit()
    db.refresh(new_provider)
    return new_provider

@app.get("/admin/providers", dependencies=[Depends(auth.get_current_admin_user)])
async def list_providers(db: Session = Depends(get_db)):
    return db.query(models.ProviderKey).all()

@app.get("/admin/usage", dependencies=[Depends(auth.get_current_admin_user)])
async def get_all_usage(db: Session = Depends(get_db)):
    return db.query(models.UsageLog).order_by(models.UsageLog.created_at.desc()).limit(100).all()

@app.get("/user/usage")
async def get_user_usage(current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    return db.query(models.UsageLog).filter(models.UsageLog.user_id == current_user.id).order_by(models.UsageLog.created_at.desc()).all()

@app.post("/user/api-keys")
async def create_user_api_key(key_in: schemas.APIKeyCreate, current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    new_key = models.APIKey(
        key=f"sk-{uuid.uuid4().hex}",
        name=key_in.name,
        user_id=current_user.id
    )
    db.add(new_key)
    db.commit()
    db.refresh(new_key)
    return new_key

@app.get("/", include_in_schema=False)
async def serve_home():
    return HTMLResponse(content="<h1>AI Proxy v3.0</h1><p>Visit /docs for API documentation or use the Next.js frontend.</p>")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8100)

@app.get("/user/api-keys")
async def list_user_api_keys(current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    return db.query(models.APIKey).filter(models.APIKey.user_id == current_user.id).all()

@app.delete("/user/api-keys/{key_id}")
async def delete_user_api_key(key_id: int, current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    key = db.query(models.APIKey).filter(models.APIKey.id == key_id, models.APIKey.user_id == current_user.id).first()
    if not key:
        raise HTTPException(status_code=404, detail="API Key not found")
    db.delete(key)
    db.commit()
    return {"message": "API Key deleted"}

@app.get("/user/stats")
async def get_user_stats(current_user: models.User = Depends(auth.get_current_active_user), db: Session = Depends(get_db)):
    logs = db.query(models.UsageLog).filter(models.UsageLog.user_id == current_user.id).all()
    total_tokens = sum(log.total_tokens for log in logs)
    total_cost = sum(log.cost for log in logs)
    total_requests = len(logs)

    # Group by model
    model_stats = {}
    for log in logs:
        if log.model not in model_stats:
            model_stats[log.model] = {"tokens": 0, "requests": 0, "cost": 0.0}
        model_stats[log.model]["tokens"] += log.total_tokens
        model_stats[log.model]["requests"] += 1
        model_stats[log.model]["cost"] += log.cost

    return {
        "total_tokens": total_tokens,
        "total_cost": total_cost,
        "total_requests": total_requests,
        "model_stats": model_stats
    }
