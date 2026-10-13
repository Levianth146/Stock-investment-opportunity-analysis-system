"""FastAPI app — rankings / ticker / debate / quotes / PDF (feature 011)."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from stockai.api.debate_service import llm_public_status
from stockai.api.deps import (
    client_ip,
    get_api_cfg,
    get_debate_service,
    get_quote_provider,
    get_store,
    init_app_state,
)
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


def create_app(
    *,
    api_cfg: dict | None = None,
    store: ResultStore | None = None,
) -> FastAPI:
    cfg = api_cfg if api_cfg is not None else load_api_cfg()
    docs_on = bool(cfg["docs_enabled"]) if "docs_enabled" in cfg else True
    app = FastAPI(
        title="StockAI API",
        version="0.11.0",
        description="Layer đọc kết quả pipeline cho web demo (feature 011).",
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

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=500, content=format_internal_error() | {"disclaimer": DISCLAIMER, "asof": None})

    @app.get("/api/health", response_model=None)
    def health(request: Request) -> dict:
        store = get_store(request)
        return _envelope({"status": "ok"}, store)

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
        return _envelope(
            {
                "asof": store.asof,
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

    @app.get("/api/rankings", response_model=None)
    def rankings(
        request: Request,
        profile: str | None = None,
        sector: str | None = None,
        rating: str | None = None,
        q: str | None = None,
        sort: str = Query("score"),
        order: str = Query("desc"),
        limit: int = Query(50, ge=1, le=500),
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
    def sectors(request: Request) -> dict:
        return get_store(request).sectors()

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
            bundle = store.get_bundle(sym, profile, debate_mode="template")
            m7 = bundle.get("m7") or {}
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
    ) -> Any:
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        if range not in ("3m", "6m", "1y", "all"):
            return _err(400, "range không hợp lệ", store)
        try:
            return store.prices(sym, range_key=range, profile=profile)
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

    @app.get("/api/report/{symbol}.pdf", response_model=None)
    def report_pdf(
        request: Request,
        symbol: str,
        profile: str | None = None,
    ):
        """TODO(N6): M9 sẽ làm lại (font tiếng Việt, 10 mục, biểu đồ). Hiện trả stub PDF."""
        store = get_store(request)
        sym = (symbol or "").strip().upper()
        # path param có thể là "HPG.pdf" nếu route bắt nhầm — FastAPI tách {symbol}.pdf
        if sym.endswith(".PDF"):
            sym = sym[:-4]
        bad = _require_symbol(store, sym)
        if bad:
            return bad
        profile = profile or store.default_profile
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
            cfg = {"profile": profile, "out_dir": out_dir}
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

    return app


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
