# FocusWith v0.5.0 — Public Android companion & more AI providers

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

- v0.5.0 is the first publicly downloadable, signed Android build. GitHub Releases also includes its SHA-256 checksum.
- Android usage access, notifications, and the optional overlay permission must be granted explicitly by the device owner.
- Some Android vendors may require removing battery restrictions for reliable background monitoring.
- Android may ask users to allow their browser or file manager to install apps from GitHub because the APK is distributed outside Google Play.

## Upgrade notes

- FocusWith is still designed for one owner per deployment.
- Existing web data and APIs remain backward compatible.
- Remote MCP and AI providers remain disabled until configured.
- Back up the SQLite database or Docker volume before upgrading a production deployment.

See `README.md`, `README.zh-CN.md`, `docs/ANDROID.md`, `docs/AI_PROVIDERS.md`, and `SECURITY.md` before installation or public deployment.
