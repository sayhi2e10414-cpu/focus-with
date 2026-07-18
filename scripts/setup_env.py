from __future__ import annotations

from pathlib import Path
import secrets


ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / ".env"
EXAMPLE = ROOT / ".env.example"


def parse_env(text: str) -> dict[str, str]:
    values = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main():
    existing = parse_env(ENV_FILE.read_text(encoding="utf-8")) if ENV_FILE.exists() else {}
    defaults = parse_env(EXAMPLE.read_text(encoding="utf-8"))
    values = {**defaults, **existing}
    values["FOCUS_API_TOKEN"] = values.get("FOCUS_API_TOKEN") or secrets.token_urlsafe(32)
    values["FOCUS_PHONE_TOKEN"] = values.get("FOCUS_PHONE_TOKEN") or secrets.token_urlsafe(32)
    lines = [
        "# Generated local configuration. Never commit this file.",
        *[f"{key}={value}" for key, value in values.items()],
        "",
    ]
    ENV_FILE.write_text("\n".join(lines), encoding="utf-8")
    ENV_FILE.chmod(0o600)
    print("Focus configuration is ready. Tokens were written to .env and were not printed.")


if __name__ == "__main__":
    main()
