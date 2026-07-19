from __future__ import annotations

import asyncio
import base64
import hashlib
import re
from urllib.parse import parse_qs, urlparse

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models
from app.config import Settings
from app.database import Base
from app.remote_mcp import create_remote_mcp
from app.security import hash_secret, verify_secret


PUBLIC_URL = "https://focus.example"
CLAUDE_CALLBACK = "https://claude.ai/api/mcp/auth_callback"


def test_password_hash_is_salted_and_verifiable():
    first = hash_secret("a-safe-test-password")
    second = hash_secret("a-safe-test-password")
    assert first != second
    assert verify_secret("a-safe-test-password", first)
    assert not verify_secret("wrong-password", first)


def test_remote_oauth_and_mcp_flow():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    settings = Settings(
        host="0.0.0.0",
        public_url=PUBLIC_URL,
        oauth_password_hash=hash_secret("a-safe-test-password"),
        oauth_allowed_redirect_uris=CLAUDE_CALLBACK,
    )
    server, remote_app, _provider = create_remote_mcp(settings, session_factory=sessions)

    verifier = "focuswith-pkce-verifier-abcdefghijklmnopqrstuvwxyz"
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "pytest", "version": "1"},
        },
    }
    mcp_headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

    async def exercise():
        transport = httpx.ASGITransport(app=remote_app)
        async with server.session_manager.run():
            async with httpx.AsyncClient(transport=transport, base_url=PUBLIC_URL, follow_redirects=False) as client:
                metadata = await client.get("/.well-known/oauth-authorization-server")
                assert metadata.status_code == 200
                assert metadata.json()["registration_endpoint"] == f"{PUBLIC_URL}/register"

                resource_metadata = await client.get("/.well-known/oauth-protected-resource/mcp")
                assert resource_metadata.status_code == 200
                assert resource_metadata.json()["resource"] == f"{PUBLIC_URL}/mcp"

                unauthorized = await client.post("/mcp", headers=mcp_headers, json=initialize)
                assert unauthorized.status_code == 401
                assert "oauth-protected-resource/mcp" in unauthorized.headers["www-authenticate"]
                head_probe = await client.head("/mcp")
                assert head_probe.status_code == 401
                assert "oauth-protected-resource/mcp" in head_probe.headers["www-authenticate"]

                evil = await client.post(
                    "/register",
                    json={
                        "redirect_uris": ["https://attacker.example/callback"],
                        "client_name": "Not Claude",
                        "grant_types": ["authorization_code", "refresh_token"],
                        "response_types": ["code"],
                        "scope": "focus",
                    },
                )
                assert evil.status_code == 400
                assert evil.json()["error"] == "invalid_redirect_uri"

                registration = await client.post(
                    "/register",
                    json={
                        "redirect_uris": [CLAUDE_CALLBACK],
                        "client_name": "Claude",
                        "token_endpoint_auth_method": "client_secret_post",
                        "grant_types": ["authorization_code", "refresh_token"],
                        "response_types": ["code"],
                        "scope": "focus",
                    },
                )
                assert registration.status_code == 201
                registered = registration.json()

                authorization = await client.get(
                    "/authorize",
                    params={
                        "client_id": registered["client_id"],
                        "redirect_uri": CLAUDE_CALLBACK,
                        "response_type": "code",
                        "code_challenge": challenge,
                        "code_challenge_method": "S256",
                        "state": "test-state",
                        "scope": "focus",
                        "resource": f"{PUBLIC_URL}/mcp",
                    },
                )
                assert authorization.status_code == 302
                assert authorization.headers["location"].startswith(f"{PUBLIC_URL}/oauth/login?")

                login_page = await client.get(
                    authorization.headers["location"],
                    headers={"Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"},
                )
                assert login_page.status_code == 200
                assert '<html lang="zh-CN">' in login_page.text
                assert "连接 Claude" in login_page.text
                assert "读取和更新你的项目、任务与专注计时器" in login_page.text
                ticket = parse_qs(urlparse(authorization.headers["location"]).query)["ticket"][0]
                csrf = re.search(r'name="csrf" value="([^"]+)"', login_page.text).group(1)  # type: ignore[union-attr]
                locale = re.search(r'name="locale" value="([^"]+)"', login_page.text).group(1)  # type: ignore[union-attr]

                login = await client.post(
                    "/oauth/login",
                    data={
                        "ticket": ticket,
                        "csrf": csrf,
                        "locale": locale,
                        "password": "a-safe-test-password",
                    },
                )
                assert login.status_code == 302
                callback = urlparse(login.headers["location"])
                callback_params = parse_qs(callback.query)
                assert f"{callback.scheme}://{callback.netloc}{callback.path}" == CLAUDE_CALLBACK
                assert callback_params["state"] == ["test-state"]

                token = await client.post(
                    "/token",
                    data={
                        "grant_type": "authorization_code",
                        "code": callback_params["code"][0],
                        "redirect_uri": CLAUDE_CALLBACK,
                        "client_id": registered["client_id"],
                        "client_secret": registered["client_secret"],
                        "code_verifier": verifier,
                        "resource": f"{PUBLIC_URL}/mcp",
                    },
                )
                assert token.status_code == 200, token.text
                issued = token.json()
                assert issued["refresh_token"]

                authorized_headers = {**mcp_headers, "Authorization": f"Bearer {issued['access_token']}"}
                initialized = await client.post("/mcp", headers=authorized_headers, json=initialize)
                assert initialized.status_code == 200, initialized.text
                assert initialized.json()["result"]["serverInfo"]["name"] == "FocusWith"
                listed = await client.post(
                    "/mcp",
                    headers=authorized_headers,
                    json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
                )
                assert listed.status_code == 200, listed.text
                tools = {item["name"]: item for item in listed.json()["result"]["tools"]}
                assert len(tools) == 7
                assert tools["get_focus_context"]["annotations"]["readOnlyHint"] is True
                assert tools["complete_task"]["annotations"]["destructiveHint"] is True

                refreshed = await client.post(
                    "/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": issued["refresh_token"],
                        "client_id": registered["client_id"],
                        "client_secret": registered["client_secret"],
                        "scope": "focus",
                        "resource": f"{PUBLIC_URL}/mcp",
                    },
                )
                assert refreshed.status_code == 200, refreshed.text
                rotated = refreshed.json()
                assert rotated["access_token"] != issued["access_token"]
                assert (await client.post("/mcp", headers=authorized_headers, json=initialize)).status_code == 401
                new_headers = {**mcp_headers, "Authorization": f"Bearer {rotated['access_token']}"}
                assert (await client.post("/mcp", headers=new_headers, json=initialize)).status_code == 200

                db = sessions()
                try:
                    stored = db.query(models.OAuthTokenRecord).all()
                    assert stored
                    assert all(item.token_hash not in {issued["access_token"], issued["refresh_token"]} for item in stored)
                finally:
                    db.close()

    try:
        asyncio.run(exercise())
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()
