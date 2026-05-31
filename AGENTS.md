# 🤖 Instructions for AI Agents

Welcome, Jules or other agents. This project is a professional AI Proxy Gateway.

## Project Structure
- `main.py`: FastAPI application and routing.
- `models.py`: SQLAlchemy database models.
- `auth.py`: JWT authentication and security.
- `provider_manager.py`: AI provider selection and load balancing.
- `proxy_manager.py`: Proxy rotation and formatting.
- `static/index.html`: Vue.js Dashboard UI.
- `static/lib/`: Bundled JS/CSS assets (Vue, Tailwind, Axios).

## Coding Conventions
1. **Async Everywhere**: Use `acompletion` and `async for` for all AI model calls to avoid blocking the event loop.
2. **Security First**: Never store API keys in plain text. Hash internal user keys with SHA-256.
3. **Database Performance**: Use SQLAlchemy `func` for aggregations (Sum, Count) instead of Python loops.
4. **Offline Assets**: Do not use external CDNs in the frontend. All assets must be in `static/lib/`.

## Testing
Run tests using `pytest`. Always add tests for new features.

## Deployment
The project is containerized using `Dockerfile` and `docker-compose.yml`.
