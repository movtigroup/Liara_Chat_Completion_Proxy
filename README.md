# 🚀 Universal AI Proxy v3.2.0

Professional AI Model Proxy Gateway with support for 100+ models, multi-provider load balancing, secure user management, and detailed usage tracking.

## ✨ Key Features

- **🤖 100+ Models Support**: Powered by LiteLLM, supporting OpenAI, Anthropic, Google, Hugging Face, and more.
- **🛡️ Secure Auth System**: JWT-based authentication with SHA-256 hashed API keys.
- **📊 Advanced Analytics**: Database-side token usage and cost calculation (PostgreSQL/SQLite).
- **🌐 Proxy & Load Balancer**: HTTP/SOCKS5 proxy support with country-based routing and priority failover.
- **🕹️ Professional Dashboard**: Modern dark-themed UI (Vue.js) with 100% locally bundled assets for offline use.
- **⚡ Non-Blocking Performance**: Fully asynchronous architecture using `litellm.acompletion`.
- **🔄 DevOps Ready**: Automated tagging, GitHub Releases, and GitLab mirroring.

## 🚀 Quick Start

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Setup**:
   Create a `.env` file:
   ```env
   DATABASE_URL=sqlite:///./sql_app.db
   SECRET_KEY=your_secure_random_key
   ```

3. **Run the Server**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8100
   ```

4. **Access the Dashboard**:
   Open `http://localhost:8100` in your browser. (The first registered user becomes Admin).

## 🛠 Admin Capabilities

- **Providers**: Add multiple API keys per provider with priority levels.
- **Proxies**: Manage HTTP/SOCKS5 proxy lists for IP protection.
- **Usage**: Monitor system-wide usage, costs, and token consumption.

## 🤖 API Usage (OpenAI Compatible)

```bash
curl http://localhost:8100/api/v1/chat/completions \
  -H "Authorization: Bearer YOUR_SECURE_KEY" \
  -d '{
    "model": "openai/gpt-4o",
    "messages": [{"role": "user", "content": "Hello world"}]
  }'
```

## 📜 Development & Contributions

Please see [CONTRIBUTING.md](CONTRIBUTING.md) and [CHANGELOG.md](CHANGELOG.md) for details.

---
Developed by **MovtiGroup**
