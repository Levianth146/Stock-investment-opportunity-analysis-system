"""Dependency FastAPI — store, rate limiter, quote provider (singleton theo app.state)."""
from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

from fastapi import Request

from stockai.api.debate_service import DebateService
from stockai.api.quotes import QuoteProvider, SnapshotQuoteProvider
from stockai.api.ratelimit import DebateRateLimiter
from stockai.api.store import ResultStore, load_api_cfg


def init_app_state(app: Any, *, api_cfg: dict | None = None, store: ResultStore | None = None) -> None:
    cfg = api_cfg if api_cfg is not None else load_api_cfg()
    st = store if store is not None else ResultStore(cfg)
    cache_dir = Path(cfg.get("cache_dir") or st.cache_dir)
    limiter = DebateRateLimiter(
        max_per_hour=int(cfg.get("debate_live_max_per_hour") or 10),
        max_per_ip_per_hour=int(cfg.get("debate_live_max_per_ip_per_hour") or 3),
        max_per_day=int(cfg.get("debate_live_max_per_day") or 15),
        budget_path=cache_dir / "_debate_budget.json",
    )
    app.state.api_cfg = cfg
    app.state.store = st
    app.state.limiter = limiter
    app.state.debate_service = DebateService(st, limiter)
    app.state.quote_provider = SnapshotQuoteProvider(st)


def get_store(request: Request) -> ResultStore:
    return request.app.state.store


def get_debate_service(request: Request) -> DebateService:
    return request.app.state.debate_service


def get_quote_provider(request: Request) -> QuoteProvider:
    return request.app.state.quote_provider


def get_api_cfg(request: Request) -> dict:
    return request.app.state.api_cfg


def _parse_ip(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        ipaddress.ip_address(text)
    except ValueError:
        return None
    return text


def client_ip(request: Request) -> str:
    """IP client: mặc định chỉ ``request.client.host``; proxy headers khi trust_proxy_headers."""
    host = "unknown"
    if request.client and request.client.host:
        host = request.client.host

    cfg = getattr(request.app.state, "api_cfg", None) or {}
    if not bool(cfg.get("trust_proxy_headers", False)):
        return host

    header_name = str(cfg.get("proxy_ip_header") or "CF-Connecting-IP").strip() or "CF-Connecting-IP"
    preferred = _parse_ip(request.headers.get(header_name))
    if preferred:
        return preferred

    xff = request.headers.get("x-forwarded-for")
    if xff:
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            last = _parse_ip(parts[-1])
            if last:
                return last

    return host
