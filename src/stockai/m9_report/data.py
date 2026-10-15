"""Gom dữ liệu cho báo cáo từ snapshot + upstream (M2-M8) + cfg; không tự ước lượng số.

Các phép tính ở đây chỉ là số học trên dữ liệu có sẵn (trung bình trượt từ giá snapshot,
vốn hóa = giá x số cổ phiếu, xếp hạng theo điểm M7 của cùng profile).
"""
from __future__ import annotations

import csv
import json
import math
from functools import lru_cache

import pandas as pd
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from stockai.m9_report.fmt import parse_date, to_float

PROFILES = ("long_term", "swing")


@lru_cache(maxsize=1)
def _listing_company_names() -> dict[str, dict[str, str]]:
    """Read full and display names from the repository's offline listing file."""
    path = Path(__file__).resolve().parents[3] / "config" / "listing_icb.csv"
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            return {
                str(row.get("Mã CK") or "").strip().upper(): {
                    "full_name": str(row.get("Tên Doanh Nghiệp") or "").strip(),
                    "short_name": str(row.get("Tên thương hiệu / Viết tắt") or "").strip(),
                }
                for row in rows
                if str(row.get("Mã CK") or "").strip()
            }
    except (OSError, csv.Error):
        return {}


def _cover_company_metadata(ticker: str, company: dict) -> dict:
    """Add offline full/display names for the cover without changing base fields."""
    result = dict(company)
    listing = _listing_company_names().get(str(ticker or "").upper(), {})
    if not any(result.get(key) for key in ("legal_name", "full_name", "company_full_name")):
        if listing.get("full_name"):
            result["full_name"] = listing["full_name"]
    if not result.get("short_name") and listing.get("short_name"):
        result["short_name"] = listing["short_name"]
    return result


def metric(mod: dict | None, name: str) -> float | None:
    if not isinstance(mod, dict) or not isinstance(mod.get("metrics"), dict):
        return None
    m = mod["metrics"].get(name)
    return to_float(m.get("value")) if isinstance(m, dict) else None


def metric_note(mod: dict | None, name: str) -> str | None:
    if not isinstance(mod, dict) or not isinstance(mod.get("metrics"), dict):
        return None
    m = mod["metrics"].get(name)
    return m.get("note") if isinstance(m, dict) else None


def rank_of(ticker: str, score: float | None, rows: list[tuple[str, float]]) -> tuple[int | None, int]:
    """Hạng theo điểm giảm dần, hòa điểm xếp theo mã (cùng quy tắc /api/rankings)."""
    s = to_float(score)
    pool = {t: float(v) for t, v in rows if to_float(v) is not None}
    if s is not None:
        pool[ticker] = s
    ordered = sorted(pool.items(), key=lambda kv: (-kv[1], kv[0]))
    if s is None:
        return None, len(ordered)
    for i, (t, _) in enumerate(ordered, start=1):
        if t == ticker:
            return i, len(ordered)
    return None, len(ordered)


def load_universe_from_cache(cache_dir: str | Path, asof: str, profile: str) -> list[tuple[str, float]]:
    """Đọc điểm M7 các mã đã xếp hạng từ cache API (data/api_cache); mỗi mã lấy file mới nhất."""
    d = Path(cache_dir)
    if not d.is_dir():
        return []
    newest: dict[str, tuple[float, Path]] = {}
    for p in d.glob(f"*_{asof}_{profile}_*.json"):
        if p.name.startswith("_"):
            continue
        ticker = p.name.split("_", 1)[0]
        mt = p.stat().st_mtime
        if ticker not in newest or mt > newest[ticker][0]:
            newest[ticker] = (mt, p)
    out: list[tuple[str, float]] = []
    for ticker, (_, p) in newest.items():
        try:
            b = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        m7 = b.get("m7") if isinstance(b, dict) else None
        if not isinstance(m7, dict):
            continue
        qg = m7.get("quality_gate") if isinstance(m7.get("quality_gate"), dict) else {}
        s = to_float(m7.get("score"))
        if qg.get("scored") is False or s is None:
            continue
        out.append((ticker, s))
    return out


def rolling_mean(vals: list[float], n: int) -> list[float | None]:
    out: list[float | None] = []
    acc = 0.0
    for i, v in enumerate(vals):
        acc += v
        if i >= n:
            acc -= vals[i - n]
        out.append(acc / n if i >= n - 1 else None)
    return out


_LIVE_NUM = ("price", "change", "change_pct", "volume", "prev_close")


def sanitize_live(raw: Any) -> dict:
    """Làm sạch khối realtime do API truyền vào (M9 không tự gọi mạng).

    Chỉ giữ số hữu hạn và chuỗi ngắn; thiếu giá thì trả {} để báo cáo dùng giá EOD.
    """
    if not isinstance(raw, dict):
        return {}

    def _fnum(v: Any) -> float | None:
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return f if math.isfinite(f) else None

    def _fstr(v: Any, n: int = 80) -> str | None:
        return str(v)[:n] if isinstance(v, str) and v.strip() else None

    out: dict = {"captured_at": _fstr(raw.get("captured_at")), "session_phase": _fstr(raw.get("session_phase"))}
    q = raw.get("quote")
    if isinstance(q, dict) and _fnum(q.get("price")) is not None and _fnum(q.get("price")) > 0:
        out["quote"] = {k: _fnum(q.get(k)) for k in _LIVE_NUM}
        out["quote"].update({k: _fstr(q.get(k)) for k in ("state", "basis", "label", "ts")})
    idx = raw.get("index")
    if isinstance(idx, dict) and _fnum(idx.get("price")) is not None:
        out["index"] = {"name": _fstr(idx.get("name")) or "VN-Index", "price": _fnum(idx.get("price")),
                        "change_pct": _fnum(idx.get("change_pct")),
                        "basis": _fstr(idx.get("basis")), "label": _fstr(idx.get("label"))}
    br = raw.get("breadth")
    if isinstance(br, dict) and all(_fnum(br.get(k)) is not None for k in ("up", "down")):
        out["breadth"] = {k: _fnum(br.get(k)) or 0.0 for k in ("up", "down", "flat")}
    return out if "quote" in out or "index" in out else {}


@dataclass
class ReportData:
    ticker: str
    as_of: str
    profile: str
    company: dict
    synthetic: bool
    m: dict[str, dict]
    m7: dict
    m8: dict
    scored: bool
    rows: list[dict]
    closes: list[float]
    dates: list[str]
    volumes: list[float]
    ma: dict[str, list[float | None]]
    ma_notes: list[str]
    annual: list[dict]
    quarterly: list[dict]
    tech_series: dict[str, list[float | None]]
    fin_unit: str | None
    fin_estimated: bool
    universe: list[tuple[str, float]]
    rank: int | None
    total: int
    other_profile: str | None
    other_score: float | None
    other_rank: int | None
    other_total: int
    debate_source: str
    debate_model: str | None
    bull: list
    bear: list
    sources: list[dict]
    news_by_id: dict[str, dict]
    news: list[dict]
    snapshot_flags: list[str]
    live: dict = field(default_factory=dict)
    tech_notes: list[str] = field(default_factory=list)

    @property
    def close(self) -> float | None:
        return metric(self.m.get("m3"), "close") or (self.closes[-1] if self.closes else None)

    @property
    def score(self) -> float | None:
        return to_float(self.m7.get("score"))

    @property
    def rating(self) -> str:
        return str(self.m7.get("rating") or "Không xếp hạng")

    @property
    def target(self) -> dict | None:
        t = self.m7.get("target")
        return t if isinstance(t, dict) else None

    def all_flags(self) -> list[str]:
        out: list[str] = []
        for f in self.snapshot_flags:
            out.append(f)
        for k in ("m2", "m3", "m4", "m5", "m6"):
            out += [f for f in (self.m.get(k) or {}).get("flags") or [] if isinstance(f, str)]
        out += [f for f in self.m7.get("flags") or [] if isinstance(f, str)]
        seen: set[str] = set()
        uniq = []
        for f in out:
            if f not in seen:
                seen.add(f)
                uniq.append(f)
        return uniq


def _as_dict(x: Any) -> dict:
    return x if isinstance(x, dict) else {}


def build_report_data(snapshot: dict, upstream: dict, cfg: dict, *, price_days: int = 252) -> ReportData:
    meta = _as_dict(snapshot.get("meta"))
    m7 = _as_dict(upstream.get("m7"))
    m8 = _as_dict(upstream.get("m8"))
    ticker = str(m7.get("ticker") or meta.get("ticker") or "N/A")
    as_of = str(m7.get("as_of") or meta.get("as_of") or "")
    profile = str(m7.get("profile") or cfg.get("profile") or "long_term")
    qg = _as_dict(m7.get("quality_gate"))
    scored = qg.get("scored") is not False and to_float(m7.get("score")) is not None

    asof_d = parse_date(as_of)
    raw_rows = list((_as_dict(snapshot.get("prices"))).get("rows") or [])
    rows = []
    for r in raw_rows:
        if not isinstance(r, dict):
            continue
        d = parse_date(r.get("date"))
        if d is None or (asof_d is not None and d > asof_d) or to_float(r.get("close")) is None:
            continue
        rows.append(r)
    all_closes = [float(r["close"]) for r in rows]
    ma_full = {
        "MA20": rolling_mean(all_closes, 20),
        "MA50": rolling_mean(all_closes, 50),
        "MA200": rolling_mean(all_closes, 200),
    }
    tail = rows[-max(1, int(price_days)):]
    k0 = len(rows) - len(tail)
    ma = {k: v[k0:] for k, v in ma_full.items()}
    # đối chiếu MA cuối với M3; lệch thì không vẽ đường đó
    m3 = _as_dict(upstream.get("m3"))
    ma_notes: list[str] = []
    for key, mk in (("MA20", "ma20"), ("MA50", "ma50"), ("MA200", "ma200")):
        ref = metric(m3, mk)
        last = ma[key][-1] if ma[key] else None
        if ref is None or last is None or abs(ref - last) > max(0.5, abs(ref) * 1e-6):
            ma_notes.append(f"{key}: không khớp hoặc thiếu giá trị M3, không vẽ")
            ma[key] = []

    fin = _as_dict(snapshot.get("financials"))
    annual = []
    for a in fin.get("annual") or []:
        if not isinstance(a, dict):
            continue
        pd_ = parse_date(a.get("published_at"))
        if asof_d is not None and pd_ is not None and pd_ > asof_d:
            continue
        annual.append(a)
    annual = sorted(annual, key=lambda a: str(a.get("period")))[-5:]
    fin_estimated = any(bool(a.get("published_at_estimated")) for a in annual)

    quarterly = []
    for q in fin.get("quarterly") or []:
        if not isinstance(q, dict):
            continue
        pd_ = parse_date(q.get("published_at"))
        if asof_d is not None and pd_ is not None and pd_ > asof_d:
            continue
        quarterly.append(q)
    quarterly = sorted(quarterly, key=lambda q: str(q.get("period")))[-8:]

    # Chuỗi RSI/MACD dùng đúng công thức và tham số của M3. Chỉ phục vụ trực quan hóa;
    # giá trị cuối được đối chiếu với output M3 ở layout trước khi hiển thị.
    tech_series: dict[str, list[float | None]] = {"rsi14": [], "macd": [], "macd_signal": [], "macd_histogram": []}
    try:
        from stockai.m3_technical.run import _load_m3_cfg

        m3_cfg, _ = _load_m3_cfg(cfg)
        rsi_period = int(m3_cfg.get("rsi_period", 14))
        macd_cfg = m3_cfg.get("macd") or {}
        macd_fast = int(macd_cfg.get("fast", 12))
        macd_slow = int(macd_cfg.get("slow", 26))
        macd_signal_span = int(macd_cfg.get("signal", 9))
        if rows:
            closes_s = pd.Series(all_closes, dtype=float)
            change = closes_s.diff()
            gain = change.clip(lower=0).fillna(0.0)
            loss = (-change.clip(upper=0)).fillna(0.0)
            avg_gain = gain.ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
            avg_loss = loss.ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
            rs = avg_gain / avg_loss.replace(0, float("nan"))
            rsi = 100 - 100 / (1 + rs)
            # Đồng bộ trường hợp không có loss với M3.
            mask_zero = avg_loss == 0
            rsi.loc[mask_zero & (avg_gain > 0)] = 100.0
            rsi.loc[mask_zero & (avg_gain <= 0)] = 50.0
            ema_fast = closes_s.ewm(span=macd_fast, adjust=False).mean()
            ema_slow = closes_s.ewm(span=macd_slow, adjust=False).mean()
            macd_s = ema_fast - ema_slow
            signal_s = macd_s.ewm(span=macd_signal_span, adjust=False).mean()
            hist_s = macd_s - signal_s
            def tail_list(series):
                vals = series.iloc[k0:].tolist()
                return [float(v) if v is not None and not pd.isna(v) and math.isfinite(float(v)) else None for v in vals]
            tech_series = {
                "rsi14": tail_list(rsi),
                "macd": tail_list(macd_s),
                "macd_signal": tail_list(signal_s),
                "macd_histogram": tail_list(hist_s),
            }
    except Exception:
        pass

    universe = list(cfg.get("universe_scores") or [])
    if not universe and cfg.get("api_cache_dir"):
        universe = load_universe_from_cache(cfg["api_cache_dir"], as_of, profile)
    universe = [(str(t), float(s)) for t, s in universe if to_float(s) is not None]
    rank, total = rank_of(ticker, m7.get("score") if scored else None, universe) if universe else (None, 0)

    other = next((p for p in PROFILES if p != profile), None)
    other_m7 = _as_dict(_as_dict(cfg.get("other_profile")).get("m7"))
    other_score = to_float(other_m7.get("score")) if _as_dict(other_m7.get("quality_gate")).get("scored") is not False else None
    other_universe = [(str(t), float(s)) for t, s in (_as_dict(cfg.get("other_profile")).get("universe_scores") or [])
                      if to_float(s) is not None]
    o_rank, o_total = rank_of(ticker, other_score, other_universe) if other_universe and other_score is not None else (None, 0)

    deb = _as_dict(cfg.get("debate"))
    if deb.get("source") in ("CACHE", "LLM") and isinstance(deb.get("bull"), list) and isinstance(deb.get("bear"), list):
        debate_source, bull, bear = "CACHE", list(deb["bull"]), list(deb["bear"])
        debate_model = deb.get("model")
    else:
        # Luôn dựng lại template khi xuất PDF để nhận wording mới (không phụ thuộc cache API cũ)
        debate_source, debate_model = "TEMPLATE", None
        bull, bear = list(m7.get("bull") or []), list(m7.get("bear") or [])
        try:
            from stockai.llm.payload import build_debate_payload
            from stockai.m7_scoring.debate_template import build_template_debate

            # cfg API thường thiếu scoring.yaml → polarity = 0; bổ sung từ file + contributions M7
            cfg_debate = dict(cfg)
            if not isinstance(cfg_debate.get("profiles"), dict):
                try:
                    import yaml

                    from stockai.m9_report.theme import ROOT as _ROOT

                    sc = yaml.safe_load((_ROOT / "config" / "scoring.yaml").read_text(encoding="utf-8")) or {}
                    if isinstance(sc, dict):
                        cfg_debate = {**sc, **cfg_debate}
                except OSError:
                    pass
            payload = build_debate_payload(
                snapshot,
                {k: upstream.get(k) for k in ("m2", "m3", "m4", "m5", "m6")},
                cfg_debate,
                score=to_float(m7.get("score")),
                rating=str(m7.get("rating") or "") or None,
                scores=m7.get("scores") if isinstance(m7.get("scores"), dict) else None,
            )
            contrib = m7.get("contributions") if isinstance(m7.get("contributions"), dict) else {}
            if contrib:
                pol = {}
                for k in ("F", "T", "V", "S", "R"):
                    v = to_float(contrib.get(k))
                    if v is not None:
                        pol[k] = round(v, 2)
                if pol:
                    payload["module_polarity"] = pol
            tb, te, _ = build_template_debate(payload, cfg=cfg_debate)
            if tb and te:
                bull, bear = tb, te
        except Exception:
            pass

    news_list = [n for n in snapshot.get("news") or [] if isinstance(n, dict)]
    news_by_id = {str(n.get("id")): n for n in news_list if n.get("id")}
    return ReportData(
        ticker=ticker,
        as_of=as_of,
        profile=profile,
        company=_cover_company_metadata(ticker, _as_dict(snapshot.get("company"))),
        synthetic=bool(meta.get("synthetic")),
        m={k: _as_dict(upstream.get(k)) for k in ("m2", "m3", "m4", "m5", "m6")},
        m7=m7,
        m8=m8,
        scored=scored,
        rows=tail,
        closes=[float(r["close"]) for r in tail],
        dates=[str(r.get("date"))[:10] for r in tail],
        volumes=[to_float(r.get("volume")) or 0.0 for r in tail],
        ma=ma,
        ma_notes=ma_notes,
        annual=annual,
        quarterly=quarterly,
        tech_series=tech_series,
        fin_unit=fin.get("unit"),
        fin_estimated=fin_estimated,
        universe=universe,
        rank=rank,
        total=total,
        other_profile=other if other_score is not None else None,
        other_score=other_score,
        other_rank=o_rank,
        other_total=o_total,
        debate_source=debate_source,
        debate_model=debate_model,
        bull=bull,
        bear=bear,
        sources=[s for s in snapshot.get("sources") or [] if isinstance(s, dict)],
        news_by_id=news_by_id,
        news=news_list,
        snapshot_flags=[f for f in meta.get("flags") or [] if isinstance(f, str)],
        live=sanitize_live(cfg.get("live")),
    )
