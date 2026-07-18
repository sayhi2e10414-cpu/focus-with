from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .config import PROJECT_ROOT, settings
from .database import Base, engine
from .routes.api import router as api_router
from .routes.phone import router as phone_router
from .worker import stop_worker, worker_loop


VERSION = (PROJECT_ROOT / "VERSION").read_text(encoding="utf-8").strip()
WEB_ROOT = PROJECT_ROOT / "web"
settings.validate_remote_mcp()

remote_mcp_server = None
remote_mcp_app = None
if settings.remote_mcp_enabled:
    from .remote_mcp import create_remote_mcp

    remote_mcp_server, remote_mcp_app, _remote_oauth_provider = create_remote_mcp(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(engine)
    if remote_mcp_server is not None:
        async with remote_mcp_server.session_manager.run():
            task = asyncio.create_task(worker_loop())
            try:
                yield
            finally:
                await stop_worker(task)
    else:
        task = asyncio.create_task(worker_loop())
        try:
            yield
        finally:
            await stop_worker(task)


app = FastAPI(title="FocusWith", version=VERSION, lifespan=lifespan)
app.include_router(api_router)
app.include_router(phone_router)
app.mount("/assets", StaticFiles(directory=WEB_ROOT), name="assets")


@app.get("/api/meta", include_in_schema=False)
def meta():
    return {
        "version": VERSION,
        "auth_required": bool(settings.api_token),
        "local_only": settings.local_only,
        "ai_provider": settings.ai_provider,
        "ai_enabled": settings.ai_provider != "none" and bool(settings.ai_model),
        "ai_model": settings.ai_model if settings.ai_provider != "none" else "",
        "telegram_enabled": bool(settings.telegram_bot_token and settings.telegram_chat_id),
        "remote_mcp_enabled": settings.remote_mcp_enabled,
        "remote_mcp_url": f"{settings.public_url}/mcp" if settings.remote_mcp_enabled else "",
    }


@app.get("/api/health", include_in_schema=False)
def health():
    return {"ok": True, "version": VERSION}


@app.post("/api/local-session", include_in_schema=False)
def local_session(request: Request):
    client_host = request.client.host if request.client else ""
    if not settings.local_only or client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
        raise HTTPException(status_code=404, detail="Not found")
    return {"token": settings.api_token}


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(WEB_ROOT / "index.html")


if remote_mcp_app is not None:
    # The OAuth discovery, authorization, and Streamable HTTP routes live in this
    # protected sub-application. It is mounted last so Focus's normal web/API
    # routes keep their existing behavior.
    app.mount("/", remote_mcp_app, name="remote-mcp")


def run():
    import uvicorn

    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
