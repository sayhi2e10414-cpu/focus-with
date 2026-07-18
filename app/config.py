from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _path_from_env(name: str, default: Path) -> Path:
    raw = (os.getenv(name) or "").strip()
    path = Path(raw).expanduser() if raw else default
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


@dataclass(frozen=True)
class Settings:
    host: str = (os.getenv("FOCUS_HOST") or "127.0.0.1").strip()
    port: int = int(os.getenv("FOCUS_PORT") or "8765")
    timezone_name: str = (os.getenv("FOCUS_TIMEZONE") or "Asia/Shanghai").strip()
    data_dir: Path = _path_from_env("FOCUS_DATA_DIR", PROJECT_ROOT / "data")
    api_token: str = (os.getenv("FOCUS_API_TOKEN") or "").strip()
    phone_token: str = (os.getenv("FOCUS_PHONE_TOKEN") or "").strip()
    ai_provider: str = (os.getenv("FOCUS_AI_PROVIDER") or "none").strip().lower()
    ai_api_key: str = (os.getenv("FOCUS_AI_API_KEY") or "").strip()
    ai_model: str = (os.getenv("FOCUS_AI_MODEL") or "").strip()
    ai_base_url: str = (os.getenv("FOCUS_AI_BASE_URL") or "").strip().rstrip("/")
    telegram_bot_token: str = (os.getenv("FOCUS_TELEGRAM_BOT_TOKEN") or "").strip()
    telegram_chat_id: str = (os.getenv("FOCUS_TELEGRAM_CHAT_ID") or "").strip()
    public_url: str = (os.getenv("FOCUS_PUBLIC_URL") or "").strip().rstrip("/")
    oauth_password_hash: str = (os.getenv("FOCUS_OAUTH_PASSWORD_HASH") or "").strip()
    oauth_allowed_redirect_uris: str = (
        os.getenv("FOCUS_OAUTH_ALLOWED_REDIRECT_URIS")
        or "https://claude.ai/api/mcp/auth_callback,https://claude.com/api/mcp/auth_callback"
    ).strip()

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'focus.db'}"

    @property
    def local_only(self) -> bool:
        return self.host in {"127.0.0.1", "localhost", "::1"}

    @property
    def remote_mcp_enabled(self) -> bool:
        return bool(self.public_url and self.oauth_password_hash)

    @property
    def allowed_oauth_redirect_uris(self) -> tuple[str, ...]:
        return tuple(item.strip() for item in self.oauth_allowed_redirect_uris.split(",") if item.strip())

    @property
    def public_hostname(self) -> str:
        return urlsplit(self.public_url).netloc

    def validate_remote_mcp(self) -> None:
        if bool(self.public_url) != bool(self.oauth_password_hash):
            raise ValueError("FOCUS_PUBLIC_URL and FOCUS_OAUTH_PASSWORD_HASH must be configured together")
        if not self.public_url:
            return
        parsed = urlsplit(self.public_url)
        if parsed.scheme != "https" and parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("Remote MCP requires an HTTPS FOCUS_PUBLIC_URL")
        if not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError("FOCUS_PUBLIC_URL must be an origin such as https://focus.example.com")
        if not self.allowed_oauth_redirect_uris:
            raise ValueError("At least one OAuth redirect URI must be allowed")


settings = Settings()
