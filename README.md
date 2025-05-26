# Liara Chat Completion Proxy (FastAPI)

یک API ساده و سریع با FastAPI که درخواست‌های `/chat/completions` را به سرورهای لیارا فوروارد می‌کند و از چند مسیر (multi-endpoint fallback) پشتیبانی می‌کند.

## ✨ ویژگی‌ها

* پشتیبانی از چند مدل: `openai/gpt-4o-mini` و `google/gemini-2.0-flash-001`
* پشتیبانی از ورودی‌های متنی و تصویری
* مدیریت خطاها و استثناها
* لاگ‌گیری حرفه‌ای با Loguru
* امکان fallback به چند مسیر لیارا
* مناسب برای توسعه و استفاده در تولید (Production)

## 🚀 اجرا

### 1. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### 2. اجرا با uvicorn

```bash
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

### 3. یا اجرای Docker

```bash
docker build -t liara-chat-proxy .
docker run -p 8100:8100 liara-chat-proxy
```

## 🛠 ساختار فایل‌ها

```
.
├── main.py             # اپلیکیشن FastAPI
├── link.py             # لیست URLهای سرور لیارا
├── requirements.txt    # پکیج‌های پایتون
├── Dockerfile          # اجرای سریع با داکر
├── logs/app.log        # فایل لاگ (به صورت خودکار ساخته می‌شود)
```

## 🧪 تست نمونه

### با Curl برای متن:

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

### با Curl برای تصویر:

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

## 📦 افزودن مسیر جدید لیارا

در فایل `link.py` فقط یک خط اضافه کن:

```python
LIARA_API_PATHS = [
    "682bb6c5009ad8b8440289b4",
    "682bb8eb153623bd82f7d38e",
    "جدیدت_را_اینجا_اضافه_کن"
]
```

---

ساخته شده با ❤️ توسط MovtiGroup و FastAPI
