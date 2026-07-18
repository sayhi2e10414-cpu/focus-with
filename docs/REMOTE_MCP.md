# Secure Remote MCP for Claude.ai

Remote mode lets Claude.ai reach the same private projects, tasks, and timer as the FocusWith web app. It is optional: local FocusWith and the stdio MCP connector continue to work without a domain or VPS.

## What is automated

The clean-VPS deployment script creates private tokens, hashes the OAuth admin password, starts FocusWith and Caddy with Docker Compose, obtains an HTTPS certificate, and verifies the public health endpoint. Connecting the deployed server to a Claude account remains one deliberate user action because Claude must show and complete the OAuth approval flow.

You need:

- A VPS with Docker Engine and the Docker Compose plugin.
- A dedicated hostname, such as `focus.example.com`, whose A/AAAA record points to the VPS.
- Inbound TCP ports 80 and 443; UDP 443 is optional but enables HTTP/3.

On a clean VPS:

```bash
git clone YOUR_REPOSITORY_URL focus-with
cd focus-with
./scripts/deploy_remote.sh --domain focus.example.com
```

If the command runs non-interactively, it generates an admin password in `.focuswith-admin-password` with mode `0600` and prints only the file path. Retrieve it directly from the VPS through a secure terminal; do not paste it into an AI chat, issue, or Git commit. When run interactively, the script asks for a password without echoing it and stores only a salted password hash.

## Connect Claude.ai

1. Open Claude **Settings → Connectors** and choose **Add custom connector**.
2. Enter `https://focus.example.com/mcp`, using your own hostname.
3. Select **Connect**. Claude dynamically registers an OAuth client and opens the FocusWith approval page.
4. Enter the FocusWith admin password once. Claude receives a short-lived, revocable token; it never receives the password.
5. Enable the connector in the conversations where you want Claude to help with FocusWith.

No Client ID or Client Secret is needed in Claude's advanced settings because FocusWith supports Dynamic Client Registration and PKCE.

## VPS with an existing reverse proxy

The clean-VPS script stops before changing anything if port 80 or 443 is already occupied. That protects an existing Nginx, Caddy, or other site. In that case:

```bash
python3 scripts/setup_remote_env.py --domain focus.example.com
docker compose --env-file .env.remote -f docker-compose.remote-proxy.yml up -d --build
```

FocusWith then listens only on `127.0.0.1:8765`. Add a dedicated HTTPS virtual host using [deploy/nginx-focuswith.conf.example](../deploy/nginx-focuswith.conf.example), or the equivalent configuration in your existing proxy. Preserve the original `Host` header, disable proxy buffering, and allow long-lived HTTP responses.

## Revoke or rotate access

See connection counts without exposing token values:

```bash
docker compose --env-file .env.remote -f docker-compose.remote.yml exec focus python -m app.oauth_admin status
```

Immediately revoke every Claude/MCP connection:

```bash
docker compose --env-file .env.remote -f docker-compose.remote.yml exec focus python -m app.oauth_admin revoke-all
```

Rotate the admin password and recreate the Focus container:

```bash
python3 scripts/setup_remote_env.py --domain focus.example.com --rotate-password
docker compose --env-file .env.remote -f docker-compose.remote.yml up -d --force-recreate focus
```

Password rotation does not silently invalidate existing OAuth tokens; run `revoke-all` when compromise is suspected.

## Security model

- Remote MCP is disabled unless both `FOCUS_PUBLIC_URL` and `FOCUS_OAUTH_PASSWORD_HASH` are configured.
- Production public URLs must use HTTPS.
- Dynamic registration accepts only explicitly allowed callback URLs; the defaults are Claude's current `claude.ai` callback and the announced future `claude.com` callback.
- OAuth uses authorization code + S256 PKCE, one-time five-minute codes, one-hour access tokens, rotating 30-day refresh tokens, and token-family revocation.
- Admin passwords use salted scrypt hashes, with PBKDF2-SHA256 as a compatibility fallback for Python builds without scrypt. Access tokens, refresh tokens, authorization codes, login tickets, and CSRF values are stored only as SHA-256 hashes.
- Login tickets expire after ten minutes and lock after five incorrect attempts; a global failure window also limits distributed password guessing.
- The MCP endpoint validates bearer scope, resource audience, Host, and Origin before accepting a request.
- The database and `.env.remote` remain private Docker/host data. Back them up securely and never publish them.

This is a single-owner deployment. Do not share one instance among unrelated users; multi-user authorization and data isolation are intentionally outside the first release.
