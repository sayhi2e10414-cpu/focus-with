# FocusWith — agent installation contract

This repository is designed to be installed by a coding agent on behalf of a user.

## Safe installation flow

1. Read `README.md` and this file completely.
2. Never place credentials in source files, Git commits, command output, or chat messages.
3. Run `./scripts/install.sh`; it creates `.env` with random scoped tokens when missing.
4. Ask the user only for optional provider credentials they explicitly want to enable.
5. Run `./scripts/focus doctor` and report the local URL and enabled integrations.
6. Default to `127.0.0.1`. Do not expose Focus publicly without authentication and explicit user approval.

## Remote deployment contract

- Remote deployment requires an explicit user request, a user-controlled VPS, and a dedicated HTTPS hostname.
- Read `docs/REMOTE_MCP.md` before changing network state.
- Run `scripts/deploy_remote.sh` only on a clean VPS where ports 80/443 are available. If they are occupied, stop and use the documented existing-proxy mode; never replace or reconfigure an unrelated site automatically.
- Never expose `/mcp` without the built-in OAuth layer. Never weaken callback allowlisting, PKCE, audience validation, or TLS to make a client connect.
- Never print or transmit `.env.remote`, `.focuswith-admin-password`, API tokens, provider keys, OAuth client secrets, token records, or database contents.
- Connecting Claude.ai requires the owner to complete the browser approval step. Do not attempt to bypass it.

## Optional configuration

- Core Focus works without any AI provider.
- AI keys belong only in `.env` or the operating system keychain.
- Telegram and Claude connectors are optional adapters, not core dependencies.
- Phone tracking uses `FOCUS_PHONE_TOKEN`, never the full API token.
- If installing FocusFloat, put the generated API token into macOS Keychain without printing it or embedding it in the app bundle.

## Development

- Keep runtime data under `data/`; it is intentionally ignored by Git.
- Add migrations for schema changes after the initial public release.
- Run the full test suite and `./scripts/focus doctor` before publishing a release.
