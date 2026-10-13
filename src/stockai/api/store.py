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
        for p in self.snapshots_dir.glob("*_????-??-??.json"):
            if p.name.startswith("_"):
                continue
            stem = p.stem
            if "_" not in stem:
                continue
            d = stem.rsplit("_", 1)[-1]
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                dates.append(d)
        return max(dates) if dates else datetime.utcnow().strftime("%Y-%m-%d")

    def _build_index(self) -> dict[str, Path]:
        if self._ticker_index is not None:
            return self._ticker_index
        idx: dict[str, Path] = {}
        asof = self.asof
        if self.snapshots_dir.is_dir():
            for p in self.snapshots_dir.glob(f"*_{asof}.json"):
                if p.name.startswith("_"):
                    continue
                ticker = p.name[: -(len(asof) + 6)]  # strip _YYYY-MM-DD.json
                if is_valid_symbol(ticker):
                    idx[ticker] = p
        self._ticker_index = idx
        return idx

    def list_tickers(self) -> list[str]:
        return sorted(self._build_index().keys())

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
        m7 = bundle.get("m7") or {}
        company = bundle.get("company") or {}
        scores = m7.get("scores") if isinstance(m7.get("scores"), dict) else {}
        qg = m7.get("quality_gate") if isinstance(m7.get("quality_gate"), dict) else {}
        scored = qg.get("scored") is not False and m7.get("score") is not None
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
            "ranked": bool(scored),
            "quality_gate": qg,
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
                        company = snap.get("company") if isinstance(snap.get("company"), dict) else {}
                        rows.append(
                            {
                                "ticker": ticker,
                                "name": company.get("name"),
                                "sector": company.get("sector"),
                                "exchange": company.get("exchange"),
                                "score": None,
                                "rating": "Không xếp hạng",
                                "scores": {"F": None, "T": None, "V": None, "S": None, "R": None},
                                "ranked": False,
                                "quality_gate": {
                                    "tier": "insufficient",
                                    "scored": False,
                                    "reasons": [],
                                },
                            }
                        )
                        continue
                bundle = self.get_bundle(ticker, profile, debate_mode="template")
                rows.append(self.ranking_row(bundle))
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
        limit = max(1, min(500, int(limit)))
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
        return {"total": total, "items": page, "asof": self.asof, "disclaimer": DISCLAIMER}

    def sectors(self) -> dict[str, Any]:
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
        items = [
            {"sector": k, "count": v, "label": k}
            for k, v in sorted(counts.items(), key=lambda x: (-x[1], x[0]))
        ]
        return {"asof": self.asof, "disclaimer": DISCLAIMER, "items": items}

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
    ) -> dict[str, Any]:
        profile = profile or self.default_profile
        snap = self.load_snapshot(symbol)
        rows = list(((snap.get("prices") or {}).get("rows") or []))
        asof = self.asof
        if rows and range_key != "all":
            # 3m≈63, 6m≈126, 1y≈252 phiên giao dịch gần đúng
            n_map = {"3m": 63, "6m": 126, "1y": 252}
            n = n_map.get(range_key, 63)
            rows = rows[-n:]

        # MA từ M3 metrics (giá trị cuối) — không tính lại chuỗi MA trong API
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

        ohlcv = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            ohlcv.append(
                {
                    "time": r.get("date"),
                    "open": r.get("open"),
                    "high": r.get("high"),
                    "low": r.get("low"),
                    "close": r.get("close"),
                    "volume": r.get("volume"),
                }
            )
        return {
            "asof": asof,
            "disclaimer": DISCLAIMER,
            "symbol": symbol,
            "range": range_key,
            "ohlcv": ohlcv,
            "ma20": ma20,
            "ma50": ma50,
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
        return {
            "asof": self.asof,
            "disclaimer": DISCLAIMER,
            "symbol": symbol,
            "items": items,
        }


def format_internal_error() -> dict[str, str]:
    """Lỗi nội bộ chung — không lộ traceback/đường dẫn."""
    _ = traceback.format_exc()  # nuốt để không in ra response
    return {"error": "Lỗi nội bộ", "detail": "Không thể xử lý yêu cầu."}
