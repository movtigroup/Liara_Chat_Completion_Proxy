# Changelog

All notable changes to this project will be documented in this file.

## [3.2.0] - 2026-05-31
### Added
- SHA-256 hashing for internal API keys for enhanced security.
- WebSocket resource management to handle stream interruptions.
- GitLab mirror automated workflow.
- CONTRIBUTING.md, CHANGELOG.md, and AGENTS.md.

### Fixed
- Critical async blocking issue by switching to `litellm.acompletion`.
- Performance degradation in usage reporting using database-side SQL aggregations.
- Frontend asset tracking to ensure dashboard availability.

## [3.1.0] - 2026-05-31
### Added
- Proxy List management (HTTP/SOCKS5) in the Admin dashboard.
- Country-based routing support for API and Playground.

## [3.0.0] - 2026-05-31
### Added
- Universal AI Provider support using LiteLLM (100+ models).
- JWT-based User Authentication and management.
- Professional Dark-themed Dashboard with locally bundled assets.
- Real-time token usage and cost tracking.

### Changed
- Removed Liara-specific logic and endpoints.
- Migrated to a universal load-balanced architecture.

## [2.5.0] - 2025
- Legacy Liara Proxy Version.
