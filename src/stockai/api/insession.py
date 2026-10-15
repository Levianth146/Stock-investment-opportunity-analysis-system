"""Phân tích trong phiên (tạm tính) — chỉ nhóm liquid; số gắn basis live|eod."""
from __future__ import annotations

import math
from typing import Any

from stockai.api.realtime import QuoteTick, RealtimeHub

# GTGD tối thiểu cho movers (VND/ngày)
MIN_VALUE_TRADED = 1_000_000_000.0  # 1 tỷ


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x or math.isinf(x):
        return None
    return x


def _sma(closes: list[float], n: int) -> float | None:
    if len(closes) < n or n <= 0:
        return None
    window = closes[-n:]
    return sum(window) / n


def _rsi14(closes: list[float], period: int = 14) -> float | None:
    if len(closes) < period + 1:
        return None
    gains = 0.0
    losses = 0.0
    for i in range(-period, 0):
        d = closes[i] - closes[i - 1]
        if d >= 0:
            gains += d
        else:
            losses -= d
    avg_gain = gains / period
    avg_loss = losses / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def _avg_vol(volumes: list[float], n: int = 20) -> float | None:
    if len(volumes) < n:
        return None
    window = volumes[-n:]
    if not window:
        return None
    return sum(window) / len(window)


def _closes_vols(snap: dict) -> tuple[list[float], list[float], list[float], list[float]]:
    """Trả (closes, highs, lows, volumes) từ prices.rows."""
    rows = ((snap.get("prices") or {}).get("rows") or []) if isinstance(snap, dict) else []
    closes: list[float] = []
    highs: list[float] = []
    lows: list[float] = []
    vols: list[float] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        c = _num(r.get("close"))
        if c is None:
            continue
        closes.append(c)
        h = _num(r.get("high"))
        l = _num(r.get("low"))
        v = _num(r.get("volume"))
        highs.append(h if h is not None else c)
        lows.append(l if l is not None else c)
        vols.append(v if v is not None else 0.0)
    return closes, highs, lows, vols


_STATIC_CACHE: dict[str, Any] = {"asof": None, "by_sym": {}}


def _static_for(store: Any, sym: str) -> dict[str, Any] | None:
    """Chỉ số tĩnh theo (asof, mã): SMA/RSI/TB20/52w/ngành/CP lưu hành — tính 1 lần, không đọc lại file."""
    asof = getattr(store, "asof", None)
    if _STATIC_CACHE["asof"] != asof:
        _STATIC_CACHE["asof"] = asof
        _STATIC_CACHE["by_sym"] = {}
    by_sym: dict[str, Any] = _STATIC_CACHE["by_sym"]
    if sym in by_sym:
        return by_sym[sym]
    try:
        snap = store.load_snapshot(sym)
    except Exception:  # noqa: BLE001
        return None
    closes, highs, lows, vols = _closes_vols(snap)
    company = snap.get("company") if isinstance(snap.get("company"), dict) else {}
    hi = lo = None
    if highs and lows:
        hi = max(highs[-252:]) if len(highs) >= 20 else max(highs)
        lo = min(lows[-252:]) if len(lows) >= 20 else min(lows)
    st = {
        "sma50": _sma(closes, 50),
        "sma200": _sma(closes, 200),
        "avg20": _avg_vol(vols, 20),
        "rsi": _rsi14(closes, 14),
        "hi": hi,
        "lo": lo,
        "last_vol": vols[-1] if vols else None,
        "sector": company.get("sector") or "Khác",
        "shares": _num(company.get("shares_outstanding")),
    }
    by_sym[sym] = st
    return st


def _live_valuation(
    snap: dict,
    price: float | None,
    *,
    as_of_ts: str,
    basis: str,
) -> dict[str, Any]:
    """P/E, P/B, dividend yield tạm tính từ giá live × fundamentals EOD."""
    company = snap.get("company") if isinstance(snap.get("company"), dict) else {}
    shares = _num(company.get("shares_outstanding"))
    fin = snap.get("financials") if isinstance(snap.get("financials"), dict) else {}
    annual = [p for p in (fin.get("annual") or []) if isinstance(p, dict)]
    items: dict = {}
    if annual:
        annual_sorted = sorted(annual, key=lambda p: str(p.get("period") or ""))
        items = annual_sorted[-1].get("items") if isinstance(annual_sorted[-1].get("items"), dict) else {}

    nip = _num(items.get("net_income_parent"))
    if nip is None:
        nip = _num(items.get("net_income"))
    equity = _num(items.get("total_equity"))
    div = _num(items.get("dividends_paid"))
    eps = _num(items.get("eps"))

    mcap = (price * shares) if (price is not None and shares is not None) else None
    pe = None
    if price is not None and eps is not None and eps != 0:
        pe = price / eps
    elif mcap is not None and nip is not None and nip != 0:
        pe = mcap / nip
    pb = None
    if mcap is not None and equity is not None and equity != 0:
        pb = mcap / equity
    dy = None
    if mcap is not None and div is not None and mcap != 0:
        dy = abs(div) / mcap

    return {
        "price": {"value": price, "as_of_ts": as_of_ts, "basis": basis},
        "market_cap": {"value": mcap, "as_of_ts": as_of_ts, "basis": basis},
        "pe": {"value": pe, "as_of_ts": as_of_ts, "basis": basis},
        "pb": {"value": pb, "as_of_ts": as_of_ts, "basis": basis},
        "dividend_yield": {"value": dy, "as_of_ts": as_of_ts, "basis": basis},
        "sector_ref": {
            "value": None,
            "unreliable": False,
            "as_of_ts": as_of_ts,
            "basis": "eod",
        },
        "label": "tạm tính",
    }


def _fmt_ddmm(asof: str | None) -> str:
    if not asof or len(str(asof)) < 10:
        return "—"
    s = str(asof)
    return f"{s[8:10]}/{s[5:7]}"


_MARKET_CACHE: dict[str, Any] = {"asof": None, "val": None}


def _eod_market(store: Any) -> dict:
    """store.market() đọc nhiều snapshot — cache theo asof (EOD không đổi trong phiên)."""
    if not hasattr(store, "market"):
        return {}
    asof = getattr(store, "asof", None)
    if _MARKET_CACHE["asof"] != asof or _MARKET_CACHE["val"] is None:
        _MARKET_CACHE["val"] = store.market()
        _MARKET_CACHE["asof"] = asof
    return _MARKET_CACHE["val"]


def _eod_prior_close(eod_idx: dict | None) -> float | None:
    """Đóng cửa phiên trước từ series_eod (điểm cuối = phiên đóng gần nhất)."""
    if not isinstance(eod_idx, dict):
        return None
    series = eod_idx.get("series_30d")
    if isinstance(series, list) and series:
        last = series[-1]
        if isinstance(last, dict):
            return _num(last.get("close"))
    return _num(eod_idx.get("prev_close")) or _num(eod_idx.get("close"))


def _build_index_block(hub: RealtimeHub, store: Any, as_of_ts: str) -> dict[str, Any]:
    """VN-Index từ kênh T=mi hoặc EOD snapshot; không bịa VN30/HNX.

    Có mi → basis=live, candles_1m ≥1, prev_close = priorValueIndexes hoặc series_eod.
    Ngoài giờ: vẫn hiện nến phiên gần nhất nếu còn trong RAM.
    """
    avail = hub.available_indices()
    live_q = hub.get_index_quote("VNINDEX")
    candles = hub.candles("VNINDEX") if live_q else []
    eod = _eod_market(store)
    eod_idx = eod.get("index") if isinstance(eod, dict) else None
    series_eod = (eod_idx or {}).get("series_30d") if isinstance(eod_idx, dict) else None
    prior_eod = _eod_prior_close(eod_idx if isinstance(eod_idx, dict) else None)

    closed_now = hub.session_now().phase == "closed"
    close_day = hub.session_close_date()
    # Có quote từ mi (không phụ thuộc cờ subscribe _index_ok — tránh mất live khi reconnect).
    # Ngoài giờ chỉ dùng khi hub giữ phiên mới hơn snapshot EOD; ngược lại lùi về EOD.
    if live_q and live_q.price is not None and (not closed_now or close_day):
        if live_q.prev_close is None and prior_eod is not None:
            hub.set_index_prev_from_eod("VNINDEX", prior_eod)
            live_q = hub.get_index_quote("VNINDEX") or live_q
        prev_val = live_q.prev_close if live_q.prev_close is not None else prior_eod
        chg = live_q.change_pct
        if chg is None and prev_val is not None and prev_val != 0 and live_q.price is not None:
            chg = (live_q.price - prev_val) / prev_val * 100.0
        basis = live_q.basis if live_q.basis == "live" or candles else "live"
        if live_q.state == "closed" and not candles:
            basis = "eod"
        label = (
            "trực tiếp (tạm tính)"
            if basis == "live" and live_q.state in ("live", "stale")
            else f"đóng cửa {_fmt_ddmm(store.asof)}"
        )
        if closed_now and close_day:
            basis = "close"
            label = f"đóng cửa {_fmt_ddmm(close_day)} (tạm tính)"
        idx_val = hub.get_index_value("VNINDEX")
        out: dict[str, Any] = {
            "symbol": "VNINDEX",
            "name": "VN-Index",
            "price": {"value": live_q.price, "as_of_ts": as_of_ts, "basis": basis},
            "prev_close": {"value": prev_val, "as_of_ts": as_of_ts, "basis": "eod"},
            "change_pct": {
                "value": chg,
                "as_of_ts": as_of_ts,
                "basis": basis,
            },
            "candles_1m": candles,
            "series_eod": series_eod,
            "available": avail or ["VNINDEX"],
            "label": label,
            "source": "realtime" if basis in ("live", "close") else "eod",
        }
        if live_q.volume is not None:
            out["volume"] = {
                "value": live_q.volume,
                "as_of_ts": as_of_ts,
                "basis": basis,
            }
        if idx_val is not None:
            out["value"] = {
                "value": idx_val,
                "as_of_ts": as_of_ts,
                "basis": basis,
                "unit": "tỷ VND",
            }
        return out

    # Fallback EOD — chỉ VN-Index
    if isinstance(eod_idx, dict) and eod_idx.get("close") is not None:
        prev_eod = None
        series = eod_idx.get("series_30d")
        if isinstance(series, list) and len(series) >= 2 and isinstance(series[-2], dict):
            prev_eod = _num(series[-2].get("close"))
        if prev_eod is None:
            prev_eod = _num(eod_idx.get("prev_close"))
        return {
            "symbol": "VNINDEX",
            "name": "VN-Index",
            "price": {
                "value": eod_idx.get("close"),
                "as_of_ts": as_of_ts,
                "basis": "eod",
            },
            "prev_close": {
                "value": prev_eod,
                "as_of_ts": as_of_ts,
                "basis": "eod",
            },
            "change_pct": {
                "value": eod_idx.get("change_pct"),
                "as_of_ts": as_of_ts,
                "basis": "eod",
            },
            "candles_1m": [],
            "series_eod": eod_idx.get("series_30d"),
            "available": ["VNINDEX"],
            "label": f"đóng cửa {_fmt_ddmm(eod_idx.get('asof_session') or store.asof)}",
            "source": "eod",
        }
    return {
        "symbol": "VNINDEX",
        "name": "VN-Index",
        "price": {"value": None, "as_of_ts": as_of_ts, "basis": "eod"},
        "prev_close": {"value": None, "as_of_ts": as_of_ts, "basis": "eod"},
        "change_pct": {"value": None, "as_of_ts": as_of_ts, "basis": "eod"},
        "candles_1m": [],
        "series_eod": None,
        "available": [],
        "label": "EOD",
        "source": "none",
    }


def build_market_analysis(
    hub: RealtimeHub, store: Any, *, include_valuation: bool = True
) -> dict[str, Any]:
    """Tạo payload GET /api/realtime/market — breadth, lists, heatmap, valuation mẫu."""
    sess = hub.session_now()
    as_of_ts = sess.as_of_ts
    frac = max(sess.session_fraction, 0.05)
    session_open = sess.phase != "closed"
    close_day = hub.session_close_date()  # ngày của giá chốt phiên chưa có EOD (hoặc None)

    up = down = flat = unmatched = 0
    excluded_no_ref = 0
    above_sma50 = below_sma50 = 0
    above_sma200 = below_sma200 = 0
    hit_52w_hi = hit_52w_lo = 0
    liquid_n = 0

    strong_up: list[dict] = []
    strong_down: list[dict] = []
    vol_spike: list[dict] = []
    hi52: list[dict] = []
    lo52: list[dict] = []
    overbought: list[dict] = []
    oversold: list[dict] = []
    heatmap: list[dict] = []

    for q in hub.iter_liquid_quotes():
        liquid_n += 1
        sym = q.symbol
        st = _static_for(store, sym)
        if st is None:
            continue
        price = q.price
        basis = q.basis if (q.state in ("live", "stale") or q.basis == "close") else "eod"
        chg = q.change_pct
        has_ref = (
            getattr(q, "prev_close_source", "none") in ("tick", "snapshot")
            and q.prev_close is not None
        )
        # "Đã khớp" = có tick thật trong phiên này (stale không tick ≠ đứng giá).
        traded = hub.has_traded_session(sym)

        # Breadth 4 nhóm: up/down/flat/unmatched — tổng = liquid
        if session_open and not traded:
            unmatched += 1
        elif not has_ref:
            excluded_no_ref += 1
            flat += 1  # vẫn nằm trong 4 nhóm (flat khi thiếu %)
        elif chg is not None:
            if chg > 0.05:
                up += 1
            elif chg < -0.05:
                down += 1
            else:
                flat += 1
        else:
            flat += 1

        sma50 = st["sma50"]
        sma200 = st["sma200"]
        if price is not None and sma50 is not None:
            if price >= sma50:
                above_sma50 += 1
            else:
                below_sma50 += 1
        if price is not None and sma200 is not None:
            if price >= sma200:
                above_sma200 += 1
            else:
                below_sma200 += 1

        avg20 = st["avg20"]
        # % / Vol tương đối: chỉ khi live (hoặc phiên đóng hợp lệ); không bịa +0% khi thiếu stream
        metrics_ok = (not session_open) or traded
        if not metrics_ok:
            chg = None

        # KL hôm nay: trong phiên chỉ lấy từ tick (totalVolumeTraded đã × lot→CP).
        # Không tick → relative_vol=null, không vào volume_spike (không dùng EOD làm "hôm nay").
        today_vol: float | None = None
        rel_vol: float | None = None
        rel_vol_label: str | None = None
        vol_ratio: float | None = None
        if session_open:
            if traded and q.volume is not None:
                today_vol = float(q.volume)
                if avg20 and avg20 > 0 and frac > 0:
                    # KL luỹ kế / (TB20 × phần phiên đã trôi) — frac đồng hồ = "ước tính"
                    expected = avg20 * frac
                    vol_ratio = today_vol / expected if expected > 0 else None
                    rel_vol = round(vol_ratio, 2) if vol_ratio is not None else None
                    rel_vol_label = "ước tính"
        else:
            # Ngoài giờ: KL/TB20 nguyên phiên, không nhân session_fraction
            today_vol = float(q.volume) if q.volume is not None else st["last_vol"]
            if avg20 and avg20 > 0 and today_vol is not None:
                rel_vol = round(today_vol / avg20, 2)
                rel_vol_label = f"phiên {_fmt_ddmm(close_day or store.asof)}, KL/TB20"

        # GTGD ngày (ước lượng) — trong phiên chỉ mã đã khớp
        value_traded = None
        if price is not None and today_vol is not None:
            value_traded = price * today_vol
        liquid_ok = value_traded is not None and value_traded >= MIN_VALUE_TRADED

        if st["hi"] is not None and st["lo"] is not None and price is not None:
            hi = st["hi"]
            lo = st["lo"]
            if price >= hi * 0.999:
                hit_52w_hi += 1
                if liquid_ok:
                    hi52.append(
                        _row(
                            sym, price, chg, as_of_ts, basis,
                            rel_vol=rel_vol, rel_vol_label=rel_vol_label,
                        )
                    )
            if price <= lo * 1.001:
                hit_52w_lo += 1
                if liquid_ok:
                    lo52.append(
                        _row(
                            sym, price, chg, as_of_ts, basis,
                            rel_vol=rel_vol, rel_vol_label=rel_vol_label,
                        )
                    )

        if liquid_ok and has_ref:
            if chg is not None and chg >= 3.0:
                strong_up.append(
                    _row(
                        sym, price, chg, as_of_ts, basis,
                        rel_vol=rel_vol, rel_vol_label=rel_vol_label,
                    )
                )
            if chg is not None and chg <= -3.0:
                strong_down.append(
                    _row(
                        sym, price, chg, as_of_ts, basis,
                        rel_vol=rel_vol, rel_vol_label=rel_vol_label,
                    )
                )

            # volume_spike: chỉ mã có tick hôm nay; ngưỡng ≥2× (KL / (TB20×frac))
            if (
                session_open
                and traded
                and vol_ratio is not None
                and vol_ratio >= 2.0
            ):
                vol_spike.append(
                    {
                        **_row(
                            sym, price, chg, as_of_ts, basis,
                            rel_vol=rel_vol, rel_vol_label=rel_vol_label,
                        ),
                        "vol_ratio": round(vol_ratio, 2),
                        "session_fraction": round(frac, 4),
                        "session_fraction_label": "ước tính",
                    }
                )

        rsi = st["rsi"]
        if rsi is not None and liquid_ok:
            if rsi >= 70:
                overbought.append(
                    {**_row(sym, price, chg, as_of_ts, "eod", rel_vol=rel_vol), "rsi14": round(rsi, 2)}
                )
            elif rsi <= 30:
                oversold.append(
                    {**_row(sym, price, chg, as_of_ts, "eod", rel_vol=rel_vol), "rsi14": round(rsi, 2)}
                )

        sector = st["sector"]
        shares = st["shares"]
        mcap = (price * shares) if (price is not None and shares is not None) else None
        ref_px = q.prev_close if q.prev_close is not None else price
        mcap_ref = (ref_px * shares) if (ref_px is not None and shares is not None) else None
        if not metrics_ok:
            hm_label = "chưa có giá trực tiếp"
            hm_chg: float | None = None
        elif has_ref:
            hm_label = "tạm tính"
            hm_chg = chg
        else:
            hm_label = "chưa có giá tham chiếu"
            hm_chg = None
        heatmap.append(
            {
                "symbol": sym,
                "sector": sector,
                "change_pct": {
                    "value": hm_chg,
                    "as_of_ts": as_of_ts,
                    "basis": basis,
                },
                "market_cap": {
                    "value": mcap,
                    "as_of_ts": as_of_ts,
                    "basis": basis,
                },
                "market_cap_ref": mcap_ref,
                "label": hm_label,
            }
        )

    def _top(rows: list[dict], key: str = "change_pct", n: int = 10, reverse: bool = True) -> list[dict]:
        def _k(r: dict) -> float:
            v = r.get(key)
            if isinstance(v, dict):
                v = v.get("value")
            try:
                return float(v) if v is not None else float("-inf" if reverse else "inf")
            except (TypeError, ValueError):
                return float("-inf" if reverse else "inf")

        return sorted(rows, key=_k, reverse=reverse)[:n]

    sample_vals: list[dict] = []
    sample_syms = list(hub._liquid)[:12] if include_valuation else []  # noqa: SLF001
    for sym in sample_syms:
        try:
            snap = store.load_snapshot(sym)
        except Exception:  # noqa: BLE001
            continue
        q = hub.get_quote(sym)
        sample_vals.append(
            {
                "symbol": sym,
                **_live_valuation(
                    snap,
                    q.price,
                    as_of_ts=as_of_ts,
                    basis=q.basis if (q.state in ("live", "stale") or q.basis == "close") else "eod",
                ),
            }
        )

    status = hub.status()
    live_basis = "live" if status["mode"] == "live" else ("close" if close_day else "eod")
    breadth_sum = up + down + flat + unmatched
    index_block = _build_index_block(hub, store, as_of_ts)

    return {
        "asof": store.asof,
        "as_of_ts": as_of_ts,
        "label": (
            "trực tiếp (tạm tính)"
            if status["mode"] == "live"
            else (
                status.get("label")
                if status["mode"] in ("connecting", "stale", "unit_mismatch")
                else (
                    f"đóng cửa {_fmt_ddmm(close_day)} (tạm tính)"
                    if close_day
                    else f"đóng cửa {_fmt_ddmm(store.asof)}"
                )
            )
        ),
        "session": status["session"],
        "realtime": {
            "mode": status["mode"],
            "state": status["state"],
        },
        "index": index_block,
        "breadth": {
            "up": {"value": up, "as_of_ts": as_of_ts, "basis": live_basis},
            "down": {"value": down, "as_of_ts": as_of_ts, "basis": live_basis},
            "flat": {"value": flat, "as_of_ts": as_of_ts, "basis": live_basis},
            "unmatched": {
                "value": unmatched,
                "as_of_ts": as_of_ts,
                "basis": live_basis,
                "label": "Chưa khớp",
            },
            "excluded_no_ref": {
                "value": excluded_no_ref,
                "as_of_ts": as_of_ts,
                "basis": "eod",
            },
            "liquid_count": liquid_n,
            "sum": breadth_sum,
            "above_sma50": {"value": above_sma50, "as_of_ts": as_of_ts, "basis": "eod"},
            "below_sma50": {"value": below_sma50, "as_of_ts": as_of_ts, "basis": "eod"},
            "above_sma200": {"value": above_sma200, "as_of_ts": as_of_ts, "basis": "eod"},
            "below_sma200": {"value": below_sma200, "as_of_ts": as_of_ts, "basis": "eod"},
            "hit_52w_high": {
                "value": hit_52w_hi,
                "as_of_ts": as_of_ts,
                "basis": live_basis,
                "label": "EOD hoặc hiện tại",
            },
            "hit_52w_low": {
                "value": hit_52w_lo,
                "as_of_ts": as_of_ts,
                "basis": live_basis,
                "label": "EOD hoặc hiện tại",
            },
            "note": (
                f"Trên {liquid_n} mã thanh khoản đủ (nhóm liquid). "
                "Tăng/Giảm/Đứng/Chưa khớp cộng đúng tổng. "
                "SMA/RSI từ EOD; % chỉ khi có giá tham chiếu."
            ),
        },
        "lists": {
            "strong_up": _top(strong_up, reverse=True),
            "strong_down": _top(strong_down, reverse=False),
            "volume_spike": _top(vol_spike, key="vol_ratio", reverse=True),
            "high_52w": hi52[:10],
            "low_52w": lo52[:10],
            "overbought": overbought[:10],
            "oversold": oversold[:10],
            "liquidity_note": "Lọc GTGD ≥ 1 tỷ đồng/ngày",
            "max_rows": 10,
        },
        "heatmap": heatmap,
        "valuation_sample": sample_vals,
        "disclaimer": (
            "Phân tích trong phiên mang tính tạm tính. "
            "Điểm số M2–M7 không dùng giá tick."
        ),
    }


def _row(
    symbol: str,
    price: float | None,
    change_pct: float | None,
    as_of_ts: str,
    basis: str,
    *,
    rel_vol: float | None = None,
    rel_vol_label: str | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "symbol": symbol,
        "price": {"value": price, "as_of_ts": as_of_ts, "basis": basis},
        "change_pct": {"value": change_pct, "as_of_ts": as_of_ts, "basis": basis},
        "label": "tạm tính",
    }
    if rel_vol is not None:
        rv: dict[str, Any] = {
            "value": rel_vol,
            "as_of_ts": as_of_ts,
            "basis": basis,
        }
        if rel_vol_label:
            rv["label"] = rel_vol_label
        out["relative_vol"] = rv
    return out


def compute_breadth_from_quotes(
    quotes: list[QuoteTick],
    *,
    flat_eps: float = 0.05,
    traded: set[str] | None = None,
    session_open: bool = False,
) -> dict[str, int]:
    """Helper test — đếm up/down/flat/unmatched từ change_pct."""
    up = down = flat = unmatched = 0
    traded = traded or set()
    for q in quotes:
        if session_open and q.symbol not in traded and q.state not in ("live", "stale"):
            unmatched += 1
            continue
        chg = q.change_pct
        if chg is None:
            flat += 1
        elif chg > flat_eps:
            up += 1
        elif chg < -flat_eps:
            down += 1
        else:
            flat += 1
    return {"up": up, "down": down, "flat": flat, "unmatched": unmatched}
