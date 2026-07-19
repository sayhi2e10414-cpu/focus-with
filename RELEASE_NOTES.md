# FocusWith v0.4.2 — Android companion & more AI providers

FocusWith can now stay with you on Android and connect to more AI providers without giving a phone or model unrestricted access to your server.

FocusWith 现在也可以在 Android 上陪你专注，并支持更多 AI 服务，同时继续保持最小权限和私有优先。

## Highlights

- Added an Android companion with usage-event monitoring, offline retries, and protection against screen-off false positives.
- Added a persistent timer notification and an optional draggable system overlay capsule.
- Added a phone-scoped timer endpoint so the Android companion never needs the full Focus API token.
- Added OpenAI Responses API support alongside Anthropic and OpenAI-compatible providers such as DeepSeek, GLM, and Ollama.
- Added setup guidance for Codex, Claude, ChatGPT Remote MCP, and local-model workflows.
- Kept monitored Android packages editable and stored the phone token with Android Keystore encryption.

## Android preview notes

- v0.4.2 fixes the GitHub Actions Android toolchain and documents the owner-granted usage-access permission for a clean Lint build.
- Android usage access, notifications, and the optional overlay permission must be granted explicitly by the device owner.
- Some Android vendors may require removing battery restrictions for reliable background monitoring.
- The first GitHub build produces a debug APK for testing. A signed release APK will follow before broad public distribution.

## Upgrade notes

- FocusWith is still designed for one owner per deployment.
- Existing web data and APIs remain backward compatible.
- Remote MCP and AI providers remain disabled until configured.
- Back up the SQLite database or Docker volume before upgrading a production deployment.

See `README.md`, `README.zh-CN.md`, `docs/ANDROID.md`, `docs/AI_PROVIDERS.md`, and `SECURITY.md` before installation or public deployment.
