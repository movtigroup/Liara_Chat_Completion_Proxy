from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Union, Literal
from functools import lru_cache
from loguru import logger
import httpx
import os

from link import LIARA_BASE_URLS

app = FastAPI()

# Setup logger
logger.add("logs/app.log", rotation="1 MB", retention="10 days", level="DEBUG", enqueue=True, backtrace=True, diagnose=True)

# Schemas
class TextContent(BaseModel):
    type: Literal["text"] = "text"
    text: str

class ImageURL(BaseModel):
    type: Literal["image_url"] = "image_url"
    image_url: dict

class Message(BaseModel):
    role: Literal["user", "system", "assistant"]
    content: Union[str, List[Union[TextContent, ImageURL]]]

class CompletionRequest(BaseModel):
    model: Literal["openai/gpt-4o-mini", "google/gemini-2.0-flash-001"]
    messages: List[Message]

@lru_cache()
def get_headers(api_key: str):
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    try:
        response = await call_next(request)
    except Exception as e:
        logger.exception("Unhandled exception in middleware")
        raise
    logger.info(f"Response status: {response.status_code}")
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unhandled error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})

@app.post("/api/v1/chat/completions")
async def proxy_chat(request: Request, body: CompletionRequest):
    api_key = request.headers.get("Authorization")
    if not api_key or not api_key.startswith("Bearer "):
        logger.warning("Missing or invalid API key.")
        raise HTTPException(status_code=401, detail="API Key is required in Authorization header.")

    api_key = api_key.replace("Bearer ", "").strip()

    for url in LIARA_BASE_URLS:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    f"{url}/chat/completions",
                    headers=get_headers(api_key),
                    json=body.dict()
                )
                logger.info(f"Forwarded to Liara URL {url} - Status: {response.status_code}")
                return JSONResponse(content=response.json(), status_code=response.status_code)
        except httpx.RequestError as e:
            logger.warning(f"Connection failed to {url}: {e}")
            continue
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Status error from {url}: {e}")
            raise HTTPException(status_code=e.response.status_code, detail=e.response.text)

    raise HTTPException(status_code=502, detail="All upstream servers failed.")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8100, reload=True)
