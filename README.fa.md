
# 🚀 پراکسی تکمیل چت لیارا (FastAPI)

یک API ساده و سریع مبتنی بر **FastAPI** که درخواست‌های `/chat/completions` را به سرورهای لیارا فوروارد می‌کند و از fallback چندمسیره برای پایداری بالا پشتیبانی می‌کند.

---

# 🚀 Liara Chat Completion Proxy (FastAPI) 🇬🇧

**برای نسخه انگلیسی [اینجا کلیک کنید](README.md)**

---

## ✨ ویژگی‌ها | Features

- 🤖 پشتیبانی از چند مدل:
  - `openai/gpt-4o-mini`
  - `google/gemini-2.0-flash-001`
- 🖼️ پشتیبانی از ورودی‌های متنی و تصویر (text + image_url)
- 🛡️ مدیریت کامل خطاها و استثناها
- 📜 لاگ‌گیری حرفه‌ای با **Loguru**
- 🔄 پشتیبانی از fallback به چند مسیر لیارا برای اطمینان از پایداری
- ⚙️ مناسب برای محیط‌های توسعه و تولید

---

## 🚀 شروع سریع | Quick Start

### 1. نصب وابستگی‌ها | Install dependencies

```bash
pip install -r requirements.txt
````

### 2. اجرای محلی با Uvicorn | Run locally with Uvicorn

```bash
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

### 3. اجرای داکر | Or run with Docker

```bash
docker build -t liara-chat-proxy .
docker run -p 8100:8100 liara-chat-proxy
```

---

## 🗂️ ساختار فایل‌ها | File Structure

```
.
├── main.py             # برنامه FastAPI | FastAPI application
├── link.py             # لیست URLهای سرور لیارا | List of Liara server URLs
├── requirements.txt    # پکیج‌های پایتون | Python packages
├── Dockerfile          # تنظیمات داکر برای اجرا سریع | Docker setup for quick deployment
├── logs/app.log        # فایل لاگ (به صورت خودکار ساخته می‌شود) | Log file (auto-generated)
```

---

## 🧪 نمونه درخواست‌ها برای تست | Example Requests

### درخواست متنی با Curl | Text request with Curl

```bash
curl http://localhost:8100/api/v1/chat/completions \
  -H "Authorization: Bearer <LIARA_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [
      {"role": "user", "content": "معنای زندگی چیست؟"}
    ]
  }'
```

---

### درخواست ترکیبی متن و تصویر | Text + Image request

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
          {"type": "text", "text": "چه چیزی در این تصویر می‌بینی؟"},
          {"type": "image_url", "image_url": {"url": "https://example.com/image.jpg"}}
        ]
      }
    ]
  }'
```

---

## 🛠 افزودن مسیر جدید لیارا | Add new Liara endpoints

فقط مسیر جدید خود را در فایل `link.py` اضافه کنید:

```python
LIARA_API_PATHS = [
    "682bb6c5009ad8b844028900",
    "682bb8eb153623bd82f7d300",
    "مسیر_جدید_شما_اینجا"
]
```

---

## ❤️ ساخته شده با ❤️ توسط MovtiGroup و FastAPI

---

## Do you want the English version?

برای نسخه انگلیسی این README اینجا کلیک کنید: [README.md](README.md)

---
