# 🚀 Liara Chat Completion Proxy (FastAPI)

A simple and fast **FastAPI** based API that proxies `/chat/completions` requests to Liara servers, supporting multi-endpoint fallback for high availability.

---

## ✨ Features

- 🤖 Supports multiple models:
  - `openai/gpt-4o-mini`
  - `google/gemini-2.0-flash-001`
- 🖼️ Supports both text and image URL inputs (text + image_url)
- 🛡️ Comprehensive error and exception handling
- 📜 Professional logging with **Loguru**
- 🔄 Fallback support to multiple Liara endpoints to ensure reliability
- ⚙️ Suitable for both development and production environments

---

## 🚀 Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run locally with Uvicorn

```bash
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

### 3. Or run with Docker

```bash
docker build -t liara-chat-proxy .
docker run -p 8100:8100 liara-chat-proxy
```

---

## 🗂️ File Structure

```
.
├── main.py             # FastAPI application
├── link.py             # List of Liara server URLs
├── requirements.txt    # Python packages
├── Dockerfile          # Docker setup for quick deployment
├── logs/app.log        # Log file (auto-generated)
```

---

## 🧪 Example Test Requests

### Text Request with Curl

```bash
curl http://localhost:8100/api/v1/chat/completions \
  -H "Authorization: Bearer <LIARA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "What is the meaning of life?"}
    ]
  }'
```

---

### Mixed Text and Image URL Request

```bash
curl http://localhost:8100/api/v1/chat/completions \
  -H "Authorization: Bearer <LIARA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-2.0-flash-001",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "What do you see in this image?"},
          {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
        ]
      }
    ]
  }'
```

---

## 🛠 Adding New Liara Endpoints

Simply add your new endpoint path in the `link.py` file:

```python
LIARA_API_PATHS = [
    "682bb6c5009ad8b844028900",
    "682bb8eb153623bd82f7d300",
    "your_new_endpoint_here"
]
```

---

## ❤️ Built with ❤️ by MovtiGroup and FastAPI

---

If you want, I can also provide you with the **Persian-README.md** version. Just ask!  
