from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Union, Literal
from functools import lru_cache
from loguru import logger
import httpx

app = FastAPI()

# لاگ فایل با سطح INFO (دیباگ فقط داخل فایل ذخیره می‌شود)
logger.add("logs/app.log", rotation="10 MB", retention="10 days", level="DEBUG", enqueue=True, backtrace=True, diagnose=True)
logger.configure(handlers=[{"sink": "logs/app.log", "level": "DEBUG"}, {"sink": "stderr", "level": "INFO"}])

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
    response = await call_next(request)
    logger.info(f"Response status: {response.status_code}")
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTP Exception: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

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

    LIARA_URL = "https://ai.liara.ir/api/v1/682bb6c5009ad8b8440289b4/chat/completions"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            payload = {
                "model": body.model,
                "messages": [m.dict() for m in body.messages],
            }
            logger.info(f"Forwarding request to Liara")
            response = await client.post(LIARA_URL, headers=get_headers(api_key), json=payload)
            response.raise_for_status()
            data = response.json()

            # تبدیل پاسخ به فرمت OpenAI SDK
            transformed_response = {
                "id": data.get("id"),
                "object": data.get("object"),
                "created": data.get("created"),
                "model": data.get("model"),
                "choices": [
                    {
                        "index": choice.get("index"),
                        "message": choice.get("message"),
                        "finish_reason": choice.get("finish_reason"),
                    }
                    for choice in data.get("choices", [])
                ],
                "usage": data.get("usage", {}),
            }

            return JSONResponse(content=transformed_response, status_code=response.status_code)

    except httpx.RequestError as e:
        logger.warning(f"Network error when connecting to Liara: {e}")
        raise HTTPException(status_code=502, detail="Cannot connect to upstream server.")
    except httpx.HTTPStatusError as e:
        logger.error(f"Upstream HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8100)
