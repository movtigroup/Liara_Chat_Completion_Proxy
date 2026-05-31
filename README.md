# 🚀 Universal AI Proxy v3.0

Professional AI Model Proxy with support for 100+ models, multi-provider load balancing, user management, and detailed usage tracking.

## ✨ Key Features

- **🤖 100+ Models Support**: Powered by LiteLLM, supporting OpenAI, Anthropic, Google, Hugging Face, and more.
- **🛡️ Authentication & Authorization**: JWT-based user system with registration and login.
- **🔑 API Key Management**: Users can generate and manage multiple internal API keys.
- **📊 Usage Tracking**: Real-time token usage and cost calculation for every request.
- **🌐 Load Balancer**: Distribute requests across multiple provider keys with priority routing.
- **🕹️ Professional Dashboard**: Built-in UI for monitoring usage, testing models, and managing providers.
- **🔌 Offline Capability**: All frontend assets are bundled locally; no external CDN dependencies.
- **🗄️ Flexible Database**: Supports PostgreSQL for production and SQLite for local development.

## 🚀 Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Environment Variables**:
   Create a `.env` file:
   ```env
   DATABASE_URL=sqlite:///./sql_app.db
   SECRET_KEY=your_random_secret_key
   ```

3. **Run the Server**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8100
   ```

4. **Access the Dashboard**:
   Open `http://localhost:8100` in your browser.

## 🛠 Admin Setup

1. The first user to register becomes the **Admin**.
2. Navigate to **Providers** in the dashboard to add your AI API keys (OpenAI, etc.).
3. Set priority and optional base URLs for custom endpoints (like New-API).

## 🧪 API Usage

Standard OpenAI-compatible endpoint:
```bash
curl http://localhost:8100/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_INTERNAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "openai/gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---
Developed by MovtiGroup
