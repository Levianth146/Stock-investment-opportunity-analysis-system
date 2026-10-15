"""Kho kết quả M2–M8 (NO-LLM) + cache đĩa cho FastAPI."""
from __future__ import annotations

import hashlib
import json
import re
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from stockai.contracts.schemas import validate
from stockai.m2_fundamental.run import run as run_m2
from stockai.m3_technical.run import run as run_m3
from stockai.m4_valuation.run import run as run_m4
from stockai.m5_sentiment.run import run as run_m5
from stockai.m6_risk.run import run as run_m6
from stockai.m7_scoring.run import run as run_m7
from stockai.m8_validate.run import run as run_m8

_SYMBOL_RE = re.compile(r"^[A-Z0-9]{1,6}$")
DISCLAIMER = (
    "Đây không phải lời khuyên đầu tư. Điểm số mang tính minh họa, "
    "chưa hiệu chỉnh/kiểm định (illustrative, uncalibrated)."
)
PROFILES = ("long_term", "swing")
FORMULA_VERSION = "v2"
SORT_KEYS = {"score", "F", "T", "V", "S", "R"}


def _quantile_sorted(sorted_vals: list[float], q: float) -> float | None:
    """Phân vị tuyến tính trên mẫu đã sắp (q trong [0, 1])."""
    import math

    if not sorted_vals:
        return None
    n = len(sorted_vals)
    if n == 1:
        return float(sorted_vals[0])
    q = max(0.0, min(1.0, float(q)))
    idx = q * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(sorted_vals[lo])
    w = idx - lo
    return float(sorted_vals[lo]) * (1.0 - w) + float(sorted_vals[hi]) * w


def _percentile_band(sorted_vals: list[float]) -> dict[str, float | None] | None:
    """p10/p25/p50/p75/p90 từ pe_sorted/pb_sorted — phục vụ biểu đồ định giá."""
    if not sorted_vals:
        return None
    return {
        "p10": _quantile_sorted(sorted_vals, 0.10),
        "p25": _quantile_sorted(sorted_vals, 0.25),
        "p50": _quantile_sorted(sorted_vals, 0.50),
        "p75": _quantile_sorted(sorted_vals, 0.75),
        "p90": _quantile_sorted(sorted_vals, 0.90),
    }


def repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def load_api_cfg(path: str | Path | None = None) -> dict:
    p = Path(path) if path else repo_root() / "config" / "api.yaml"
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return dict(raw) if isinstance(raw, dict) else {}


def is_valid_symbol(symbol: str) -> bool:
    return bool(symbol) and bool(_SYMBOL_RE.fullmatch(symbol))


def _safe_module(name: str, fn, snapshot: dict, upstream: dict, cfg: dict, schema: str) -> dict:
    try:
        out = fn(snapshot, upstream, cfg)
        errs = validate(out, schema)
        if errs:
            return {
                "module": name,
                "status": "error",
                "score": None,
                "metrics": {},
                "evidence": [],
                "flags": [f"{name}_invalid_output"],
                "error": "; ".join(errs[:3]),
            }
        return out
    except Exception as e:  # noqa: BLE001
        return {
            "module": name,
            "status": "error",
            "score": None,
            "metrics": {},
            "evidence": [],
            "flags": [f"{name}_crashed"],
            "error": str(e)[:200],
        }


def run_m2_m8(
    snapshot: dict,
    profile: str,
    *,
    debate_mode: str = "template",
    out_dir: str | None = None,
) -> dict[str, Any]:
    """Chạy M2–M8; mặc định debate.mode=template (không LLM)."""
    root = repo_root()
    cfg: dict[str, Any] = {}
    for name in ("scoring", "data_sources", "llm", "valuation", "technical", "sentiment"):
        fp = root / "config" / f"{name}.yaml"
        if fp.is_file():
            chunk = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
            if isinstance(chunk, dict):
                cfg.update(chunk)
    cfg["profile"] = profile
    if out_dir:
        cfg["out_dir"] = out_dir

    # Ép chế độ debate cho nhánh API list/cache
    llm = dict(cfg.get("llm") or {}) if isinstance(cfg.get("llm"), dict) else {}
    debate = dict(llm.get("debate") or {}) if isinstance(llm.get("debate"), dict) else {}
    debate["mode"] = debate_mode
    llm["debate"] = debate
    cfg["llm"] = llm
    cfg["debate"] = debate

    up: dict[str, Any] = {}
    for name, fn in (
        ("m2", run_m2),
        ("m3", run_m3),
        ("m4", run_m4),
        ("m5", run_m5),
        ("m6", run_m6),
    ):
        up[name] = _safe_module(name, fn, snapshot, up, cfg, "module_out")
    up["m7"] = _safe_module("m7", run_m7, snapshot, up, cfg, "result")
    up["m8"] = _safe_module("m8", run_m8, snapshot, up, cfg, "validation")
    return up


def _file_digest(path: Path) -> str:
    if not path.is_file():
        return "missing"
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


def config_fingerprint(root: Path | None = None) -> str:
    root = root or repo_root()
    parts = [
        _file_digest(root / "config" / "scoring.yaml"),
        _file_digest(root / "config" / "valuation.yaml"),
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:16]


class ResultStore:
    """Đọc snapshot + cache kết quả M2–M8 theo (ticker, profile, asof, cfg+mtime)."""

    def __init__(
        self,
        api_cfg: dict | None = None,
        *,
        snapshots_dir: Path | None = None,
        cache_dir: Path | None = None,
        asof: str | None = None,
        root: Path | None = None,
    ) -> None:
        self.root = root or repo_root()
        self.api_cfg = dict(api_cfg or load_api_cfg(self.root / "config" / "api.yaml"))
        snap_rel = snapshots_dir or Path(
            str(self.api_cfg.get("snapshots_dir") or "data/snapshots_ext")
        )
        self.snapshots_dir = snap_rel if snap_rel.is_absolute() else self.root / snap_rel
        cache_rel = cache_dir or Path(str(self.api_cfg.get("cache_dir") or "data/api_cache"))
        self.cache_dir = cache_rel if cache_rel.is_absolute() else self.root / cache_rel
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_profile = str(self.api_cfg.get("default_profile") or "long_term")
        self._cfg_fp = config_fingerprint(self.root)
        self._ticker_index: dict[str, Path] | None = None
        self._ticker_catalog: list[dict[str, Any]] | None = None
        self._ranking_mem: dict[str, list[dict[str, Any]]] = {}
        self._scored_tickers: list[str] | None = None
        self._asof = asof if asof and asof != "auto" else None
        if self._asof is None:
            cfg_asof = self.api_cfg.get("asof")
            if isinstance(cfg_asof, str) and cfg_asof.strip() and cfg_asof.strip().lower() != "auto":
                self._asof = cfg_asof.strip()
        self._resolved_asof: str | None = None

    @property
    def asof(self) -> str:
        if self._asof:
            return self._asof
        if self._resolved_asof:
            return self._resolved_asof
        self._resolved_asof = self._discover_newest_asof()
        return self._resolved_asof

    def _discover_newest_asof(self) -> str:
        dates: list[str] = []
        if not self.snapshots_dir.is_dir():
            return datetime.utcnow().strftime("%Y-%m-%d")
        for p in self.snapshots_dir.rglob("*_????-??-??.json"):
            if p.name.startswith("_"):
                continue
            stem = p.stem
            if "_" not in stem:
                continue
            d = stem.rsplit("_", 1)[-1]
            ticker = stem.rsplit("_", 1)[0]
            if is_valid_symbol(ticker) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                dates.append(d)
        return max(dates) if dates else datetime.utcnow().strftime("%Y-%m-%d")

    def _build_index(self) -> dict[str, Path]:
        if self._ticker_index is not None:
            return self._ticker_index
        idx: dict[str, Path] = {}
        asof = self.asof
        if self.snapshots_dir.is_dir():
            # Prefer files nearest the configured root when a ticker is duplicated.
            paths = sorted(self.snapshots_dir.rglob(f"*_{asof}.json"),
                           key=lambda p: (len(p.relative_to(self.snapshots_dir).parts), p.as_posix()))
            for p in paths:
                if p.name.startswith("_"):
                    continue
                ticker = p.name[: -(len(asof) + 6)]  # strip _YYYY-MM-DD.json
                if is_valid_symbol(ticker):
                    idx.setdefault(ticker, p)
        self._ticker_index = idx
        return idx

    def list_tickers(self) -> list[str]:
        return sorted(self._build_index().keys())

    def ticker_catalog(self) -> list[dict[str, Any]]:
        """All snapshot tickers, without running scoring or filtering out unranked stocks."""
        if self._ticker_catalog is not None:
            return self._ticker_catalog
        from math import isfinite

        def finite(value):
            return value if isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value) else None

        items = []
        for ticker in self.list_tickers():
            try:
                snapshot = self.load_snapshot(ticker)
            except (OSError, ValueError):
                items.append({"symbol": ticker, "name": ticker, "snapshot_status": "error"})
                continue
            company = snapshot.get("company") or {}
            prices = sorted((row for row in (snapshot.get("prices") or {}).get("rows", [])
                             if row.get("date", "") <= self.asof and finite(row.get("close")) is not None),
                            key=lambda row: row.get("date", ""))
            latest = prices[-1] if prices else {}
            close = finite(latest.get("close"))
            previous = finite(prices[-2].get("close")) if len(prices) > 1 else None
            change = close - previous if close is not None and previous is not None else None
            items.append({
                "symbol": ticker, "name": company.get("name") or ticker,
                "exchange": company.get("exchange"), "sector": company.get("sector"),
                "snapshot_status": "ok", "data_status": (snapshot.get("meta") or {}).get("data_status") or {},
                "price_date": latest.get("date"), "current_price": close,
                "price_change": change,
                "price_change_percent": round(change / previous * 100, 2) if change is not None and previous and previous > 0 else None,
                "volume": finite(latest.get("volume")),
            })
        self._ticker_catalog = items
        return items

    def list_scored_tickers(self) -> list[str]:
        """Mã không insufficient (quality_gate scored). Cache sau lần quét đầu."""
        from stockai.contracts.helpers import quality_tier

        if self._scored_tickers is not None:
            return list(self._scored_tickers)
        scored: list[str] = []
        for t in self.list_tickers():
            try:
                if quality_tier(self.load_snapshot(t)) != "insufficient":
                    scored.append(t)
            except Exception:
                continue
        self._scored_tickers = scored
        return list(scored)

    def has_ticker(self, symbol: str) -> bool:
        return symbol in self._build_index()

    def snapshot_path(self, symbol: str) -> Path:
        idx = self._build_index()
        if symbol not in idx:
            raise KeyError(symbol)
        return idx[symbol]

    def load_snapshot(self, symbol: str) -> dict:
        path = self.snapshot_path(symbol)
        return json.loads(path.read_text(encoding="utf-8"))

    def _cache_hash(self, symbol: str) -> str:
        path = self.snapshot_path(symbol)
        mtime = str(path.stat().st_mtime_ns)
        raw = f"{symbol}|{self.default_profile}|{self.asof}|{self._cfg_fp}|{mtime}"
        # profile nằm trong tên file cache; hash gồm cfg + mtime snapshot
        return hashlib.sha256(f"{self._cfg_fp}|{mtime}".encode()).hexdigest()[:20]

    def cache_path(self, symbol: str, profile: str) -> Path:
        h = self._cache_hash(symbol)
        return self.cache_dir / f"{symbol}_{self.asof}_{profile}_{h}.json"

    def get_bundle(
        self,
        symbol: str,
        profile: str,
        *,
        debate_mode: str = "template",
        force: bool = False,
    ) -> dict[str, Any]:
        """Trả upstream M2–M8 (+ meta). Ưu tiên cache đĩa khi debate_mode=template."""
        if not is_valid_symbol(symbol) or not self.has_ticker(symbol):
            raise KeyError(symbol)
        if profile not in PROFILES:
            raise ValueError(f"profile không hợp lệ: {profile}")

        cpath = self.cache_path(symbol, profile)
        if debate_mode == "template" and not force and cpath.is_file():
            try:
                cached = json.loads(cpath.read_text(encoding="utf-8"))
                if isinstance(cached, dict) and "m7" in cached:
                    # Bổ sung shares_outstanding nếu cache cũ thiếu (additive, không đổi điểm)
                    co = cached.get("company") if isinstance(cached.get("company"), dict) else {}
                    if co.get("shares_outstanding") is None:
                        try:
                            snap = self.load_snapshot(symbol)
                            sc = snap.get("company") if isinstance(snap.get("company"), dict) else {}
                            if sc.get("shares_outstanding") is not None:
                                co = dict(co)
                                co["shares_outstanding"] = sc.get("shares_outstanding")
                                cached = dict(cached)
                                cached["company"] = co
                        except Exception:
                            pass
                    return cached
            except (OSError, json.JSONDecodeError):
                pass

        snapshot = self.load_snapshot(symbol)
        up = run_m2_m8(snapshot, profile, debate_mode=debate_mode)
        company = snapshot.get("company") if isinstance(snapshot.get("company"), dict) else {}
        bundle = {
            "ticker": symbol,
            "as_of": self.asof,
            "profile": profile,
            "company": {
                "name": company.get("name"),
                "sector": company.get("sector"),
                "exchange": company.get("exchange"),
                "is_bank": company.get("is_bank"),
                "shares_outstanding": company.get("shares_outstanding"),
            },
            "m2": up.get("m2"),
            "m3": up.get("m3"),
            "m4": up.get("m4"),
            "m5": up.get("m5"),
            "m6": up.get("m6"),
            "m7": up.get("m7"),
            "m8": up.get("m8"),
            "debate_mode": debate_mode,
            "cache_hash": self._cache_hash(symbol),
        }
        if debate_mode == "template":
            try:
                cpath.write_text(
                    json.dumps(bundle, ensure_ascii=False, indent=1, default=str),
                    encoding="utf-8",
                )
            except OSError:
                pass
        return bundle

    def ranking_row(self, bundle: dict) -> dict[str, Any]:
        from stockai.api.signals import build_signals_from_m3

        m7 = bundle.get("m7") or {}
        company = bundle.get("company") or {}
        scores = m7.get("scores") if isinstance(m7.get("scores"), dict) else {}
        qg = m7.get("quality_gate") if isinstance(m7.get("quality_gate"), dict) else {}
        scored = qg.get("scored") is not False and m7.get("score") is not None
        # Giá đóng cửa + giá tham chiếu (bội số ngành M4) — additive cho UI web
        price = None
        m4 = bundle.get("m4") if isinstance(bundle.get("m4"), dict) else {}
        m4m = m4.get("metrics") if isinstance(m4.get("metrics"), dict) else {}
        pc = m4m.get("price_close")
        if isinstance(pc, dict):
            price = pc.get("value")
        elif isinstance(pc, (int, float)):
            price = float(pc)
        target = m7.get("target") if isinstance(m7.get("target"), dict) else None
        if target is None and isinstance(m4.get("target"), dict):
            target = m4.get("target")
        ref = target.get("base") if isinstance(target, dict) else None
        upside = None
        if isinstance(price, (int, float)) and isinstance(ref, (int, float)) and price != 0:
            upside = round((float(ref) - float(price)) / float(price) * 100.0, 2)
        shares = company.get("shares_outstanding")
        market_cap = None
        if (
            isinstance(shares, (int, float))
            and isinstance(price, (int, float))
            and shares > 0
            and price > 0
        ):
            market_cap = float(shares) * float(price)
        m3 = bundle.get("m3") if isinstance(bundle.get("m3"), dict) else None
        signals = build_signals_from_m3(m3)
        return {
            "ticker": bundle.get("ticker") or m7.get("ticker"),
            "name": company.get("name"),
            "sector": company.get("sector"),
            "exchange": company.get("exchange"),
            "score": m7.get("score"),
            "rating": m7.get("rating") or "Không xếp hạng",
            "scores": {
                "F": scores.get("F"),
                "T": scores.get("T"),
                "V": scores.get("V"),
                "S": scores.get("S"),
                "R": scores.get("R"),
            },
            "price": price,
            "reference_price": ref,
            "upside_pct": upside,
            "market_cap": market_cap,
            "signals": signals,
            "ranked": bool(scored),
            "quality_gate": qg,
        }

    def market(self) -> dict[str, Any]:
        """VN-Index từ snapshot (đóng cửa gần nhất ≤ asof) — không realtime."""
        tickers = self.list_scored_tickers() or self.list_tickers()
        sample = tickers[:8]
        series_by_ticker: dict[str, list[dict[str, Any]]] = {}
        for t in sample:
            try:
                snap = self.load_snapshot(t)
            except Exception:
                continue
            idx = snap.get("index") if isinstance(snap.get("index"), dict) else {}
            rows = idx.get("rows") if isinstance(idx, dict) else None
            if not isinstance(rows, list):
                continue
            cleaned: list[dict[str, Any]] = []
            for r in rows:
                if not isinstance(r, dict):
                    continue
                d = str(r.get("date") or "")[:10]
                if not d or d > self.asof:
                    continue
                c = r.get("close")
                if not isinstance(c, (int, float)):
                    continue
                cleaned.append({"time": d, "close": float(c)})
            if cleaned:
                series_by_ticker[t] = cleaned

        if not series_by_ticker:
            return {
                "asof": self.asof,
                "disclaimer": DISCLAIMER,
                "index": None,
                "flags": ["market_index_unavailable"],
            }

        # Chọn chuỗi dài nhất làm gốc; đối chiếu tối đa 3 mã
        primary_t = max(series_by_ticker.keys(), key=lambda k: len(series_by_ticker[k]))
        primary = series_by_ticker[primary_t]
        flags: list[str] = []
        others = [k for k in series_by_ticker if k != primary_t][:2]
        for ot in others:
            a = {p["time"]: p["close"] for p in primary[-5:]}
            b = {p["time"]: p["close"] for p in series_by_ticker[ot][-5:]}
            common = set(a) & set(b)
            if not common:
                flags.append(f"market_index_no_overlap:{ot}")
                continue
            if any(abs(a[d] - b[d]) > 1e-6 for d in common):
                flags.append(f"market_index_mismatch:{ot}")

        series_30d = primary[-30:]
        last = series_30d[-1] if series_30d else None
        prev = series_30d[-2] if len(series_30d) >= 2 else None
        change_pct = None
        if last and prev and prev["close"]:
            change_pct = round((last["close"] - prev["close"]) / prev["close"] * 100.0, 2)

        return {
            "asof": self.asof,
            "disclaimer": DISCLAIMER,
            "index": {
                "symbol": "VNINDEX",
                "close": last["close"] if last else None,
                "change_pct": change_pct,
                "asof_session": last["time"] if last else None,
                "series_30d": series_30d,
            },
            "flags": flags,
        }

    def iter_ranking_rows(
        self, profile: str, *, include_unranked: bool = True
    ) -> list[dict[str, Any]]:
        from stockai.contracts.helpers import quality_tier

        mem_key = f"{profile}|{include_unranked}|{self.asof}|{self._cfg_fp}"
        if mem_key in self._ranking_mem:
            return list(self._ranking_mem[mem_key])

        tickers = self.list_tickers() if include_unranked else self.list_scored_tickers()
        rows: list[dict[str, Any]] = []
        for ticker in tickers:
            try:
                if include_unranked:
                    snap = self.load_snapshot(ticker)
                    if quality_tier(snap) == "insufficient":
                        # hàng unranked tối thiểu — không chạy M2–M8
                        from stockai.contracts.helpers import quality_reasons

                        company = snap.get("company") if isinstance(snap.get("company"), dict) else {}
                        reasons = quality_reasons(snap)
                        rows.append(
                            {
                                "ticker": ticker,
                                "name": company.get("name"),
                                "sector": company.get("sector"),
                                "exchange": company.get("exchange"),
                                "score": None,
                                "rating": "Không xếp hạng",
                                "scores": {"F": None, "T": None, "V": None, "S": None, "R": None},
                                "price": None,
                                "reference_price": None,
                                "upside_pct": None,
                                "market_cap": None,
                                "signals": {
                                    "above_ma50": None,
                                    "above_ma200": None,
                                    "rsi_zone": None,
                                    "volume_up": None,
                                },
                                "ranked": False,
                                "quality_gate": {
                                    "tier": "insufficient",
                                    "scored": False,
                                    "reasons": reasons,
                                },
                            }
                        )
                        continue
                bundle = self.get_bundle(ticker, profile, debate_mode="template")
                row = self.ranking_row(bundle)
                # 014g: số cơ hội / rủi ro (không gồm basis=info); peers ngành bỏ qua ở bảng xếp hạng
                try:
                    from stockai.api.checks import evaluate_all_checks

                    snap = self.load_snapshot(ticker)
                    ch = evaluate_all_checks(
                        snapshot=snap,
                        bundle=bundle,
                        sector_peer_metrics=[],
                    )
                    row["rewards_count"] = ch.get("rewards_count")
                    row["risks_count"] = ch.get("risks_count")
                except Exception:
                    row["rewards_count"] = None
                    row["risks_count"] = None
                rows.append(row)
            except Exception:
                # bỏ mã lỗi khi xây bảng xếp hạng (demo); không lộ traceback ra API
                continue
        self._ranking_mem[mem_key] = list(rows)
        return rows

    def rankings(
        self,
        *,
        profile: str | None = None,
        sector: str | None = None,
        rating: str | None = None,
        q: str | None = None,
        sort: str = "score",
        order: str = "desc",
        limit: int = 50,
        offset: int = 0,
        include_unranked: bool = False,
    ) -> dict[str, Any]:
        profile = profile or self.default_profile
        if profile not in PROFILES:
            raise ValueError("profile")
        sort = sort if sort in SORT_KEYS else "score"
        order = order if order in ("asc", "desc") else "desc"
        limit = max(1, min(2000, int(limit)))
        offset = max(0, int(offset))

        rows = self.iter_ranking_rows(profile, include_unranked=include_unranked)
        if not include_unranked:
            rows = [r for r in rows if r.get("ranked")]
        if sector:
            sec = sector.strip().lower()
            rows = [r for r in rows if str(r.get("sector") or "").lower() == sec]
        if rating:
            rows = [r for r in rows if str(r.get("rating") or "") == rating]
        if q:
            qq = q.strip().upper()
            rows = [
                r
                for r in rows
                if qq in str(r.get("ticker") or "").upper()
                or qq in str(r.get("name") or "").upper()
            ]

        reverse = order == "desc"

        def sort_val(r: dict) -> tuple:
            if sort == "score":
                v = r.get("score")
            else:
                v = (r.get("scores") or {}).get(sort)
            # None cuối khi desc, đầu khi asc → dùng sentinel
            missing = v is None
            num = float(v) if isinstance(v, (int, float)) else 0.0
            return (missing, -num if reverse else num, str(r.get("ticker") or ""))

        rows.sort(key=sort_val)
        total = len(rows)
        page = rows[offset : offset + limit]
        # total_scored = số mã đã có điểm trong profile (không phụ thuộc limit/lọc)
        scored_n = sum(
            1
            for r in self.iter_ranking_rows(profile, include_unranked=False)
            if r.get("ranked") and isinstance(r.get("score"), (int, float))
        )
        return {
            "total": total,
            "total_scored": int(scored_n),
            "items": page,
            "asof": self.asof,
            "disclaimer": DISCLAIMER,
        }

    def sectors(self, *, profile: str | None = None) -> dict[str, Any]:
        """Danh sách ngành + thống kê điểm (additive, feature 014)."""
        profile = profile or self.default_profile
        counts: dict[str, int] = {}
        for ticker in self.list_tickers():
            try:
                snap = self.load_snapshot(ticker)
            except Exception:
                continue
            company = snap.get("company") if isinstance(snap.get("company"), dict) else {}
            sec = company.get("sector") or "Khác"
            if not isinstance(sec, str) or not sec.strip():
                sec = "Khác"
            counts[sec] = counts.get(sec, 0) + 1

        # Thống kê từ hàng đã xếp hạng (chạy cache template)
        by_sec: dict[str, list[dict[str, Any]]] = {}
        try:
            rows = self.iter_ranking_rows(profile, include_unranked=False)
        except Exception:
            rows = []
        for r in rows:
            if not r.get("ranked"):
                continue
            sec = r.get("sector") or "Khác"
            by_sec.setdefault(str(sec), []).append(r)

        def _median(vals: list[float]) -> float | None:
            if not vals:
                return None
            s = sorted(vals)
            n = len(s)
            mid = n // 2
            if n % 2:
                return s[mid]
            return (s[mid - 1] + s[mid]) / 2.0

        def _mean(vals: list[float]) -> float | None:
            return sum(vals) / len(vals) if vals else None

        items: list[dict[str, Any]] = []
        for sec, count in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            scored_rows = by_sec.get(sec, [])
            score_vals = [
                float(r["score"])
                for r in scored_rows
                if isinstance(r.get("score"), (int, float))
            ]
            rating_dist: dict[str, int] = {}
            for r in scored_rows:
                rt = str(r.get("rating") or "Không xếp hạng")
                rating_dist[rt] = rating_dist.get(rt, 0) + 1
            pillar_means: dict[str, float | None] = {}
            for k in ("F", "T", "V", "S", "R"):
                vals = [
                    float((r.get("scores") or {}).get(k))
                    for r in scored_rows
                    if isinstance((r.get("scores") or {}).get(k), (int, float))
                ]
                m = _mean(vals)
                pillar_means[k] = round(m, 2) if m is not None else None
            mean_s = _mean(score_vals)
            med_s = _median(score_vals)
            items.append(
                {
                    "sector": sec,
                    "label": sec,
                    "count": count,
                    "n_scored": len(scored_rows),
                    "mean_score": round(mean_s, 2) if mean_s is not None else None,
                    "median_score": round(med_s, 2) if med_s is not None else None,
                    "rating_distribution": rating_dist,
                    "mean_pillars": pillar_means,
                }
            )
        return {
            "asof": self.asof,
            "disclaimer": DISCLAIMER,
            "profile": profile,
            "items": items,
        }

    def sector_peer_context(
        self, symbol: str, profile: str | None = None
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Peers cùng ngành có điểm: metrics cho percentile + scores cho pillar_rank.

        Trả (peer_metrics, peer_score_rows). Không gồm chính mã trong metrics list
        (caller tự cộng); score rows gồm cả peers scored cùng ngành (có thể gồm self).
        """
        profile = profile or self.default_profile
        try:
            own = self.load_snapshot(symbol)
        except Exception:
            return [], []
        company = own.get("company") if isinstance(own.get("company"), dict) else {}
        sector = company.get("sector") or ""
        if not sector:
            return [], []

        rows = self.iter_ranking_rows(profile, include_unranked=False)
        sector_rows = [
            r
            for r in rows
            if r.get("ranked")
            and str(r.get("sector") or "") == str(sector)
            and isinstance(r.get("score"), (int, float))
        ]
        peer_score_rows = [
            {"ticker": r.get("ticker"), "scores": r.get("scores") or {}, "score": r.get("score")}
            for r in sector_rows
        ]

        metrics: list[dict[str, Any]] = []
        for r in sector_rows:
            t = str(r.get("ticker") or "")
            if not t or t == symbol:
                continue
            try:
                b = self.get_bundle(t, profile, debate_mode="template")
            except Exception:
                continue
            m2 = b.get("m2") if isinstance(b.get("m2"), dict) else {}
            m4 = b.get("m4") if isinstance(b.get("m4"), dict) else {}
            m6 = b.get("m6") if isinstance(b.get("m6"), dict) else {}

            def _mv(mod: dict, key: str) -> float | None:
                met = mod.get("metrics") if isinstance(mod.get("metrics"), dict) else {}
                raw = met.get(key)
                if isinstance(raw, (int, float)):
                    return float(raw)
                if isinstance(raw, dict) and isinstance(raw.get("value"), (int, float)):
                    return float(raw["value"])
                return None

            metrics.append(
                {
                    "ticker": t,
                    "pe": _mv(m4, "pe"),
                    "pb": _mv(m4, "pb"),
                    "roe": _mv(m2, "roe") or _mv(m4, "roe"),
                    "revenue_yoy": _mv(m2, "revenue_yoy") or _mv(m2, "rev_yoy"),
                    "ann_vol": _mv(m6, "ann_vol") or _mv(m6, "volatility"),
                }
            )
        return metrics, peer_score_rows

    def universe_counts(self, profile: str | None = None) -> tuple[int, int]:
        """Đếm universe/scored từ quality_tier snapshot — không chạy M2–M8."""
        _ = profile
        return len(self.list_tickers()), len(self.list_scored_tickers())

    def prices(
        self,
        symbol: str,
        *,
        range_key: str = "3m",
        profile: str | None = None,
        include_index: bool = False,
        include_indicators: bool = False,
    ) -> dict[str, Any]:
        """OHLCV + tùy chọn VN-Index căn ngày và chuỗi chỉ báo (cùng công thức M3)."""
        from stockai.api.indicators import align_index_series, compute_indicator_series

        profile = profile or self.default_profile
        snap = self.load_snapshot(symbol)
        all_rows = list(((snap.get("prices") or {}).get("rows") or []))
        asof = self.asof
        # Lọc không look-ahead trước khi cắt range
        rows = [
            r
            for r in all_rows
            if isinstance(r, dict) and str(r.get("date") or "")[:10] <= asof
        ]
        # Chỉ báo cần lịch sử dài hơn cửa sổ hiển thị — tính trên toàn bộ ≤ as_of rồi cắt
        full_ohlcv = [
            {
                "time": r.get("date"),
                "open": r.get("open"),
                "high": r.get("high"),
                "low": r.get("low"),
                "close": r.get("close"),
                "volume": r.get("volume"),
            }
            for r in rows
        ]
        display = full_ohlcv
        if display and range_key != "all":
            n_map = {"3m": 63, "6m": 126, "1y": 252}
            n = n_map.get(range_key, 63)
            display = display[-n:]

        # Giá trị MA cuối (tương thích 011) từ M3 metrics
        ma20 = ma50 = None
        try:
            bundle = self.get_bundle(symbol, profile, debate_mode="template")
            m3 = bundle.get("m3") or {}
            metrics = m3.get("metrics") if isinstance(m3.get("metrics"), dict) else {}
            if isinstance(metrics.get("ma20"), dict):
                ma20 = metrics["ma20"].get("value")
            if isinstance(metrics.get("ma50"), dict):
                ma50 = metrics["ma50"].get("value")
        except Exception:
            pass

        out: dict[str, Any] = {
            "asof": asof,
            "disclaimer": DISCLAIMER,
            "symbol": symbol,
            "range": range_key,
            "ohlcv": display,
            "ma20": ma20,
            "ma50": ma50,
        }

        times = [str(r.get("time") or "")[:10] for r in display]

        if include_index:
            idx = snap.get("index") if isinstance(snap.get("index"), dict) else {}
            idx_rows = list(idx.get("rows") or []) if isinstance(idx, dict) else []
            aligned = align_index_series(idx_rows, times, as_of=asof)
            out["index"] = {
                "symbol": (idx.get("symbol") if isinstance(idx, dict) else None) or "VNINDEX",
                "series": aligned,  # None nếu thiếu nguồn
                "note": None
                if aligned is not None
                else "Không có chuỗi chỉ số trong snapshot; trả null.",
            }

        if include_indicators:
            # Tính trên full rồi cắt theo cửa sổ hiển thị
            series = compute_indicator_series(full_ohlcv, as_of=asof)
            time_set = set(times)
            out["indicators"] = {
                k: [p for p in v if p.get("time") in time_set] for k, v in series.items()
            }
            out["indicators_meta"] = {
                "source": "m3_formula_parity",
                "note": "MA/RSI/MACD cùng công thức M3; không dùng phiên sau as_of.",
            }

        return out

    def financials(self, symbol: str) -> dict[str, Any]:
        from stockai.api.financials import build_financials_payload

        snap = self.load_snapshot(symbol)
        payload = build_financials_payload(snap, asof=self.asof, disclaimer=DISCLAIMER)
        payload["symbol"] = symbol
        return payload

    def income_flow(self, symbol: str, *, period: str = "TTM") -> dict[str, Any]:
        """Sankey P&L (017c). period = năm ``YYYY`` hoặc ``TTM``."""
        from stockai.api.income_flow import build_income_flow_payload

        snap = self.load_snapshot(symbol)
        payload = build_income_flow_payload(
            snap,
            period=(period or "TTM").strip(),
            asof=self.asof,
            disclaimer=DISCLAIMER,
        )
        payload["symbol"] = symbol
        return payload

    def peers(self, symbol: str) -> dict[str, Any]:
        """Peers từ snapshot + hàng mã đang xem; median ngành từ valuation_sector_stats."""
        snap = self.load_snapshot(symbol)
        company = snap.get("company") if isinstance(snap.get("company"), dict) else {}
        sector = company.get("sector")
        peer_rows = [p for p in (snap.get("peers") or []) if isinstance(p, dict)]

        # Hàng chính: lấy từ M4 metrics nếu có
        own: dict[str, Any] = {
            "ticker": symbol,
            "is_self": True,
            "pe": None,
            "pb": None,
            "roe": None,
            "market_cap": None,
        }
        try:
            bundle = self.get_bundle(symbol, self.default_profile, debate_mode="template")
            m4 = bundle.get("m4") or {}
            metrics = m4.get("metrics") if isinstance(m4.get("metrics"), dict) else {}
            for key in ("pe", "pb"):
                raw = metrics.get(key)
                if isinstance(raw, dict):
                    own[key] = raw.get("value")
                elif isinstance(raw, (int, float)):
                    own[key] = float(raw)
            # ROE từ M2 nếu có
            m2 = bundle.get("m2") or {}
            m2m = m2.get("metrics") if isinstance(m2.get("metrics"), dict) else {}
            roe_m = m2m.get("roe")
            if isinstance(roe_m, dict):
                own["roe"] = roe_m.get("value")
        except Exception:
            pass
        # market_cap từ snapshot meta/company nếu có
        for src in (company, snap.get("meta") or {}):
            if isinstance(src, dict) and src.get("market_cap") is not None:
                try:
                    own["market_cap"] = float(src["market_cap"])
                except (TypeError, ValueError):
                    pass
                break

        items: list[dict[str, Any]] = [own]
        for p in peer_rows:
            t = str(p.get("ticker") or "").upper()
            if not t or t == symbol:
                continue
            items.append(
                {
                    "ticker": t,
                    "is_self": False,
                    "pe": p.get("pe"),
                    "pb": p.get("pb"),
                    "roe": p.get("roe"),
                    "market_cap": p.get("market_cap"),
                    "source_id": p.get("source_id"),
                }
            )

        sector_medians: dict[str, Any] = {
            "sector": sector,
            "median_pe": None,
            "median_pb": None,
            "n_pe": None,
            "n_pb": None,
            "pe_band": None,
            "pb_band": None,
        }
        stats_path = self.root / "data" / "valuation_sector_stats.json"
        if stats_path.is_file() and sector:
            try:
                stats = json.loads(stats_path.read_text(encoding="utf-8"))
                sec_map = stats.get("sectors") if isinstance(stats, dict) else None
                if isinstance(sec_map, dict) and sector in sec_map:
                    block = sec_map[sector] or {}
                    pe_sorted = [float(x) for x in (block.get("pe_sorted") or []) if isinstance(x, (int, float))]
                    pb_sorted = [float(x) for x in (block.get("pb_sorted") or []) if isinstance(x, (int, float))]
                    sector_medians.update(
                        {
                            "median_pe": block.get("median_pe"),
                            "median_pb": block.get("median_pb"),
                            "n_pe": block.get("n_pe"),
                            "n_pb": block.get("n_pb"),
                            "pe_band": _percentile_band(pe_sorted),
                            "pb_band": _percentile_band(pb_sorted),
                            "stats_as_of": stats.get("as_of"),
                            "stats_version": stats.get("version"),
                        }
                    )
            except (OSError, json.JSONDecodeError):
                pass

        return {
            "asof": self.asof,
            "disclaimer": DISCLAIMER,
            "symbol": symbol,
            "sector": sector,
            "items": items,
            "sector_medians": sector_medians,
        }

    def news(self, symbol: str, *, profile: str | None = None) -> dict[str, Any]:
        profile = profile or self.default_profile
        snap = self.load_snapshot(symbol)
        by_id = {
            str(n.get("id")): n
            for n in (snap.get("news") or [])
            if isinstance(n, dict) and n.get("id")
        }
        bundle = self.get_bundle(symbol, profile, debate_mode="template")
        m5 = bundle.get("m5") or {}
        items: list[dict[str, Any]] = []
        for ev in m5.get("evidence") or []:
            if not isinstance(ev, dict) or not ev.get("news_id"):
                continue
            nid = str(ev["news_id"])
            src_n = by_id.get(nid) or {}
            text = str(ev.get("text") or "")
            label = "trung tính"
            if text.startswith("tích cực"):
                label = "tích cực"
            elif text.startswith("tiêu cực"):
                label = "tiêu cực"
            title = text.split("|", 1)[-1].strip() if "|" in text else (src_n.get("title") or text)
            items.append(
                {
                    "id": nid,
                    "title": title or src_n.get("title"),
                    "label": label,
                    "source": src_n.get("source"),
                    "url": src_n.get("url"),
                    "published_at": src_n.get("published_at"),
                    "link": src_n.get("url"),
                }
            )
        classified = {it["id"] for it in items}
        raw: list[dict[str, Any]] = []
        for n in snap.get("news") or []:
            if not isinstance(n, dict) or not n.get("id") or str(n["id"]) in classified:
                continue
            url = n.get("url")
            label = "chưa phân loại"
            try:
                from stockai.m5_sentiment.run import classify_title

                pol, _m, _meta = classify_title(
                    str(n.get("title") or ""), symbol, source=str(n.get("source") or "")
                )
                label = "tích cực" if pol >= 0.1 else ("tiêu cực" if pol <= -0.1 else "trung tính")
            except Exception:  # noqa: BLE001
                pass
            raw.append(
                {
                    "id": str(n["id"]),
                    "title": n.get("title"),
                    "label": label,
                    "source": n.get("source"),
                    "url": url if isinstance(url, str) and url.startswith("http") else None,
                    "published_at": n.get("published_at"),
                }
            )
        raw.sort(key=lambda x: str(x.get("published_at") or ""), reverse=True)
        dates = [str(n.get("published_at") or "")[:10] for n in (snap.get("news") or []) if isinstance(n, dict)]
        return {
            "asof": self.asof,
            "disclaimer": DISCLAIMER,
            "symbol": symbol,
            "items": items,
            "other_items": raw[:30],
            "latest_news_date": max(dates) if dates and max(dates) else None,
            "total_news": len(snap.get("news") or []),
        }


def format_internal_error() -> dict[str, str]:
    """Lỗi nội bộ chung — không lộ traceback/đường dẫn."""
    _ = traceback.format_exc()  # nuốt để không in ra response
    return {"error": "Lỗi nội bộ", "detail": "Không thể xử lý yêu cầu."}
