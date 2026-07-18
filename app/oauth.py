from __future__ import annotations

import html
import json
import secrets
import time
from collections.abc import Callable
from urllib.parse import urlencode

from pydantic import AnyHttpUrl
from sqlalchemy.orm import Session
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    AuthorizeError,
    OAuthAuthorizationServerProvider,
    RefreshToken,
    RegistrationError,
    TokenError,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from . import models
from .security import opaque_hash, verify_secret


FOCUS_SCOPE = "focus"
ACCESS_TOKEN_SECONDS = 60 * 60
REFRESH_TOKEN_SECONDS = 60 * 60 * 24 * 30
LOGIN_SECONDS = 10 * 60
CODE_SECONDS = 5 * 60
MAX_LOGIN_ATTEMPTS = 5
GLOBAL_FAILURE_WINDOW_SECONDS = 15 * 60
GLOBAL_FAILURE_LIMIT = 20
MAX_REGISTERED_CLIENTS = 50


class StoredRefreshToken(RefreshToken):
    family_id: str


class FocusOAuthProvider(
    OAuthAuthorizationServerProvider[AuthorizationCode, StoredRefreshToken, AccessToken]
):
    """Persistent single-owner OAuth provider for a private FocusWith server."""

    def __init__(
        self,
        *,
        public_url: str,
        password_hash: str,
        allowed_redirect_uris: tuple[str, ...],
        session_factory: Callable[[], Session],
    ):
        self.public_url = public_url.rstrip("/")
        self.resource_url = f"{self.public_url}/mcp"
        self.password_hash = password_hash
        self.allowed_redirect_uris = frozenset(allowed_redirect_uris)
        self.session_factory = session_factory

    @staticmethod
    def _scopes(raw: str) -> list[str]:
        return list(json.loads(raw))

    def _cleanup(self, db: Session, now: int) -> None:
        db.query(models.OAuthLoginRequest).filter(
            models.OAuthLoginRequest.expires_at_epoch < now - 3600
        ).delete(synchronize_session=False)
        db.query(models.OAuthAuthorizationCodeRecord).filter(
            models.OAuthAuthorizationCodeRecord.expires_at_epoch < now - 3600
        ).delete(synchronize_session=False)
        db.query(models.OAuthTokenRecord).filter(
            models.OAuthTokenRecord.expires_at_epoch < now - REFRESH_TOKEN_SECONDS
        ).delete(synchronize_session=False)
        db.query(models.OAuthLoginFailure).filter(
            models.OAuthLoginFailure.occurred_at_epoch < now - 24 * 60 * 60
        ).delete(synchronize_session=False)

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        db = self.session_factory()
        try:
            record = db.get(models.OAuthClient, client_id)
            return OAuthClientInformationFull.model_validate_json(record.data_json) if record else None
        finally:
            db.close()

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        if not client_info.client_id:
            raise RegistrationError("invalid_client_metadata", "A client ID is required")
        redirects = {str(item) for item in (client_info.redirect_uris or [])}
        if not redirects or not redirects.issubset(self.allowed_redirect_uris):
            raise RegistrationError(
                "invalid_redirect_uri",
                "This FocusWith server only accepts explicitly allowed OAuth callback URLs",
            )

        db = self.session_factory()
        try:
            now = int(time.time())
            self._cleanup(db, now)
            existing = db.get(models.OAuthClient, client_info.client_id)
            if existing is None and db.query(models.OAuthClient).count() >= MAX_REGISTERED_CLIENTS:
                raise RegistrationError(
                    "invalid_client_metadata",
                    "The client registration limit has been reached; remove stale connectors first",
                )
            record = existing or models.OAuthClient(client_id=client_info.client_id)
            record.data_json = client_info.model_dump_json()
            record.created_at_epoch = existing.created_at_epoch if existing else now
            db.add(record)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        if not client.client_id:
            raise AuthorizeError("invalid_request", "Missing client ID")
        if params.resource and params.resource.rstrip("/") != self.resource_url:
            raise AuthorizeError("invalid_request", "The requested resource does not match this FocusWith server")

        ticket = "fw_login_" + secrets.token_urlsafe(32)
        scopes = params.scopes or [FOCUS_SCOPE]
        if set(scopes) != {FOCUS_SCOPE}:
            raise AuthorizeError("invalid_scope", "FocusWith only supports the focus scope")

        db = self.session_factory()
        try:
            now = int(time.time())
            self._cleanup(db, now)
            db.add(
                models.OAuthLoginRequest(
                    ticket_hash=opaque_hash(ticket),
                    csrf_hash=opaque_hash(secrets.token_urlsafe(32)),
                    client_id=client.client_id,
                    oauth_state=params.state,
                    redirect_uri=str(params.redirect_uri),
                    redirect_uri_explicit=params.redirect_uri_provided_explicitly,
                    code_challenge=params.code_challenge,
                    scopes_json=json.dumps(scopes),
                    resource=self.resource_url,
                    expires_at_epoch=now + LOGIN_SECONDS,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
        return f"{self.public_url}/oauth/login?{urlencode({'ticket': ticket})}"

    def _login_record(self, db: Session, ticket: str) -> models.OAuthLoginRequest | None:
        record = db.get(models.OAuthLoginRequest, opaque_hash(ticket))
        now = int(time.time())
        if not record or record.used_at_epoch or record.expires_at_epoch < now:
            return None
        return record

    def _render_login(
        self,
        *,
        ticket: str,
        csrf: str,
        client_name: str,
        error: str = "",
        status_code: int = 200,
    ) -> HTMLResponse:
        safe_ticket = html.escape(ticket, quote=True)
        safe_csrf = html.escape(csrf, quote=True)
        safe_client = html.escape(client_name or "Claude", quote=True)
        error_html = f'<p class="error" role="alert">{html.escape(error)}</p>' if error else ""
        body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Connect to FocusWith</title><style>
:root{{color-scheme:light}}*{{box-sizing:border-box}}body{{margin:0;background:#f5f5f7;color:#1d1d1f;font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text",sans-serif}}
main{{width:min(480px,calc(100% - 32px));margin:10vh auto;background:#fff;border-radius:24px;padding:36px;box-shadow:0 18px 60px rgba(0,0,0,.08)}}
.eyebrow{{color:#6e6e73;font-size:13px;font-weight:600;letter-spacing:.04em;text-transform:uppercase}}h1{{font-size:32px;line-height:1.1;margin:10px 0 12px}}p{{color:#6e6e73;line-height:1.5}}.permission{{background:#f5f5f7;border-radius:16px;padding:16px;margin:22px 0}}
label{{display:block;font-size:14px;font-weight:600;margin:20px 0 8px}}input{{width:100%;border:0;background:#f0f0f2;border-radius:12px;padding:14px 16px;font:inherit;outline:0}}input:focus{{box-shadow:0 0 0 3px rgba(0,113,227,.2)}}
button{{width:100%;margin-top:18px;border:0;border-radius:999px;background:#0071e3;color:#fff;padding:14px 18px;font:inherit;font-weight:650;cursor:pointer}}.error{{color:#b42318;background:#fff1f0;border-radius:12px;padding:12px}}small{{display:block;color:#86868b;margin-top:18px;line-height:1.45}}
</style></head><body><main><div class="eyebrow">FocusWith · private connector</div><h1>Connect {safe_client}</h1>
<p>Enter your FocusWith admin password to approve this connection.</p><div class="permission"><strong>Permission requested</strong><p>Read and update your projects, tasks, and focus timer.</p></div>
{error_html}<form method="post" action="/oauth/login" autocomplete="off"><input type="hidden" name="ticket" value="{safe_ticket}"><input type="hidden" name="csrf" value="{safe_csrf}">
<label for="password">Admin password</label><input id="password" name="password" type="password" required autofocus minlength="12"><button type="submit">Connect securely</button></form>
<small>The password is checked by your own server. Claude receives a revocable token, never your password.</small></main></body></html>"""
        response = HTMLResponse(body, status_code=status_code)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
                "Referrer-Policy": "no-referrer",
                "X-Content-Type-Options": "nosniff",
                "X-Frame-Options": "DENY",
            }
        )
        response.set_cookie(
            "focus_oauth_csrf",
            csrf,
            max_age=LOGIN_SECONDS,
            path="/oauth/login",
            secure=self.public_url.startswith("https://"),
            httponly=True,
            samesite="lax",
        )
        return response

    async def login_page(self, request: Request) -> Response:
        ticket = request.query_params.get("ticket", "")
        db = self.session_factory()
        try:
            record = self._login_record(db, ticket)
            if not record:
                return HTMLResponse("This authorization request is invalid or expired.", status_code=400)
            client = db.get(models.OAuthClient, record.client_id)
            client_info = OAuthClientInformationFull.model_validate_json(client.data_json) if client else None
            csrf = secrets.token_urlsafe(32)
            record.csrf_hash = opaque_hash(csrf)
            db.commit()
            return self._render_login(
                ticket=ticket,
                csrf=csrf,
                client_name=(client_info.client_name if client_info else None) or "Claude",
            )
        finally:
            db.close()

    async def handle_login(self, request: Request) -> Response:
        form = await request.form()
        ticket = form.get("ticket")
        csrf = form.get("csrf")
        password = form.get("password")
        cookie_csrf = request.cookies.get("focus_oauth_csrf", "")
        if not all(isinstance(item, str) and item for item in (ticket, csrf, password)):
            return HTMLResponse("Invalid authorization request.", status_code=400)

        assert isinstance(ticket, str) and isinstance(csrf, str) and isinstance(password, str)
        db = self.session_factory()
        try:
            record = self._login_record(db, ticket)
            if not record:
                return HTMLResponse("This authorization request is invalid or expired.", status_code=400)
            client_record = db.get(models.OAuthClient, record.client_id)
            client_info = (
                OAuthClientInformationFull.model_validate_json(client_record.data_json) if client_record else None
            )
            client_name = (client_info.client_name if client_info else None) or "Claude"

            csrf_ok = (
                bool(cookie_csrf)
                and secrets.compare_digest(cookie_csrf, csrf)
                and secrets.compare_digest(record.csrf_hash, opaque_hash(csrf))
            )
            if not csrf_ok:
                return HTMLResponse("Invalid authorization request.", status_code=400)

            if record.failed_attempts >= MAX_LOGIN_ATTEMPTS:
                record.used_at_epoch = int(time.time())
                db.commit()
                return HTMLResponse("Too many attempts. Start the connection again.", status_code=429)

            now = int(time.time())
            recent_failures = db.query(models.OAuthLoginFailure).filter(
                models.OAuthLoginFailure.occurred_at_epoch >= now - GLOBAL_FAILURE_WINDOW_SECONDS
            ).count()
            if recent_failures >= GLOBAL_FAILURE_LIMIT:
                return HTMLResponse("Login is temporarily locked. Try again later.", status_code=429)

            if not verify_secret(password, self.password_hash):
                record.failed_attempts += 1
                db.add(models.OAuthLoginFailure(occurred_at_epoch=now))
                new_csrf = secrets.token_urlsafe(32)
                record.csrf_hash = opaque_hash(new_csrf)
                db.commit()
                return self._render_login(
                    ticket=ticket,
                    csrf=new_csrf,
                    client_name=client_name,
                    error="That password was not correct.",
                    status_code=401,
                )

            code = "fw_code_" + secrets.token_urlsafe(32)
            db.add(
                models.OAuthAuthorizationCodeRecord(
                    code_hash=opaque_hash(code),
                    client_id=record.client_id,
                    redirect_uri=record.redirect_uri,
                    redirect_uri_explicit=record.redirect_uri_explicit,
                    code_challenge=record.code_challenge,
                    scopes_json=record.scopes_json,
                    resource=record.resource,
                    subject="owner",
                    expires_at_epoch=now + CODE_SECONDS,
                )
            )
            record.used_at_epoch = now
            db.commit()
            redirect = construct_redirect_uri(record.redirect_uri, code=code, state=record.oauth_state)
            response = RedirectResponse(redirect, status_code=302, headers={"Cache-Control": "no-store"})
            response.delete_cookie("focus_oauth_csrf", path="/oauth/login")
            return response
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        db = self.session_factory()
        try:
            record = db.get(models.OAuthAuthorizationCodeRecord, opaque_hash(authorization_code))
            now = int(time.time())
            if (
                not record
                or record.used_at_epoch
                or record.expires_at_epoch < now
                or record.client_id != client.client_id
            ):
                return None
            return AuthorizationCode(
                code=authorization_code,
                client_id=record.client_id,
                redirect_uri=record.redirect_uri,
                redirect_uri_provided_explicitly=record.redirect_uri_explicit,
                expires_at=record.expires_at_epoch,
                scopes=self._scopes(record.scopes_json),
                code_challenge=record.code_challenge,
                resource=record.resource,
                subject=record.subject,
            )
        finally:
            db.close()

    def _store_token_pair(
        self,
        db: Session,
        *,
        client_id: str,
        scopes: list[str],
        resource: str,
        subject: str,
        family_id: str,
        now: int,
    ) -> OAuthToken:
        access = "fw_at_" + secrets.token_urlsafe(32)
        refresh = "fw_rt_" + secrets.token_urlsafe(40)
        for raw, token_type, lifetime in (
            (access, "access", ACCESS_TOKEN_SECONDS),
            (refresh, "refresh", REFRESH_TOKEN_SECONDS),
        ):
            db.add(
                models.OAuthTokenRecord(
                    token_hash=opaque_hash(raw),
                    token_type=token_type,
                    client_id=client_id,
                    scopes_json=json.dumps(scopes),
                    resource=resource,
                    subject=subject,
                    family_id=family_id,
                    created_at_epoch=now,
                    expires_at_epoch=now + lifetime,
                )
            )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_SECONDS,
            refresh_token=refresh,
            scope=" ".join(scopes),
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        if not client.client_id:
            raise TokenError("invalid_client", "Missing client ID")
        db = self.session_factory()
        try:
            record = db.get(models.OAuthAuthorizationCodeRecord, opaque_hash(authorization_code.code))
            now = int(time.time())
            if not record or record.used_at_epoch or record.expires_at_epoch < now:
                raise TokenError("invalid_grant", "Authorization code is invalid or expired")
            if record.client_id != client.client_id:
                raise TokenError("invalid_grant", "Authorization code belongs to another client")
            record.used_at_epoch = now
            token = self._store_token_pair(
                db,
                client_id=record.client_id,
                scopes=self._scopes(record.scopes_json),
                resource=record.resource,
                subject=record.subject,
                family_id=secrets.token_urlsafe(24),
                now=now,
            )
            db.commit()
            return token
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def load_access_token(self, token: str) -> AccessToken | None:
        db = self.session_factory()
        try:
            record = db.get(models.OAuthTokenRecord, opaque_hash(token))
            now = int(time.time())
            if (
                not record
                or record.token_type != "access"
                or record.revoked_at_epoch
                or record.expires_at_epoch < now
                or record.resource != self.resource_url
            ):
                return None
            return AccessToken(
                token=token,
                client_id=record.client_id,
                scopes=self._scopes(record.scopes_json),
                expires_at=record.expires_at_epoch,
                resource=record.resource,
                subject=record.subject,
            )
        finally:
            db.close()

    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> StoredRefreshToken | None:
        db = self.session_factory()
        try:
            record = db.get(models.OAuthTokenRecord, opaque_hash(refresh_token))
            now = int(time.time())
            if (
                not record
                or record.token_type != "refresh"
                or record.client_id != client.client_id
                or record.revoked_at_epoch
                or record.expires_at_epoch < now
            ):
                return None
            return StoredRefreshToken(
                token=refresh_token,
                client_id=record.client_id,
                scopes=self._scopes(record.scopes_json),
                expires_at=record.expires_at_epoch,
                subject=record.subject,
                family_id=record.family_id,
            )
        finally:
            db.close()

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: StoredRefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        if not client.client_id:
            raise TokenError("invalid_client", "Missing client ID")
        db = self.session_factory()
        try:
            record = db.get(models.OAuthTokenRecord, opaque_hash(refresh_token.token))
            now = int(time.time())
            if not record or record.revoked_at_epoch or record.expires_at_epoch < now:
                raise TokenError("invalid_grant", "Refresh token is invalid or expired")
            db.query(models.OAuthTokenRecord).filter(
                models.OAuthTokenRecord.family_id == record.family_id,
                models.OAuthTokenRecord.revoked_at_epoch.is_(None),
            ).update({models.OAuthTokenRecord.revoked_at_epoch: now}, synchronize_session=False)
            token = self._store_token_pair(
                db,
                client_id=record.client_id,
                scopes=scopes,
                resource=record.resource or self.resource_url,
                subject=record.subject,
                family_id=record.family_id,
                now=now,
            )
            db.commit()
            return token
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    async def revoke_token(self, token: AccessToken | StoredRefreshToken) -> None:
        db = self.session_factory()
        try:
            record = db.get(models.OAuthTokenRecord, opaque_hash(token.token))
            if record:
                now = int(time.time())
                db.query(models.OAuthTokenRecord).filter(
                    models.OAuthTokenRecord.family_id == record.family_id,
                    models.OAuthTokenRecord.revoked_at_epoch.is_(None),
                ).update({models.OAuthTokenRecord.revoked_at_epoch: now}, synchronize_session=False)
                db.commit()
        finally:
            db.close()
