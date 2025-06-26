# 🚀 Liara Chat Completion Proxy (FastAPI)

![Python Version](https://img.shields.io/badge/Python-3.11%2B-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-purple)
![Build](https://img.shields.io/badge/Build-passing-brightgreen)
[![Open in GitHub](https://img.shields.io/badge/GitHub-Repo-blue?logo=github)](https://github.com/tahatehran)

**پروکسی پیشرفته برای مدل‌های هوش مصنوعی** با پشتیبانی از چندین مدل پیشرفته و قابلیت‌های حرفه‌ای شامل استریمینگ، کشینگ، مدیریت خطا و رابط وب‌سوکت.

---

## ✨ ویژگی‌های کلیدی

### 🤖 پشتیبانی از مدل‌های پیشرفته:
- `openai/gpt-4o-mini`
- `google/gemini-2.0-flash-001`
- `deepseek/deepseek-v3-0324`
- `meta/llama-3-3-70b-instruct`
- `anthropic/claude-3-7-sonnet`
- `anthropic/claude-3-5-sonnet`

### 🚀 قابلیت‌های حرفه‌ای:
- 🔄 WebSocket API برای استریمینگ واقعی
- 💾 سیستم کش پیشرفته برای پاسخ‌های سریعتر
- ⚙️ محدودیت درخواست (100 درخواست در دقیقه)
- 🖥️ رابط کاربری HTML/CSS/JS برای تست و مستندات
- 🐳 پشتیبانی کامل از Docker
- 📊 لاگ‌گیری حرفه‌ای با Loguru
- 🛡️ مدیریت خطای پیشرفته
- 🔄 پشتیبانی از چندین سرور لیارا با قابلیت Fallback

---

## 🚀 شروع سریع

### 1. نصب وابستگی‌ها
```bash
pip install -r requirements.txt
```

### 2. اجرای سرور
```bash
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

### 3. اجرا با Docker
```bash
docker build -t ai-proxy .
docker run -d -p 8100:8100 --name ai-proxy ai-proxy
```

### 4. دسترسی به رابط کاربری
باز کردن مرورگر و رفتن به آدرس:  
`http://localhost:8100`

---

## 🧪 نمونه کد کلاینت پایتون

### اتصال به API معمولی
```python
import httpx
import json

url = "http://localhost:8100/api/v1/chat/completions"
headers = {
    "Authorization": "Bearer YOUR_API_KEY",
    "Content-Type": "application/json"
}

data = {
    "model": "openai/gpt-4o-mini",
    "messages": [
        {"role": "user", "content": "سلام، چطوری؟"}
    ],
    "temperature": 0.7,
    "max_tokens": 500
}

response = httpx.post(url, headers=headers, json=data)
print(response.json())
```

### اتصال به WebSocket (استریمینگ)
```python
import websockets
import asyncio
import json

async def chat_stream():
    async with websockets.connect("ws://localhost:8100/ws/v1/chat/completions") as ws:
        # ارسال API Key
        await ws.send(json.dumps({"api_key": "YOUR_API_KEY"}))
        
        # ارسال تنظیمات چت
        config = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": "درباره هوش مصنوعی توضیح بده"}],
            "stream": True
        }
        await ws.send(json.dumps(config))
        
        # دریافت پاسخ استریم
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

## 🗂️ ساختار پروژه
```
.
├── Dockerfile
├── docker-compose.yml
├── liara.json
├── link.py
├── main.py
├── requirements.txt
├── schemas.py
├── static
│   ├── index.html
│   ├── script.js
│   └── style.css
└── utils.py
```

---

## 🧪 نمونه درخواست‌ها

### درخواست متنی
```bash
curl http://localhost:8100/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "معنی زندگی چیست؟"}
    ]
  }'
```

### درخواست ترکیبی متن و تصویر
```bash
curl http://localhost:8100/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemini-2.0-flash-001",
    "messages": [
      {
        "role": "user",
        "content": [
          {"type": "text", "text": "چه چیزی در این تصویر می‌بینی؟"},
          {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
        ]
      }
    ]
  }'
```

### درخواست WebSocket
```javascript
const ws = new WebSocket('ws://localhost:8100/ws/v1/chat/completions');

ws.onopen = () => {
  ws.send(JSON.stringify({
    api_key: "YOUR_API_KEY"
  }));
  
  ws.send(JSON.stringify({
    model: "openai/gpt-4o-mini",
    messages: [{role: "user", content: "سلام"}],
    stream: true
  }));
};

ws.onmessage = (event) => {
  console.log(JSON.parse(event.data));
};
```

---

## 🛠 پیکربندی Liara
فایل `liara.json` را با مقادیر مناسب پر کنید:
```json
{
  "app": "your-app-name",
  "port": 8100,
  "build": {
    "location": "germany",
    "base": "python"
  },
  "disks": [],
  "env": {
    "PYTHONUNBUFFERED": "1",
    "TZ": "Asia/Tehran"
  }
}
```

---

## ❤️ توسعه داده شده توسط MovtiGroup با FastAPI

---

## 📜 مجوز
```text
MIT License © 2025 MOVTIGROUP
```

[![Open in GitHub](https://img.shields.io/badge/GitHub-Repo-blue?logo=github)](https://github.com/tahatehran)
