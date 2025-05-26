
# 🚀 Liara Chat Completion Proxy (FastAPI)

یک API ساده و سریع با **FastAPI** که درخواست‌های `/chat/completions` را به سرورهای **لیارا** فوروارد می‌کند و از چند مسیر (multi-endpoint fallback) پشتیبانی می‌کند.

---

## ✨ ویژگی‌ها

- 🤖 پشتیبانی از چند مدل:
  - `openai/gpt-4o-mini`
  - `google/gemini-2.0-flash-001`
- 🖼️ پشتیبانی از ورودی‌های متنی و تصویری (متن + URL تصویر)
- 🛡️ مدیریت خطاها و استثناها به صورت کامل و حرفه‌ای
- 📜 لاگ‌گیری حرفه‌ای با **Loguru**
- 🔄 امکان fallback به چند مسیر لیارا برای اطمینان از پاسخگویی
- ⚙️ مناسب برای توسعه و استفاده در محیط تولید (Production)

---

## 🚀 راه‌اندازی و اجرا

### 1. نصب وابستگی‌ها

```bash
pip install -r requirements.txt
```

### 2. اجرای لوکال با Uvicorn

```bash
uvicorn main:app --host 0.0.0.0 --port 8100 --reload
```

### 3. یا اجرای در داکر

```bash
docker build -t liara-chat-proxy .
docker run -p 8100:8100 liara-chat-proxy
```

---

## 🗂️ ساختار فایل‌ها

```
.
├── main.py             # اپلیکیشن FastAPI
├── link.py             # لیست URLهای سرور لیارا
├── requirements.txt    # پکیج‌های پایتون
├── Dockerfile          # اجرای سریع با داکر
├── logs/app.log        # فایل لاگ (به صورت خودکار ساخته می‌شود)
```

---

## 🧪 نمونه تست درخواست‌ها

### درخواست متنی (Text) با Curl

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

### درخواست ترکیبی متن و تصویر (Text + Image URL)

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

## 🛠 افزودن مسیر جدید لیارا

کافیست در فایل `link.py` خط مربوط به مسیر جدید را اضافه کنید:

```python
LIARA_API_PATHS = [
    "682bb6c5009ad8b844028900",
    "682bb8eb153623bd82f7d300",
    "مسیر_جدید_خودت_اینجا_اضافه_کن"
]
```

---

## ❤️ ساخته شده با ❤️ توسط MovtiGroup و FastAPI

---
