# Install with a coding agent

Give the repository URL or folder to a coding agent and use this prompt:

> Install FocusWith for me. Read AGENTS.md first, keep it private on localhost, run its installer and doctor checks, and do not print or commit any generated tokens. Ask me only whether I want an optional AI provider, Telegram, iPhone shortcuts, or the macOS floating timer.

The deterministic path is:

```bash
./scripts/install.sh
./scripts/focus start
./scripts/focus doctor
```

The web app opens at `http://127.0.0.1:8765`. A localhost browser connects automatically; a remotely hosted browser must be given the API token securely.

Optional credentials go only in `.env`. The agent should edit that ignored file without copying secrets into chat, source code, logs, or a Git commit, then restart Focus.

For the native timer on macOS:

```bash
./macos/FocusFloat/install.sh
```

The app stores its token in Keychain. Apple Command Line Tools are sufficient; full Xcode is not required.

## Remote Claude.ai installation

Use remote mode only when the user explicitly asks for it and supplies a VPS plus a hostname they control. The agent must read [REMOTE_MCP.md](REMOTE_MCP.md), verify DNS and existing web services, and never overwrite an existing reverse proxy. On a clean Docker VPS, the deterministic command is:

```bash
./scripts/deploy_remote.sh --domain focus.example.com
```

If ports 80/443 are occupied, use the existing-proxy path in the guide. Never put the admin password, `.env.remote`, generated credential file, API tokens, database, or OAuth records into chat or Git. The agent may report the credential file path, not its contents.
