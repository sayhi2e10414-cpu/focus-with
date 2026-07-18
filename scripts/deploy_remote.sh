#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DOMAIN=""
PASSWORD_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="${2:-}"
      shift 2
      ;;
    --password-file)
      PASSWORD_FILE="${2:-}"
      shift 2
      ;;
    *)
      echo "Usage: ./scripts/deploy_remote.sh --domain focus.example.com [--password-file /secure/path]" >&2
      exit 2
      ;;
  esac
done

if [[ -z "$DOMAIN" ]]; then
  echo "A dedicated hostname is required. Point its DNS record at this VPS, then pass --domain." >&2
  exit 2
fi
if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  echo "Docker Engine with the Compose plugin is required. Install it from Docker's official repository first." >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
  echo "python3 and curl are required for configuration and the HTTPS health check." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "Docker is not available to this user. Run with an authorized Docker user." >&2
  exit 1
fi

cd "$ROOT"
setup_args=(--domain "$DOMAIN")
if [[ -n "$PASSWORD_FILE" ]]; then
  setup_args+=(--password-file "$PASSWORD_FILE")
fi
python3 scripts/setup_remote_env.py "${setup_args[@]}"

compose=(docker compose --env-file .env.remote -f docker-compose.remote.yml)
existing_caddy="$("${compose[@]}" ps -q caddy 2>/dev/null || true)"
ports_in_use=""
if command -v ss >/dev/null 2>&1; then
  ports_in_use="$({ ss -ltn; ss -lun; } | awk '{print $4}' | grep -E '(^|:)(80|443)$' || true)"
fi
if [[ -z "$existing_caddy" && -n "$ports_in_use" ]]; then
  echo "Port 80 or 443 is already in use. No service or network configuration was changed." >&2
  echo "Use docker-compose.remote-proxy.yml and the existing-proxy instructions in docs/REMOTE_MCP.md." >&2
  exit 1
fi

"${compose[@]}" config --quiet
"${compose[@]}" up -d --build

for _ in $(seq 1 30); do
  if curl -fsS --max-time 5 "https://$DOMAIN/api/health" >/dev/null 2>&1; then
    echo "FocusWith is online. Add https://$DOMAIN/mcp as a Claude custom connector."
    echo "The OAuth admin password was never printed by this deploy script."
    exit 0
  fi
  sleep 2
done

echo "Containers started, but HTTPS is not healthy yet. Check DNS, firewall ports 80/443, and: docker compose --env-file .env.remote -f docker-compose.remote.yml logs" >&2
exit 1
