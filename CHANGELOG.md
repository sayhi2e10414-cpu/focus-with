# Changelog

## Unreleased

## 0.4.2 — 2026-07-19

- Documented and narrowly suppressed Android Lint's protected-permission warning for the owner-granted usage-access permission required by the companion.

## 0.4.1 — 2026-07-19

- Fixed the GitHub Actions Android build by installing the official Android command-line tools before invoking `sdkmanager`.
- Limited automatic Android builds to `main` pushes so release tags do not create duplicate runs.

## 0.4.0 — 2026-07-19

- Added OpenAI Responses API support and expanded provider/MCP setup guidance for OpenAI, DeepSeek, GLM, Ollama, Codex, Claude, and ChatGPT.
- Added an Android companion source project with usage-event sync, offline retries, a persistent timer notification, and an optional floating timer capsule.
- Added a phone-scoped active-timer endpoint for Android without exposing the full Focus API.

## 0.3.0 — 2026-07-19

- Added a complete Simplified Chinese web interface with automatic browser-language detection and a persistent Chinese/English switch.
- Added a bilingual OAuth approval page and Chinese-interface regression tests.

## 0.2.0 — 2026-07-18

- Added OAuth-protected Streamable HTTP Remote MCP for Claude.ai.
- Added Dynamic Client Registration, S256 PKCE, callback allowlisting, audience validation, hashed OAuth artifacts, rotating refresh tokens, and revocation controls.
- Added clean-VPS Caddy deployment and an existing-reverse-proxy deployment mode.
- Added an owner authorization page, Remote MCP documentation, security policy, and end-to-end OAuth/MCP tests.
- Renamed the public project to FocusWith and selected the MIT License.

## 0.1.0 — pre-release

- Built the private-by-default Focus web app, project/task hierarchy, timers, statistics, plan import, distraction events, browser/Telegram delivery, optional AI companion, local MCP connector, iPhone Shortcut API, and macOS floating timer.
