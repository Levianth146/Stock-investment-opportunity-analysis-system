"""Dependency FastAPI — store, rate limiter, quote provider (singleton theo app.state)."""
from __future__ import annotations

import ipaddress
from pathlib import Path
from typing import Any

from fastapi import Request

from stockai.api.debate_jobs import DebateJobManager
from stockai.api.debate_service import DebateService
from stockai.api.quotes import HubQuoteProvider, QuoteProvider, SnapshotQuoteProvider
from stockai.api.ratelimit import ConnectionLimiter, DebateRateLimiter
from stockai.api.realtime import FakeStream, RealtimeHub
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
    debate_svc = DebateService(st, limiter)
    max_workers = int(cfg.get("debate_job_max_workers") or 2)

    rt_cfg = cfg.get("realtime") if isinstance(cfg.get("realtime"), dict) else {}
    fake: FakeStream | None = None
    if cfg.get("_realtime_fake") is True:
        fake = FakeStream()
    hub = RealtimeHub(st, cfg, fake_stream=fake)
    snap_qp = SnapshotQuoteProvider(st)
    quote_provider: QuoteProvider = HubQuoteProvider(hub, snap_qp)
    sse_lim = ConnectionLimiter(
        max_per_key=int((rt_cfg or {}).get("sse_max_per_ip") or 5),
    )

    app.state.api_cfg = cfg
    app.state.store = st
    app.state.limiter = limiter
    app.state.debate_service = debate_svc
    app.state.debate_jobs = DebateJobManager(debate_svc, max_workers=max_workers)
    app.state.realtime_hub = hub
    app.state.sse_limiter = sse_lim
    app.state.quote_provider = quote_provider
    # Không start hub trong test trừ khi cfg yêu cầu
    if not cfg.get("skip_realtime_start"):
        try:
            hub.start()
        except Exception:  # noqa: BLE001
            pass


def get_store(request: Request) -> ResultStore:
    return request.app.state.store


def get_debate_service(request: Request) -> DebateService:
    return request.app.state.debate_service


def get_debate_jobs(request: Request) -> DebateJobManager:
    return request.app.state.debate_jobs


def get_quote_provider(request: Request) -> QuoteProvider:
    return request.app.state.quote_provider


def get_realtime_hub(request: Request) -> Any:
    return request.app.state.realtime_hub


def get_sse_limiter(request: Request) -> ConnectionLimiter:
    return request.app.state.sse_limiter


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
