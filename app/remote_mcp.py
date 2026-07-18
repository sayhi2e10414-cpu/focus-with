from __future__ import annotations

from urllib.parse import urlsplit

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.routes import create_auth_routes
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import AnyHttpUrl
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

from .config import Settings
from .database import SessionLocal
from .mcp_server import create_focus_mcp
from .oauth import FOCUS_SCOPE, FocusOAuthProvider


class FocusTokenVerifier:
    def __init__(self, provider: FocusOAuthProvider):
        self.provider = provider

    async def verify_token(self, token: str) -> AccessToken | None:
        return await self.provider.load_access_token(token)


def create_remote_mcp(settings: Settings, session_factory=SessionLocal):
    settings.validate_remote_mcp()
    if not settings.remote_mcp_enabled:
        raise ValueError("Remote MCP is not configured")

    provider = FocusOAuthProvider(
        public_url=settings.public_url,
        password_hash=settings.oauth_password_hash,
        allowed_redirect_uris=settings.allowed_oauth_redirect_uris,
        session_factory=session_factory,
    )
    origins = {settings.public_url}
    for redirect in settings.allowed_oauth_redirect_uris:
        parsed = urlsplit(redirect)
        if parsed.scheme and parsed.netloc:
            origins.add(f"{parsed.scheme}://{parsed.netloc}")

    issuer_url = AnyHttpUrl(settings.public_url)
    registration_options = ClientRegistrationOptions(
        enabled=True,
        valid_scopes=[FOCUS_SCOPE],
        default_scopes=[FOCUS_SCOPE],
    )
    revocation_options = RevocationOptions(enabled=True)
    server = create_focus_mcp(
        website_url=settings.public_url,
        token_verifier=FocusTokenVerifier(provider),
        auth=AuthSettings(
            issuer_url=issuer_url,
            service_documentation_url=AnyHttpUrl(settings.public_url),
            required_scopes=[FOCUS_SCOPE],
            resource_server_url=AnyHttpUrl(f"{settings.public_url}/mcp"),
        ),
        streamable_http_path="/mcp",
        stateless_http=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[settings.public_hostname],
            allowed_origins=sorted(origins),
        ),
    )

    async def oauth_login(request: Request) -> Response:
        if request.method == "POST":
            return await provider.handle_login(request)
        return await provider.login_page(request)

    authorization_routes = create_auth_routes(
        provider=provider,
        issuer_url=issuer_url,
        service_documentation_url=AnyHttpUrl(settings.public_url),
        client_registration_options=registration_options,
        revocation_options=revocation_options,
    )
    resource_app = server.streamable_http_app()
    remote_app = Starlette(
        routes=[
            *authorization_routes,
            Route("/oauth/login", endpoint=oauth_login, methods=["GET", "POST"]),
            Mount("/", app=resource_app),
        ]
    )
    return server, remote_app, provider
