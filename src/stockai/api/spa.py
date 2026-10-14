"""Phục vụ SPA đã build (web/dist) — không đụng /api."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles


def resolve_web_dist(cfg: dict, root: Path) -> Path | None:
    """Trả đường dẫn web/dist nếu tồn tại; không có thì None (API-only)."""
    rel = cfg.get("web_dist_dir") or "web/dist"
    p = Path(str(rel))
    if not p.is_absolute():
        p = root / p
    if p.is_dir() and (p / "index.html").is_file():
        return p
    return None


# Path không bao giờ fallback về SPA (kể cả khi docs/redoc tắt → vẫn 404)
_SPA_RESERVED_PREFIXES = (
    "api",
    "docs",
    "redoc",
    "openapi.json",
)


def mount_spa(app: FastAPI, dist: Path) -> None:
    """Mount assets tĩnh + fallback index.html cho route không phải /api."""

    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets)), name="spa_assets")

    @app.middleware("http")
    async def _spa_cache_headers(request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path or ""
        if path.startswith("/assets/"):
            # Vite hash → immutable
            response.headers.setdefault("Cache-Control", "public, max-age=31536000, immutable")
        elif path == "/" or path.endswith(".html"):
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        first = (full_path or "").split("/", 1)[0]
        if first in _SPA_RESERVED_PREFIXES or full_path in _SPA_RESERVED_PREFIXES:
            return Response(status_code=404, content="Not Found")
        candidate = (dist / full_path).resolve()
        try:
            candidate.relative_to(dist.resolve())
            under_dist = True
        except ValueError:
            under_dist = False
        if full_path and under_dist and candidate.is_file():
            media = "application/octet-stream"
            if full_path.endswith(".js"):
                media = "application/javascript"
            elif full_path.endswith(".css"):
                media = "text/css"
            elif full_path.endswith(".svg"):
                media = "image/svg+xml"
            elif full_path.endswith(".png"):
                media = "image/png"
            elif full_path.endswith(".woff2"):
                media = "font/woff2"
            elif full_path.endswith(".ttf"):
                media = "font/ttf"
            resp = FileResponse(candidate, media_type=media)
            if "assets" in full_path.replace("\\", "/").split("/"):
                resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
            return resp
        index = dist / "index.html"
        resp = FileResponse(index, media_type="text/html")
        resp.headers["Cache-Control"] = "no-cache"
        return resp
