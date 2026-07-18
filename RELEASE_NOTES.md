# FocusWith v0.2.0 — First public preview

FocusWith is a private-by-default, self-hosted focus system for turning goals into projects, tasks, and focused sessions. This is the first public preview of the project.

## Highlights

- Organize long-term directions, concrete projects, and actionable tasks.
- Import duration-aware Markdown plans generated in an AI chat.
- Run Pomodoro, deep-focus, free-focus, or count-up sessions with custom durations.
- Carry unfinished work forward and merge repeated sessions for the same task in daily/weekly statistics.
- Configure contextual distraction reminders from iPhone Shortcut events.
- Use the app without AI, add an optional provider, or connect a local MCP client through seven constrained tools.
- Connect Claude.ai through an OAuth-protected Streamable HTTP MCP server with DCR, S256 PKCE, audience validation, token rotation, and revocation.
- Deploy locally, with Docker Compose, or to a clean HTTPS VPS using the included Caddy workflow.
- Install the native macOS floating timer with Command Line Tools; full Xcode is not required.

## Preview notes

- FocusWith is currently designed for one owner per deployment.
- Remote MCP is disabled by default. Follow `docs/REMOTE_MCP.md`; do not expose an unauthenticated write-capable endpoint.
- Back up the SQLite database or Docker volume before upgrading.
- Review AI tool calls before allowing them to modify tasks or timer state.

See `README.md`, `README.zh-CN.md`, and `SECURITY.md` before installation or public deployment.
