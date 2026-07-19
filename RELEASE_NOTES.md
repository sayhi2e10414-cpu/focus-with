# FocusWith v0.3.0 — 中文版 / Bilingual UI

FocusWith now has a complete Simplified Chinese interface alongside English. Chinese browsers use it automatically, and every browser can switch languages at any time.

FocusWith 现在拥有完整的简体中文界面，同时保留 English。中文浏览器会自动显示中文，也可以随时手动切换语言。

## Highlights

- Complete Simplified Chinese coverage across focus, projects, statistics, settings, dialogs, and empty/error states.
- Automatic browser-language detection with a persistent Chinese/English switch.
- Bilingual OAuth approval and error pages for secure Remote MCP connections.
- Chinese screenshots and installation guidance in `README.zh-CN.md`.
- Regression tests that keep both locale dictionaries in sync and protect interpolation placeholders.

## Preview notes

- FocusWith is still designed for one owner per deployment.
- Remote MCP is disabled by default. Follow `docs/REMOTE_MCP.md`; do not expose an unauthenticated write-capable endpoint.
- Back up the SQLite database or Docker volume before upgrading.
- Review AI tool calls before allowing them to modify tasks or timer state.

See `README.md`, `README.zh-CN.md`, and `SECURITY.md` before installation or public deployment.
