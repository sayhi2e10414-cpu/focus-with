# Security policy

FocusWith stores private plans and exposes tools that can modify them. Treat its database, environment files, generated credential file, backups, and OAuth records as secrets.

## Reporting a vulnerability

Do not open a public issue containing an exploit, credential, private URL, database excerpt, or personal Focus data. Use the repository owner's private security-reporting channel. Include the affected version, deployment mode, reproduction steps with synthetic data, and the security impact.

If a credential may have been exposed:

1. Revoke Remote MCP access with `python -m app.oauth_admin revoke-all` inside the Focus container.
2. Rotate the OAuth admin password and the relevant API/provider/Telegram tokens.
3. Review server and reverse-proxy logs without publishing them.
4. Restore from a trusted backup only if data integrity is in doubt.

## Deployment baseline

- Keep local mode bound to `127.0.0.1`.
- Use the documented OAuth + HTTPS deployment for Remote MCP; never publish an unauthenticated `/mcp` endpoint.
- Apply operating-system, Docker, reverse-proxy, Python dependency, and FocusWith security updates.
- Restrict SSH, protect backups, and keep `.env`, `.env.remote`, `.focuswith-admin-password`, `data/`, and Docker volumes out of Git.
- Review AI tool actions before approval. A valid OAuth connection authorizes both reads and constrained writes through the seven documented tools.

Only the newest `0.x` release is supported before the first stable `1.0` release.
