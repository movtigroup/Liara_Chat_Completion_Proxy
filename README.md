# 🚀 Liara Chat Completion Proxy (FastAPI)

![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-purple)
[![Open in GitHub](https://img.shields.io/badge/GitHub-Repo-blue?logo=github)](https://github.com/tahatehran)

**Advanced proxy for AI models** with support for multiple advanced models and professional features including streaming, caching, error management, and WebSocket interface.

---

## ✨ Key Features

### 🤖 Support for Advanced Models:
- `openai/gpt-4o-mini`
- `google/gemini-2.0-flash-001`
- `deepseek/deepseek-v3-0324`
- `meta/llama-3-3-70b-instruct`
- `anthropic/claude-3-7-sonnet`
- `anthropic/claude-3-5-sonnet`

### 🚀 Professional Features:
- 🔄 WebSocket API for real-time streaming
- 💾 Advanced caching system for faster responses
- ⚙️ Rate limiting (default: 100 requests per minute for v1, 1000 for v2 - now dynamic)
- 🖥️ Modern HTML/CSS/JS user interface (Tailwind CSS, jQuery) with an interactive WebSocket tester
- 📄 User-friendly custom HTML error pages (403, 404, 500) for browser clients
- 🐳 Full Docker support
- 📊 Professional logging with Loguru (outputs to stderr)
- 🛡️ Advanced error management with content negotiation (JSON for API clients, HTML for browsers)
- 🔄 Support for multiple Liara servers with Fallback capability

---

## API Versioning and Access Tiers

This API offers two access tiers:

*   **v1 (Customers)**: For general use and individual developers.
    *   API Paths: `/api/v1/...` and `/ws/v1/...`
    *   API Keys with prefix `cust-valid-` or the legacy key `test-api-key`.
    *   Rate Limit: Default 100 requests per minute (now dynamically adjusted).
*   **v2 (Businesses)**: For business users requiring higher capacity and potentially more advanced features in the future.
    *   API Paths: `/api/v2/...` and `/ws/v2/...`
    *   API Keys with prefix `biz-valid-`.
    *   Rate Limit: Default 1000 requests per minute (now dynamically adjusted).

Currently, the core functionality of both v1 and v2 versions is the same, but this structure allows for the development of dedicated features for each tier in the future.

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Server
```bash
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

### 3. Run with Docker

#### A) Using Docker Hub Image (Recommended)
The Docker image for this project is automatically published to Docker Hub. You can run the latest version with the following command:

```bash
docker run -d -p 8100:8100 \
  -e UVICORN_WORKERS=2 \
  -e TZ=Asia/Tehran \
  --name ai-proxy \
  tahatehrani/liara_chat_completion_proxy:latest
```
-   `-e UVICORN_WORKERS=2`: Sets the number of Uvicorn worker processes. Adjust according to your server's CPU (e.g., `number of cores * 2 + 1`).
-   `-e TZ=Asia/Tehran`: Sets the timezone for logs.

#### B) Local Build
If you want to build the image yourself:
```bash
docker build -t my-ai-proxy .
docker run -d -p 8100:8100 \
  -e UVICORN_WORKERS=2 \
  -e TZ=Asia/Tehran \
  --name my-ai-proxy \
  my-ai-proxy
```

#### C) Using Docker Compose
For easy execution with default settings (includes `UVICORN_WORKERS=2` and `restart: unless-stopped` by default in the provided `docker-compose.yml`):
```bash
docker-compose up -d
```
To stop:
```bash
docker-compose down
```

### 4. Access User Interface
Open your browser and go to:
`http://localhost:8100`

---

## 🧪 Python Client Code Samples

### Connecting to the Standard API
```python
import httpx
import json

url = "http://localhost:8100/api/v1/chat/completions" # v1 endpoint
headers = {
    "Authorization": "Bearer test-api-key", # Example v1 customer key
    "Content-Type": "application/json"
}

data = {
    "model": "openai/gpt-4o-mini",
    "messages": [
        {"role": "user", "content": "Hello, how are you?"}
    ],
    "temperature": 0.7,
    "max_tokens": 500
}

response = httpx.post(url, headers=headers, json=data)
print(response.json())
```

### Connecting to WebSocket (Streaming)
```python
import websockets
import asyncio
import json

async def chat_stream():
    async with websockets.connect("ws://localhost:8100/ws/v1/chat/completions") as ws: # v1 endpoint
        # Send API Key
        await ws.send(json.dumps({"api_key": "Bearer test-api-key"})) # Example v1 customer key, sent in Bearer format
        
        # Send chat configuration
        config = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "Explain artificial intelligence."}],
            "stream": True
        }
        await ws.send(json.dumps(config))
        
        # Receive stream response
        async for message in ws:
            data = json.loads(message)
            if "error" in data:
                print(f"Error: {data['error']}")
                break
            if "choices" in data:
                content = data["choices"][0]["delta"].get("content", "")
                print(content, end="", flush=True)

asyncio.run(chat_stream())
```

---

## 🗂️ Project Structure
```
.
├── .github/
│   └── workflows/
│       └── liara.yaml  # For CI/CD deployment to Liara
├── .env                # For local environment variables (see .env.example if provided)
├── Dockerfile
├── docker-compose.yml
├── errors.py
├── link.py
├── main.py
├── pytest.ini
├── requirements.txt
├── schemas.py
├── static/
│   ├── 403.html          # Custom 403 Forbidden page
│   ├── 404.html          # Custom 404 Not Found page
│   ├── 500.html          # Custom 500 Internal Server Error page
│   ├── index.html
│   ├── script.js
├── tests/
└── utils.py
```

---

## 🧪 Sample Requests

### Text Request
```bash
curl http://localhost:8100/api/v1/chat/completions \
  -H "Authorization: Bearer test-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "What is the meaning of life?"}
    ]
  }'
```

### Combined Text and Image Request
```bash
curl http://localhost:8100/api/v1/chat/completions \
  -H "Authorization: Bearer test-api-key" \
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

### WebSocket Request (JavaScript Example)
```javascript
const ws = new WebSocket('ws://localhost:8100/ws/v1/chat/completions');

ws.onopen = () => {
  ws.send(JSON.stringify({
    api_key: "Bearer test-api-key" // Example v1 customer key, sent in Bearer format
  }));
  
  ws.send(JSON.stringify({
    model: "openai/gpt-4o-mini",
    messages: [{role: "user", content: "Hello"}],
    stream: true
  }));
};

ws.onmessage = (event) => {
  console.log(JSON.parse(event.data));
};
```

---

## 🛠 Deployment (Liara)

This application (version 2.1+, based on Python 3.11) is designed to be deployed on Liara. Deployment is typically handled via the GitHub Actions workflow defined in `.github/workflows/liara.yaml`, which automates the process upon pushes to the `main` branch. The necessary configurations (app name, port, API token) are managed within the workflow file and GitHub secrets.

**Resource Recommendations for Liara:**
For comfortable and stable operation, it is recommended to choose a Liara plan that provides at least:
-   **CPU:** 0.5 cores
-   **RAM:** 500 MB

While the application might run on lower resources (e.g., minimum 125MB RAM for very light use, as per recent optimizations), 500MB RAM provides a better buffer for handling concurrent requests, caching, and background tasks performed by the Uvicorn workers and the FastAPI application. Always monitor your application's resource usage on Liara and adjust your plan as needed.

---

## ❤️ Developed by MovtiGroup with FastAPI

---

## 📜 License
```text
MIT License © 2025 MOVTIGROUP
```

[![Open in GitHub](https://img.shields.io/badge/GitHub-Repo-blue?logo=github)](https://github.com/tahatehran)
