# 🚀 Liara Chat Completion Proxy (FastAPI)

A simple and fast **FastAPI** based proxy API forwarding `/chat/completions` requests to Liara servers with multi-endpoint fallback support for high availability.

---

# 🚀 پراکسی تکمیل چت لیارا (FastAPI) 🇮🇷

**برای نسخه فارسی [اینجا کلیک کنید](README.fa.md)**

---

## ✨ Features | ویژگی‌ها

- 🤖 Support for multiple models:
  - `openai/gpt-4o-mini`
  - `google/gemini-2.0-flash-001`
- 🖼️ Support for text and image inputs (text + image_url)
- 🛡️ Robust error and exception handling
- 📜 Professional logging with **Loguru**
- 🔄 Multi-endpoint fallback to Liara servers for high availability
- ⚙️ Suitable for development and production environments

---

## 🚀 Quick Start | شروع سریع

### 1. Install dependencies | نصب وابستگی‌ها

```bash
pip install -r requirements.txt
````

### 2. Run locally with Uvicorn | اجرای محلی با Uvicorn

```bash
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

### 3. Or run with Docker | یا اجرای داکر

```bash
docker build -t liara-chat-proxy .
docker run -p 8100:8100 liara-chat-proxy
```

---

## 🗂️ File Structure | ساختار فایل‌ها

```
.
├── main.py             # FastAPI application | برنامه FastAPI
├── link.py             # List of Liara server URLs | لیست URLهای سرور لیارا
├── requirements.txt    # Python packages | پکیج‌های پایتون
├── Dockerfile          # Docker setup for quick deployment | تنظیمات داکر برای اجرا سریع
├── logs/app.log        # Log file (auto-generated) | فایل لاگ (به صورت خودکار ساخته می‌شود)
```

---

## 🧪 Example Requests | نمونه درخواست‌ها برای تست

### Text request with Curl | درخواست متنی با Curl

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

### Text + Image request | درخواست ترکیبی متن و تصویر

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

## 🛠 Add new Liara endpoints | افزودن مسیر جدید لیارا

Simply add your new endpoint to `link.py`:

```python
LIARA_API_PATHS = [
    "682bb6c5009ad8b844028900",
    "682bb8eb153623bd82f7d300",
    "your_new_endpoint_here"
]
```

---

## ❤️ Built with ❤️ by MovtiGroup & FastAPI

---

## نسخه فارسی این README را می‌خواهید؟

If you want the **Persian (Farsi)** version of this README, check out: [README.fa.md](README.fa.md)



