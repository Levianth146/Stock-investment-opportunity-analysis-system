"""FastAPI app — rankings / ticker / debate / quotes / PDF / web SPA (011+014+017)."""
from __future__ import annotations

import asyncio
import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from stockai.api.debate_service import llm_public_status
from stockai.api.deps import (
    client_ip,
    get_api_cfg,
    get_debate_jobs,
    get_debate_service,
    get_quote_provider,
    get_realtime_hub,
    get_sse_limiter,
    get_store,
    init_app_state,
)
from stockai.api.insession import build_market_analysis
from stockai.api.spa import mount_spa, resolve_web_dist
from stockai.api.store import (
    DISCLAIMER,
    FORMULA_VERSION,
    PROFILES,
    ResultStore,
    format_internal_error,
    is_valid_symbol,
    load_api_cfg,
    repo_root,
)
from stockai.m9_report.run import run as run_m9

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,6}$")
_log = logging.getLogger(__name__)


def _warmup_caches(app: FastAPI) -> None:
    """Nạp sẵn rankings / sectors / market vào bộ nhớ nền."""
    try:
        st: ResultStore = app.state.store
        for profile in PROFILES:
            try:
                st.iter_ranking_rows(profile, include_unranked=False)
            except Exception as exc:  # noqa: BLE001
                _log.warning("warmup rankings %s: %s", profile, exc)
            try:
                st.sectors(profile=profile)
            except Exception as exc:  # noqa: BLE001
                _log.warning("warmup sectors %s: %s", profile, exc)
        try:
            st.market()
        except Exception as exc:  # noqa: BLE001
            _log.warning("warmup market: %s", exc)
    finally:
        app.state.ready = True



def _envelope(data: dict, store: ResultStore) -> dict:
    out = dict(data)
    out.setdefault("asof", store.asof)
    out.setdefault("disclaimer", DISCLAIMER)
    return out


def _err(status: int, message: str, store: ResultStore | None = None) -> JSONResponse:
    body: dict[str, Any] = {
        "error": message,
        "disclaimer": DISCLAIMER,
    }
    if store is not None:
        body["asof"] = store.asof
    else:
        body["asof"] = None
    return JSONResponse(status_code=status, content=body)


def _read_refreshed_at(store: ResultStore) -> str | None:
    """Đọc mốc refresh daily từ ``cache_dir/_refreshed_at.json``."""
    path = Path(store.cache_dir) / "_refreshed_at.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if isinstance(data, dict):
        v = data.get("refreshed_at")
        return str(v) if v else None
    return None


def create_app(
    *,
    api_cfg: dict | None = None,
    store: ResultStore | None = None,
) -> FastAPI:
    cfg = dict(api_cfg) if api_cfg is not None else load_api_cfg()
    # TestClient truyền store sẵn → bỏ warmup + không mở DNSE thật
    if store is not None:
        cfg.setdefault("skip_warmup", True)
        cfg.setdefault("skip_realtime_start", True)
    docs_on = bool(cfg["docs_enabled"]) if "docs_enabled" in cfg else True
    app = FastAPI(
        title="StockAI API",
        version="0.17.0",
        description="Layer đọc kết quả pipeline + SPA web + realtime tạm tính (011/014/017).",
        docs_url="/docs" if docs_on else None,
        redoc_url="/redoc" if docs_on else None,
        openapi_url="/openapi.json" if docs_on else None,
    )
    origins = cfg.get("cors_origins") or []
    if isinstance(origins, list) and origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=False,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["*"],
        )
    init_app_state(app, api_cfg=cfg, store=store)
    skip_warmup = store is not None or bool(cfg.get("skip_warmup"))
    app.state.ready = skip_warmup

    @app.on_event("startup")
    def _on_startup() -> None:
        if skip_warmup:
            app.state.ready = True
            return
        app.state.ready = False
        threading.Thread(
            target=_warmup_caches,
            args=(app,),
            name="stockai-warmup",
            daemon=True,
        ).start()

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content=format_internal_error() | {"disclaimer": DISCLAIMER, "asof": None})

    @app.get("/api/health", response_model=None)
    def health(request: Request) -> dict:
        store = get_store(request)
        ready = bool(getattr(request.app.state, "ready", True))
        return _envelope({"status": "ok" if ready else "warming"}, store)

    @app.get("/api/meta", response_model=None)
    def meta(request: Request) -> dict:
        store = get_store(request)
        try:
            universe, scored = store.universe_counts(store.default_profile)
        except Exception:
            universe, scored = len(store.list_tickers()), 0
        scoring_cfg = {}
        try:
            import yaml

            scoring_cfg = yaml.safe_load(
                (repo_root() / "config" / "scoring.yaml").read_text(encoding="utf-8")
            ) or {}
        except Exception:
            scoring_cfg = {}
        refreshed_at = _read_refreshed_at(store)
        return _envelope(
            {
                "asof": store.asof,
                "refreshed_at": refreshed_at,
                "profiles": list(PROFILES),
                "default_profile": store.default_profile,
                "universe_count": universe,
                "scored_count": scored,
                "formula": FORMULA_VERSION,
                "risk_reference": scoring_cfg.get("risk_reference"),
                "llm": llm_public_status(),
            },
            store,
        )

    @app.get("/api/llm/status", response_model=None)
    def llm_status(request: Request) -> dict:
        """Trạng thái LLM công khai (ok | quota_blocked | no_key). Không lộ key."""
        store = get_store(request)
        return _envelope(llm_public_status(), store)

    @app.get("/api/rankings", response_model=None)
    def rankings(
        request: Request,
        profile: str | None = None,
        sector: str | None = None,
        rating: str | None = None,
        q: str | None = None,
        sort: str = Query("score"),
        order: str = Query("desc"),
        limit: int = Query(50, ge=1, le=2000),
        offset: int = Query(0, ge=0),
        include_unranked: bool = False,
    ) -> Any:
        store = get_store(request)
        if q is not None and len(q) > 40:
            return _err(400, "q quá dài (tối đa 40 ký tự)", store)
        try:
            return store.rankings(
                profile=profile,
                sector=sector,
                rating=rating,
                q=q,
                sort=sort,
                order=order,
                limit=limit,
                offset=offset,
                include_unranked=include_unranked,
            )
        except ValueError:
            return _err(400, "Tham số không hợp lệ", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/sectors", response_model=None)
    def sectors(
        request: Request,
        profile: str | None = None,
    ) -> Any:
        store = get_store(request)
        profile = profile or store.default_profile
        if profile not in PROFILES:
            return _err(400, "profile không hợp lệ", store)
        try:
            return store.sectors(profile=profile)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/market", response_model=None)
    def market(request: Request) -> Any:
        """VN-Index đóng cửa từ snapshot (không realtime)."""
        store = get_store(request)
        try:
            return store.market()
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    def _require_symbol(store: ResultStore, symbol: str) -> JSONResponse | None:
        sym = (symbol or "").strip().upper()
        if not _SYMBOL_RE.fullmatch(sym) or not is_valid_symbol(sym):
            return _err(404, "Mã không hợp lệ", store)
        if not store.has_ticker(sym):
            return _err(404, "Không tìm thấy mã", store)
        return None

    @app.get("/api/tickers/{symbol}", response_model=None)
    def ticker_detail(
        request: Request,
        symbol: str,
        profile: str | None = None,
    ) -> Any:
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        profile = profile or store.default_profile
        try:
            from stockai.api.checks import evaluate_all_checks, pillar_ranks_in_sector

            bundle = store.get_bundle(sym, profile, debate_mode="template")
            m7 = bundle.get("m7") or {}
            snap = store.load_snapshot(sym)
            peer_metrics, peer_score_rows = store.sector_peer_context(sym, profile)
            checks = evaluate_all_checks(
                snapshot=snap,
                bundle=bundle,
                sector_peer_metrics=peer_metrics,
            )
            scores = m7.get("scores") if isinstance(m7.get("scores"), dict) else {}
            pillar_rank = pillar_ranks_in_sector(
                scores=scores,
                peer_scores=peer_score_rows,
                min_peers=8,
            )
            return _envelope(
                {
                    "symbol": sym,
                    "profile": profile,
                    "company": bundle.get("company"),
                    "result": m7,
                    "modules": {
                        "m2": _module_summary(bundle.get("m2")),
                        "m3": _module_summary(bundle.get("m3")),
                        "m4": _module_summary(bundle.get("m4")),
                        "m5": _module_summary(bundle.get("m5")),
                        "m6": _module_summary(bundle.get("m6")),
                    },
                    "validation": bundle.get("m8"),
                    "quality_gate": m7.get("quality_gate"),
                    "pillar_rank": pillar_rank,
                    "checks_summary": {
                        "rewards_count": checks.get("rewards_count"),
                        "risks_count": checks.get("risks_count"),
                        "f_score": checks.get("f_score"),
                    },
                },
                store,
            )
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/tickers/{symbol}/prices", response_model=None)
    def ticker_prices(
        request: Request,
        symbol: str,
        range: str = Query("3m", alias="range"),  # noqa: A002
        profile: str | None = None,
        include_index: bool = Query(False),
        include_indicators: bool = Query(False),
    ) -> Any:
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        if range not in ("3m", "6m", "1y", "all"):
            return _err(400, "range không hợp lệ", store)
        try:
            return store.prices(
                sym,
                range_key=range,
                profile=profile,
                include_index=include_index,
                include_indicators=include_indicators,
            )
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/tickers/{symbol}/financials", response_model=None)
    def ticker_financials(request: Request, symbol: str) -> Any:
        """BCTC năm/quý (tỷ VND) + margin/ROE/D/E/FCF/YoY. ROE năm: vốn trung bình."""
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        try:
            return store.financials(sym)
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/tickers/{symbol}/income-flow", response_model=None)
    def ticker_income_flow(
        request: Request,
        symbol: str,
        period: str = Query("TTM"),
    ) -> Any:
        """Sankey doanh thu → LNST (tỷ VND). Ngân hàng: supported=false."""
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        try:
            return store.income_flow(sym, period=period)
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/tickers/{symbol}/peers", response_model=None)
    def ticker_peers(request: Request, symbol: str) -> Any:
        """Peers ngành từ snapshot + median ngành (valuation_sector_stats)."""
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        try:
            return store.peers(sym)
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/tickers/{symbol}/news", response_model=None)
    def ticker_news(
        request: Request,
        symbol: str,
        profile: str | None = None,
    ) -> Any:
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        try:
            return store.news(sym, profile=profile)
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/tickers/{symbol}/checks", response_model=None)
    def ticker_checks(
        request: Request,
        symbol: str,
        profile: str | None = None,
    ) -> Any:
        """Phép kiểm minh họa (Piotroski/Graham/ngành/quy ước) — additive 014g."""
        from stockai.api.checks import evaluate_all_checks

        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        profile = profile or store.default_profile
        try:
            bundle = store.get_bundle(sym, profile, debate_mode="template")
            snap = store.load_snapshot(sym)
            peer_metrics, _ = store.sector_peer_context(sym, profile)
            out = evaluate_all_checks(
                snapshot=snap,
                bundle=bundle,
                sector_peer_metrics=peer_metrics,
            )
            return _envelope({"symbol": sym, "profile": profile, **out}, store)
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/tickers/{symbol}/quarter-summary", response_model=None)
    def ticker_quarter_summary(request: Request, symbol: str) -> Any:
        from stockai.api.checks import build_quarter_summary

        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        try:
            snap = store.load_snapshot(sym)
            prices = snap.get("prices") if isinstance(snap.get("prices"), dict) else {}
            rows = prices.get("rows") if isinstance(prices.get("rows"), list) else []
            out = build_quarter_summary(snap, prices_rows=rows)
            return _envelope({"symbol": sym, **out}, store)
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/tickers/{symbol}/snapshot-stats", response_model=None)
    def ticker_snapshot_stats(
        request: Request,
        symbol: str,
        profile: str | None = None,
    ) -> Any:
        from stockai.api.checks import build_snapshot_stats

        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        profile = profile or store.default_profile
        try:
            bundle = store.get_bundle(sym, profile, debate_mode="template")
            snap = store.load_snapshot(sym)
            out = build_snapshot_stats(snap, bundle)
            return _envelope({"symbol": sym, "profile": profile, **out}, store)
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.post("/api/tickers/{symbol}/debate", response_model=None)
    def ticker_debate(
        request: Request,
        symbol: str,
        profile: str | None = None,
        refresh: bool = False,
    ) -> Any:
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        profile = profile or store.default_profile
        if profile not in PROFILES:
            return _err(400, "profile không hợp lệ", store)
        try:
            svc = get_debate_service(request)
            return svc.run(
                sym,
                profile=profile,
                refresh=refresh,
                client_ip=client_ip(request),
            )
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            # LLM/validate fail đã được DebateService nuốt → TEMPLATE; đây là lỗi khác
            return _err(500, "Lỗi nội bộ", store)

    @app.post("/api/tickers/{symbol}/debate/jobs", response_model=None)
    def ticker_debate_job_create(
        request: Request,
        symbol: str,
        profile: str | None = None,
    ) -> Any:
        """Tạo job AI nền — trả ngay job_id (idempotent nếu cùng mã đang chạy)."""
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        profile = profile or store.default_profile
        if profile not in PROFILES:
            return _err(400, "profile không hợp lệ", store)
        try:
            mgr = get_debate_jobs(request)
            job = mgr.submit(sym, profile=profile, client_ip=client_ip(request))
            return _envelope(
                {
                    "job_id": job.job_id,
                    "state": job.state,
                    "symbol": job.symbol,
                    "profile": job.profile,
                    "attempt": job.attempt,
                },
                store,
            )
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/tickers/{symbol}/debate/jobs/{job_id}", response_model=None)
    def ticker_debate_job_get(
        request: Request,
        symbol: str,
        job_id: str,
        profile: str | None = None,
    ) -> Any:
        """Trạng thái job AI: queued|running|ok|failed (+ result khi xong)."""
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        profile = profile or store.default_profile
        if profile not in PROFILES:
            return _err(400, "profile không hợp lệ", store)
        mgr = get_debate_jobs(request)
        job = mgr.get_for_symbol(sym, profile, job_id)
        if job is None:
            return _err(404, "Không tìm thấy job", store)
        return _envelope(job.public(), store)

    @app.get("/api/quotes", response_model=None)
    def quotes(
        request: Request,
        symbols: str = Query(..., description="Danh sách mã, cách nhau bởi dấu phẩy"),
    ) -> Any:
        store = get_store(request)
        raw = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if len(raw) > 50:
            return _err(400, "symbols quá nhiều (tối đa 50 mã)", store)
        clean: list[str] = []
        for s in raw:
            if not is_valid_symbol(s) or not store.has_ticker(s):
                continue
            clean.append(s)
        provider = get_quote_provider(request)
        items = provider.get_quotes(clean)
        return _envelope({"items": items}, store)

    @app.get("/api/realtime/status", response_model=None)
    def realtime_status(request: Request) -> Any:
        store = get_store(request)
        hub = get_realtime_hub(request)
        return _envelope(hub.status(), store)

    @app.get("/api/realtime/market", response_model=None)
    def realtime_market(request: Request) -> Any:
        """Breadth / lists / heatmap / valuation tạm tính (nhóm liquid)."""
        store = get_store(request)
        hub = get_realtime_hub(request)
        try:
            payload = build_market_analysis(hub, store)
            return _envelope(payload, store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    @app.get("/api/stream", response_model=None)
    async def realtime_stream(
        request: Request,
        symbols: str = Query(..., description="Tối đa 20 mã, cách nhau bởi dấu phẩy"),
    ) -> Any:
        """SSE giá phiên — heartbeat 15s; refcount unsubscribe khi client rời."""
        store = get_store(request)
        cfg = get_api_cfg(request)
        rt = cfg.get("realtime") if isinstance(cfg.get("realtime"), dict) else {}
        max_sym = int(rt.get("sse_max_symbols") or 20)
        hb_sec = float(rt.get("sse_heartbeat_sec") or 15)

        raw = [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if not raw:
            return _err(400, "symbols bắt buộc", store)
        if len(raw) > max_sym:
            return _err(400, f"symbols quá nhiều (tối đa {max_sym} mã)", store)
        clean: list[str] = []
        for s in raw:
            if not _SYMBOL_RE.fullmatch(s) or not is_valid_symbol(s):
                return _err(400, f"Mã không hợp lệ: {s}", store)
            if not store.has_ticker(s):
                return _err(400, f"Không tìm thấy mã: {s}", store)
            clean.append(s)

        ip = client_ip(request)
        sse_lim = get_sse_limiter(request)
        if not sse_lim.try_acquire(ip):
            return _err(429, "Quá nhiều kết nối stream từ IP này", store)

        hub = get_realtime_hub(request)
        hub.acquire_view(clean)
        # TestClient: giới hạn số event để không treo generator vô hạn
        max_events = int(cfg.get("_sse_max_events") or 0)

        async def event_gen() -> AsyncIterator[str]:
            last_hb = time.monotonic()
            last_payload: dict[str, Any] = {}
            sent = 0
            try:
                # snapshot đầu
                items = hub.get_quotes(clean)
                first = {
                    "type": "quotes",
                    "items": items,
                    "label": "tạm tính",
                    "asof": store.asof,
                }
                last_payload = first
                yield f"data: {json.dumps(first, ensure_ascii=False)}\n\n"
                sent += 1
                if max_events and sent >= max_events:
                    return
                loops = 0
                while True:
                    if await request.is_disconnected():
                        break
                    loops += 1
                    # Chế độ test: thoát sớm dù chưa đủ event đổi giá
                    if max_events and loops > 4:
                        break
                    await asyncio.sleep(0.05 if max_events else 0.5)
                    items = hub.get_quotes(clean)
                    payload = {
                        "type": "quotes",
                        "items": items,
                        "label": "tạm tính",
                        "asof": store.asof,
                    }
                    # chỉ gửi khi đổi giá/state
                    sig = [(it.get("symbol"), it.get("price"), it.get("state")) for it in items]
                    prev_sig = [
                        (it.get("symbol"), it.get("price"), it.get("state"))
                        for it in (last_payload.get("items") or [])
                    ]
                    if sig != prev_sig:
                        last_payload = payload
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                        sent += 1
                        if max_events and sent >= max_events:
                            break
                    now = time.monotonic()
                    if now - last_hb >= hb_sec:
                        last_hb = now
                        yield f": heartbeat\n\n"
                        yield (
                            "data: "
                            + json.dumps(
                                {"type": "heartbeat", "ts": time.time()},
                                ensure_ascii=False,
                            )
                            + "\n\n"
                        )
                        sent += 1
                        if max_events and sent >= max_events:
                            break
            finally:
                hub.release_view(clean)
                sse_lim.release(ip)

        return StreamingResponse(
            event_gen(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    @app.get("/api/report/{symbol}.pdf", response_model=None)
    def report_pdf(
        request: Request,
        symbol: str,
        profile: str | None = None,
        cover: bool | None = None,
        technical: bool = False,
    ):
        """PDF M9 (feature 012). Debate: bản LLM trong cache API nếu có, ngược lại template.

        Không bao giờ gọi LLM mới khi xuất PDF.
        ``technical=true``: in phụ lục chi tiết kỹ thuật.
        """
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        # path param có thể là "HPG.pdf" nếu route bắt nhầm — FastAPI tách {symbol}.pdf
        if sym.endswith(".PDF"):
            sym = sym[:-4]
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        profile = profile or store.default_profile
        if profile not in PROFILES:
            return _err(400, "profile không hợp lệ", store)
        try:
            bundle = store.get_bundle(sym, profile, debate_mode="template")
            snapshot = store.load_snapshot(sym)
            upstream = {
                "m2": bundle.get("m2"),
                "m3": bundle.get("m3"),
                "m4": bundle.get("m4"),
                "m5": bundle.get("m5"),
                "m6": bundle.get("m6"),
                "m7": bundle.get("m7"),
                "m8": bundle.get("m8"),
            }
            out_dir = str(Path(store.cache_dir) / "reports")
            cfg: dict[str, Any] = {"profile": profile, "out_dir": out_dir}
            if cover is not None:
                cfg["cover"] = cover
            if technical:
                cfg["technical_appendix"] = True
            cfg.update(_report_context(request, store, sym, profile))
            m9 = run_m9(snapshot, upstream, cfg)
            pdf_path = Path(m9.get("pdf_path") or "")
            if not pdf_path.is_file():
                return _err(500, "Lỗi nội bộ", store)
            return FileResponse(
                path=str(pdf_path),
                media_type="application/pdf",
                filename=f"{sym}_{store.asof}_{profile}.pdf",
            )
        except KeyError:
            return _err(404, "Không tìm thấy mã", store)
        except Exception:
            return _err(500, "Lỗi nội bộ", store)

    # SPA: chỉ khi cấu hình có web_dist_dir và thư mục tồn tại (không tự gắn trong test)
    if cfg.get("web_dist_dir"):
        dist = resolve_web_dist(cfg, repo_root())
        if dist is not None:
            mount_spa(app, dist)

    return app


def _ranked_scores(store: ResultStore, profile: str) -> list[tuple[str, float]]:
    rows = store.iter_ranking_rows(profile, include_unranked=False)
    return [
        (str(r["ticker"]), float(r["score"]))
        for r in rows
        if r.get("ranked") and isinstance(r.get("score"), (int, float))
    ]


def _report_context(request: Request, store: ResultStore, sym: str, profile: str) -> dict[str, Any]:
    """Ngữ cảnh cho M9: điểm cả universe cùng profile, profile còn lại, debate đã cache (không gọi LLM)."""
    ctx: dict[str, Any] = {}
    try:
        ctx["universe_scores"] = _ranked_scores(store, profile)
    except Exception:
        ctx["universe_scores"] = []
    other = next((p for p in PROFILES if p != profile), None)
    if other:
        try:
            ob = store.get_bundle(sym, other, debate_mode="template")
            ctx["other_profile"] = {"m7": ob.get("m7"), "universe_scores": _ranked_scores(store, other)}
        except Exception:
            pass
    try:
        cached = get_debate_service(request).read_cached(sym, profile)
    except Exception:
        cached = None
    if cached:
        ctx["debate"] = {
            "source": "CACHE",
            "bull": list(cached.get("bull") or []),
            "bear": list(cached.get("bear") or []),
            "model": cached.get("model"),
        }
    return ctx


def _module_summary(mod: dict | None) -> dict[str, Any]:
    if not isinstance(mod, dict):
        return {"status": "missing", "score": None, "flags": []}
    return {
        "module": mod.get("module"),
        "status": mod.get("status"),
        "score": mod.get("score"),
        "flags": list(mod.get("flags") or [])[:20],
        "metrics": mod.get("metrics") if isinstance(mod.get("metrics"), dict) else {},
    }


# Instance mặc định cho uvicorn: stockai.api.app:app
app = create_app()
