from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path
import re
import secrets
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.security import hash_secret  # noqa: E402


REMOTE_ENV = ROOT / ".env.remote"
EXAMPLE = ROOT / ".env.example"
GENERATED_PASSWORD = ROOT / ".focuswith-admin-password"
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def choose_password(password_file: str | None) -> tuple[str, bool]:
    if password_file:
        path = Path(password_file).expanduser()
        if path.stat().st_mode & 0o077:
            raise SystemExit("The password file must not be readable or writable by group/other users (use chmod 600)")
        value = path.read_text(encoding="utf-8").strip()
        return value, False
    from_environment = os.getenv("FOCUSWITH_ADMIN_PASSWORD", "")
    if from_environment:
        return from_environment, False
    if sys.stdin.isatty():
        first = getpass.getpass("Choose a FocusWith admin password (12+ characters): ")
        second = getpass.getpass("Repeat the admin password: ")
        if first != second:
            raise SystemExit("Passwords did not match")
        return first, False
    return secrets.token_urlsafe(24), True


def main() -> None:
    parser = argparse.ArgumentParser(description="Create the private configuration for a remote FocusWith server")
    parser.add_argument("--domain", required=True, help="Dedicated public hostname, for example focus.example.com")
    parser.add_argument("--password-file", help="Read the admin password from a mode-600 file")
    parser.add_argument("--rotate-password", action="store_true", help="Replace an existing OAuth password hash")
    args = parser.parse_args()

    domain = args.domain.strip().lower().rstrip(".")
    if not DOMAIN_RE.fullmatch(domain):
        raise SystemExit("--domain must be a hostname such as focus.example.com")

    defaults = parse_env(EXAMPLE.read_text(encoding="utf-8"))
    existing = parse_env(REMOTE_ENV.read_text(encoding="utf-8")) if REMOTE_ENV.exists() else {}
    values = {**defaults, **existing}
    values.update(
        {
            "FOCUS_DOMAIN": domain,
            "FOCUS_HOST": "0.0.0.0",
            "FOCUS_PORT": "8765",
            "FOCUS_DATA_DIR": "/app/data",
            "FOCUS_PUBLIC_URL": f"https://{domain}",
            "FOCUS_OAUTH_ALLOWED_REDIRECT_URIS": "https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback",
        }
    )
    values["FOCUS_API_TOKEN"] = values.get("FOCUS_API_TOKEN") or secrets.token_urlsafe(32)
    values["FOCUS_PHONE_TOKEN"] = values.get("FOCUS_PHONE_TOKEN") or secrets.token_urlsafe(32)

    generated = False
    if args.rotate_password or not values.get("FOCUS_OAUTH_PASSWORD_HASH"):
        password, generated = choose_password(args.password_file)
        values["FOCUS_OAUTH_PASSWORD_HASH"] = hash_secret(password)
        if generated:
            GENERATED_PASSWORD.write_text(password + "\n", encoding="utf-8")
            GENERATED_PASSWORD.chmod(0o600)
        elif GENERATED_PASSWORD.exists():
            GENERATED_PASSWORD.unlink()

    ordered_keys = ["FOCUS_DOMAIN", *[key for key in defaults if key != "FOCUS_DOMAIN"]]
    extra_keys = [key for key in values if key not in ordered_keys]
    lines = [
        "# Generated remote configuration. Never commit or paste this file into chat.",
        *[f"{key}={values.get(key, '')}" for key in [*ordered_keys, *extra_keys]],
        "",
    ]
    REMOTE_ENV.write_text("\n".join(lines), encoding="utf-8")
    REMOTE_ENV.chmod(0o600)
    print(f"Remote configuration is ready for https://{domain}.")
    if generated:
        print(f"A generated admin password was saved to {GENERATED_PASSWORD}; it was not printed.")
    else:
        print("The admin password was hashed with scrypt and was not written to the environment file.")


if __name__ == "__main__":
    main()
