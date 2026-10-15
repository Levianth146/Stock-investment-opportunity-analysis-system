"""Phân tích trong phiên (tạm tính) — chỉ nhóm liquid; số gắn basis live|eod."""
from __future__ import annotations

import math
from typing import Any

from stockai.api.realtime import QuoteTick, RealtimeHub


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
        # kỳ mới nhất thường đứng đầu hoặc cuối — lấy period max
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

    # giá tham chiếu ngành từ M4 cache nếu có — không bắt buộc
    ref = None
    unreliable = False

    return {
        "price": {"value": price, "as_of_ts": as_of_ts, "basis": basis},
        "market_cap": {"value": mcap, "as_of_ts": as_of_ts, "basis": basis},
        "pe": {"value": pe, "as_of_ts": as_of_ts, "basis": basis},
        "pb": {"value": pb, "as_of_ts": as_of_ts, "basis": basis},
        "dividend_yield": {"value": dy, "as_of_ts": as_of_ts, "basis": basis},
        "sector_ref": {
            "value": ref,
            "unreliable": unreliable,
            "as_of_ts": as_of_ts,
            "basis": "eod",
        },
        "label": "tạm tính",
    }


def build_market_analysis(hub: RealtimeHub, store: Any) -> dict[str, Any]:
    """Tạo payload GET /api/realtime/market — breadth, lists, heatmap, valuation mẫu."""
    sess = hub.session_now()
    as_of_ts = sess.as_of_ts
    frac = max(sess.session_fraction, 0.05)  # tránh chia 0 đầu phiên

    up = down = flat = 0
    excluded_no_ref = 0
    above_sma50 = below_sma50 = 0
    above_sma200 = below_sma200 = 0
    hit_52w_hi = hit_52w_lo = 0

    strong_up: list[dict] = []
    strong_down: list[dict] = []
    vol_spike: list[dict] = []
    hi52: list[dict] = []
    lo52: list[dict] = []
    overbought: list[dict] = []
    oversold: list[dict] = []
    heatmap: list[dict] = []

    for q in hub.iter_liquid_quotes():
        sym = q.symbol
        try:
            snap = store.load_snapshot(sym)
        except Exception:  # noqa: BLE001
            continue
        closes, highs, lows, vols = _closes_vols(snap)
        price = q.price
        basis = q.basis if q.state == "live" else "eod"
        chg = q.change_pct
        has_ref = (
            getattr(q, "prev_close_source", "none") in ("tick", "snapshot")
            and q.prev_close is not None
        )
        if not has_ref:
            # Breadth / lists chỉ mã có giá tham chiếu hợp lệ
            excluded_no_ref += 1
            company = snap.get("company") if isinstance(snap.get("company"), dict) else {}
            sector = company.get("sector") or "Khác"
            shares = _num(company.get("shares_outstanding"))
            mcap = (price * shares) if (price is not None and shares is not None) else None
            heatmap.append(
                {
                    "symbol": sym,
                    "sector": sector,
                    "change_pct": {
                        "value": None,
                        "as_of_ts": as_of_ts,
                        "basis": basis,
                    },
                    "market_cap": {
                        "value": mcap,
                        "as_of_ts": as_of_ts,
                        "basis": basis,
                    },
                    "label": "chưa có giá tham chiếu",
                }
            )
            continue

        if chg is not None:
            if chg > 0.05:
                up += 1
            elif chg < -0.05:
                down += 1
            else:
                flat += 1
        else:
            flat += 1

        sma50 = _sma(closes, 50)
        sma200 = _sma(closes, 200)
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

        # 52 tuần ≈ 252 phiên
        if highs and lows and price is not None:
            hi = max(highs[-252:]) if len(highs) >= 20 else max(highs)
            lo = min(lows[-252:]) if len(lows) >= 20 else min(lows)
            if price >= hi * 0.999:
                hit_52w_hi += 1
                hi52.append(_row(sym, price, chg, as_of_ts, basis))
            if price <= lo * 1.001:
                hit_52w_lo += 1
                lo52.append(_row(sym, price, chg, as_of_ts, basis))

        if chg is not None and chg >= 3.0:
            strong_up.append(_row(sym, price, chg, as_of_ts, basis))
        if chg is not None and chg <= -3.0:
            strong_down.append(_row(sym, price, chg, as_of_ts, basis))

        avg20 = _avg_vol(vols, 20)
        today_vol = q.volume
        if today_vol is None and vols:
            today_vol = vols[-1]
        if avg20 and avg20 > 0 and today_vol is not None:
            expected = avg20 * frac
            if expected > 0 and today_vol / expected >= 2.0:
                vol_spike.append(
                    {
                        **_row(sym, price, chg, as_of_ts, basis),
                        "vol_ratio": round(today_vol / expected, 2),
                        "session_fraction": round(frac, 4),
                    }
                )

        rsi = _rsi14(closes, 14)
        if rsi is not None:
            if rsi >= 70:
                overbought.append({**_row(sym, price, chg, as_of_ts, "eod"), "rsi14": round(rsi, 2)})
            elif rsi <= 30:
                oversold.append({**_row(sym, price, chg, as_of_ts, "eod"), "rsi14": round(rsi, 2)})

        company = snap.get("company") if isinstance(snap.get("company"), dict) else {}
        sector = company.get("sector") or "Khác"
        shares = _num(company.get("shares_outstanding"))
        mcap = (price * shares) if (price is not None and shares is not None) else None
        heatmap.append(
            {
                "symbol": sym,
                "sector": sector,
                "change_pct": {
                    "value": chg,
                    "as_of_ts": as_of_ts,
                    "basis": basis,
                },
                "market_cap": {
                    "value": mcap,
                    "as_of_ts": as_of_ts,
                    "basis": basis,
                },
                "label": "tạm tính",
            }
        )

    def _top(rows: list[dict], key: str = "change_pct", n: int = 15, reverse: bool = True) -> list[dict]:
        def _k(r: dict) -> float:
            v = r.get(key)
            if isinstance(v, dict):
                v = v.get("value")
            try:
                return float(v) if v is not None else float("-inf" if reverse else "inf")
            except (TypeError, ValueError):
                return float("-inf" if reverse else "inf")

        return sorted(rows, key=_k, reverse=reverse)[:n]

    # valuation mẫu: vài mã đang xem / liquid đầu
    sample_vals: list[dict] = []
    sample_syms = list(hub._liquid)[:12]  # noqa: SLF001 — nội bộ hub
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
                    basis=q.basis if q.state == "live" else "eod",
                ),
            }
        )

    status = hub.status()
    return {
        "asof": store.asof,
        "as_of_ts": as_of_ts,
        "label": "tạm tính",
        "session": status["session"],
        "realtime": {
            "mode": status["mode"],
            "state": status["state"],
        },
        "breadth": {
            "up": {"value": up, "as_of_ts": as_of_ts, "basis": "live" if status["mode"] == "live" else "eod"},
            "down": {"value": down, "as_of_ts": as_of_ts, "basis": "live" if status["mode"] == "live" else "eod"},
            "flat": {"value": flat, "as_of_ts": as_of_ts, "basis": "live" if status["mode"] == "live" else "eod"},
            "excluded_no_ref": {
                "value": excluded_no_ref,
                "as_of_ts": as_of_ts,
                "basis": "eod",
            },
            "above_sma50": {"value": above_sma50, "as_of_ts": as_of_ts, "basis": "eod"},
            "below_sma50": {"value": below_sma50, "as_of_ts": as_of_ts, "basis": "eod"},
            "above_sma200": {"value": above_sma200, "as_of_ts": as_of_ts, "basis": "eod"},
            "below_sma200": {"value": below_sma200, "as_of_ts": as_of_ts, "basis": "eod"},
            "hit_52w_high": {"value": hit_52w_hi, "as_of_ts": as_of_ts, "basis": "live" if status["mode"] == "live" else "eod"},
            "hit_52w_low": {"value": hit_52w_lo, "as_of_ts": as_of_ts, "basis": "live" if status["mode"] == "live" else "eod"},
            "note": (
                "SMA/RSI từ EOD close; % thay đổi chỉ khi có giá tham chiếu "
                "(basicPrice DNSE hoặc snapshot trùng phiên đóng gần nhất). "
                "Mã thiếu tham chiếu đếm ở excluded_no_ref."
            ),
        },
        "lists": {
            "strong_up": _top(strong_up, reverse=True),
            "strong_down": _top(strong_down, reverse=False),
            "volume_spike": _top(vol_spike, key="vol_ratio", reverse=True),
            "high_52w": hi52[:15],
            "low_52w": lo52[:15],
            "overbought": overbought[:15],
            "oversold": oversold[:15],
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
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "price": {"value": price, "as_of_ts": as_of_ts, "basis": basis},
        "change_pct": {"value": change_pct, "as_of_ts": as_of_ts, "basis": basis},
        "label": "tạm tính",
    }


def compute_breadth_from_quotes(
    quotes: list[QuoteTick],
    *,
    flat_eps: float = 0.05,
) -> dict[str, int]:
    """Helper test — đếm up/down/flat từ change_pct."""
    up = down = flat = 0
    for q in quotes:
        chg = q.change_pct
        if chg is None:
            flat += 1
        elif chg > flat_eps:
            up += 1
        elif chg < -flat_eps:
            down += 1
        else:
            flat += 1
    return {"up": up, "down": down, "flat": flat}
