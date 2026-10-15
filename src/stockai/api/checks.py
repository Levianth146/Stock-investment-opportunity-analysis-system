"""Phép kiểm minh họa + thống kê snapshot (feature 014g) — không đổi công thức điểm."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from stockai.api.store import repo_root

_CFG_CACHE: dict[str, Any] | None = None


def load_checks_cfg(path: Path | None = None) -> dict[str, Any]:
    global _CFG_CACHE
    p = path or (repo_root() / "config" / "checks.yaml")
    if _CFG_CACHE is not None and path is None:
        return _CFG_CACHE
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    if path is None:
        _CFG_CACHE = raw
    return raw


def _num(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, dict) and "value" in v:
        v = v.get("value")
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def _metric(mod: dict | None, key: str) -> float | None:
    if not isinstance(mod, dict):
        return None
    m = mod.get("metrics") if isinstance(mod.get("metrics"), dict) else {}
    return _num(m.get(key))


def _annual_sorted(snap: dict) -> list[dict]:
    fin = snap.get("financials") if isinstance(snap.get("financials"), dict) else {}
    ann = fin.get("annual") if isinstance(fin, dict) else None
    if not isinstance(ann, list):
        return []
    # Snapshot M1: mới nhất đứng đầu — giữ nguyên thứ tự
    return [p for p in ann if isinstance(p, dict)]


def _quarterly_sorted(snap: dict) -> list[dict]:
    fin = snap.get("financials") if isinstance(snap.get("financials"), dict) else {}
    q = fin.get("quarterly") if isinstance(fin, dict) else None
    if not isinstance(q, list):
        return []
    return [p for p in q if isinstance(p, dict)]


def _items(period: dict | None) -> dict[str, Any]:
    if not period:
        return {}
    it = period.get("items")
    return it if isinstance(it, dict) else {}


def _div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _roa(items: dict) -> float | None:
    ni = _num(items.get("net_income_parent"))
    if ni is None:
        ni = _num(items.get("net_income"))
    assets = _num(items.get("total_assets"))
    return _div(ni, assets)


def _leverage(items: dict) -> float | None:
    """Nợ dài hạn / tổng tài sản (Piotroski)."""
    ltd = _num(items.get("long_term_debt"))
    assets = _num(items.get("total_assets"))
    return _div(ltd, assets)


def _current_ratio(items: dict) -> float | None:
    return _div(_num(items.get("current_assets")), _num(items.get("current_liabilities")))


def _gross_margin(items: dict) -> float | None:
    return _div(_num(items.get("gross_profit")), _num(items.get("revenue")))


def _asset_turnover(items: dict) -> float | None:
    return _div(_num(items.get("revenue")), _num(items.get("total_assets")))


def _shares_proxy(items: dict) -> float | None:
    """Số cổ phiếu ước = NI_parent / EPS (không bịa nếu thiếu)."""
    nip = _num(items.get("net_income_parent"))
    eps = _num(items.get("eps"))
    if nip is None or eps is None or eps == 0:
        return None
    return nip / eps


def _pct_change(curr: float | None, prev: float | None) -> float | None:
    if curr is None or prev is None or prev == 0:
        return None
    return (curr - prev) / abs(prev)


def _quartile_rank(value: float | None, peers: list[float], *, higher_better: bool) -> str | None:
    """Trả 'top'|'bottom'|'mid'|None — top = 25% tốt nhất theo hướng."""
    if value is None or len(peers) < 8:
        return None
    s = sorted(peers)
    n = len(s)
    # vị trí (0-based) trong peers đã gồm value nếu có
    if higher_better:
        # top quartile = cao nhất
        thr_top = s[int(0.75 * (n - 1))]
        thr_bot = s[int(0.25 * (n - 1))]
        if value >= thr_top:
            return "top"
        if value <= thr_bot:
            return "bottom"
        return "mid"
    thr_low = s[int(0.25 * (n - 1))]  # bottom quartile giá trị thấp
    thr_high = s[int(0.75 * (n - 1))]
    if value <= thr_low:
        return "bottom"
    if value >= thr_high:
        return "top"
    return "mid"


def _check_result(
    spec: dict,
    *,
    passed: bool | None,
    value: Any = None,
    display: str | None = None,
) -> dict[str, Any]:
    return {
        "id": spec["id"],
        "side": spec.get("side"),
        "label_vi": spec.get("label_vi"),
        "basis": spec.get("basis"),
        "source": spec.get("source"),
        "family": spec.get("family"),
        "passed": passed,
        "value": value,
        "display": display,
        "na": passed is None,
    }


def evaluate_piotroski(curr: dict, prev: dict) -> tuple[list[dict], dict[str, Any]]:
    """Trả (kết quả từng phép, f_score meta)."""
    cfg = load_checks_cfg()
    specs = {
        c["id"]: c
        for c in (cfg.get("checks") or [])
        if c.get("family") == "piotroski"
    }
    ci, pi = _items(curr), _items(prev)
    results: list[dict] = []

    def add(cid: str, passed: bool | None, value: Any = None, display: str | None = None) -> None:
        spec = specs.get(cid)
        if not spec:
            return
        results.append(_check_result(spec, passed=passed, value=value, display=display))

    roa_c, roa_p = _roa(ci), _roa(pi)
    add("roa_positive", None if roa_c is None else roa_c > 0, roa_c)
    cfo = _num(ci.get("cfo"))
    add("cfo_positive", None if cfo is None else cfo > 0, cfo)
    add(
        "roa_improving",
        None if roa_c is None or roa_p is None else roa_c > roa_p,
        {"curr": roa_c, "prev": roa_p},
    )
    ni = _num(ci.get("net_income_parent"))
    if ni is None:
        ni = _num(ci.get("net_income"))
    add(
        "cfo_exceeds_net_income",
        None if cfo is None or ni is None else cfo > ni,
        {"cfo": cfo, "ni": ni},
    )
    lev_c, lev_p = _leverage(ci), _leverage(pi)
    add(
        "leverage_down",
        None if lev_c is None or lev_p is None else lev_c < lev_p,
        {"curr": lev_c, "prev": lev_p},
    )
    cr_c, cr_p = _current_ratio(ci), _current_ratio(pi)
    add(
        "current_ratio_up",
        None if cr_c is None or cr_p is None else cr_c > cr_p,
        {"curr": cr_c, "prev": cr_p},
    )
    sh_c, sh_p = _shares_proxy(ci), _shares_proxy(pi)
    dil = _pct_change(sh_c, sh_p)
    add(
        "no_dilution",
        None if dil is None else dil <= 0.02,
        dil,
        display=None if dil is None else f"{dil * 100:.1f}%",
    )
    gm_c, gm_p = _gross_margin(ci), _gross_margin(pi)
    add(
        "gross_margin_up",
        None if gm_c is None or gm_p is None else gm_c > gm_p,
        {"curr": gm_c, "prev": gm_p},
    )
    at_c, at_p = _asset_turnover(ci), _asset_turnover(pi)
    add(
        "asset_turnover_up",
        None if at_c is None or at_p is None else at_c > at_p,
        {"curr": at_c, "prev": at_p},
    )

    computable = [r for r in results if r["passed"] is not None]
    passed_n = sum(1 for r in computable if r["passed"] is True)
    y = len(computable)
    f_score = {
        "x": passed_n,
        "y": y,
        "label": f"Điểm Piotroski {passed_n}/{y}" if y else None,
        "hide": y < int(cfg.get("hide_f_score_if_y_lt") or 5),
    }
    return results, f_score


def evaluate_all_checks(
    *,
    snapshot: dict,
    bundle: dict,
    sector_peer_metrics: list[dict[str, Any]] | None = None,
    cfg: dict | None = None,
) -> dict[str, Any]:
    """Đánh giá mọi phép kiểm config-driven."""
    cfg = cfg or load_checks_cfg()
    company = bundle.get("company") if isinstance(bundle.get("company"), dict) else {}
    is_bank = company.get("is_bank") is True
    m3 = bundle.get("m3") if isinstance(bundle.get("m3"), dict) else {}
    m4 = bundle.get("m4") if isinstance(bundle.get("m4"), dict) else {}
    m6 = bundle.get("m6") if isinstance(bundle.get("m6"), dict) else {}
    m2 = bundle.get("m2") if isinstance(bundle.get("m2"), dict) else {}

    ann = _annual_sorted(snapshot)
    curr = ann[0] if ann else None
    prev = ann[1] if len(ann) > 1 else None
    ci = _items(curr)

    checks_out: list[dict] = []
    f_score: dict[str, Any] | None = None

    if not is_bank and curr and prev:
        pio, f_score = evaluate_piotroski(curr, prev)
        checks_out.extend(pio)
    elif not is_bank:
        # thiếu 2 năm → mọi Piotroski na
        for spec in cfg.get("checks") or []:
            if spec.get("family") == "piotroski":
                checks_out.append(_check_result(spec, passed=None))
        f_score = {"x": 0, "y": 0, "label": None, "hide": True}

    pe = _metric(m4, "pe")
    pb = _metric(m4, "pb")
    peers = sector_peer_metrics or []
    min_peers = int(cfg.get("min_sector_peers") or 8)
    peer_ok = len(peers) >= min_peers

    def apply_spec(spec: dict) -> None:
        nonlocal checks_out
        applies = spec.get("applies_to") or "all"
        if applies == "non_bank" and is_bank:
            return
        if applies == "bank" and not is_bank:
            return
        if spec.get("family") in ("piotroski",):
            return  # đã xử lý
        cid = spec["id"]
        passed: bool | None = None
        value: Any = None

        if cid == "pe_le_15":
            passed = None if pe is None else pe <= 15
            value = pe
        elif cid == "pb_le_1_5":
            passed = None if pb is None else pb <= 1.5
            value = pb
        elif cid == "pe_x_pb_le_22_5":
            if pe is None or pb is None:
                passed = None
            else:
                value = pe * pb
                passed = value <= 22.5
        elif cid == "current_ratio_ge_2":
            cr = _current_ratio(ci)
            value = cr
            passed = None if cr is None else cr >= 2
        elif cid == "roe_top_quartile":
            roe = _metric(m2, "roe") or _metric(m4, "roe")
            vals = [p["roe"] for p in peers if isinstance(p.get("roe"), (int, float))]
            if roe is not None and peer_ok:
                q = _quartile_rank(roe, vals + [roe], higher_better=True)
                passed = q == "top"
            value = roe
        elif cid == "pe_bottom_quartile":
            vals = [p["pe"] for p in peers if isinstance(p.get("pe"), (int, float))]
            if pe is not None and peer_ok:
                q = _quartile_rank(pe, vals + [pe], higher_better=False)
                passed = q == "bottom"
            value = pe
        elif cid == "pe_top_quartile":
            vals = [p["pe"] for p in peers if isinstance(p.get("pe"), (int, float))]
            if pe is not None and peer_ok:
                q = _quartile_rank(pe, vals + [pe], higher_better=False)
                passed = q == "top"  # top = đắt = rủi ro
            value = pe
        elif cid == "pb_bottom_quartile":
            vals = [p["pb"] for p in peers if isinstance(p.get("pb"), (int, float))]
            if pb is not None and peer_ok:
                q = _quartile_rank(pb, vals + [pb], higher_better=False)
                passed = q == "bottom"
            value = pb
        elif cid == "revenue_growth_top_quartile":
            g = _metric(m2, "revenue_yoy") or _metric(m2, "rev_yoy")
            vals = [
                p["revenue_yoy"]
                for p in peers
                if isinstance(p.get("revenue_yoy"), (int, float))
            ]
            if g is not None and peer_ok and len(vals) >= min_peers - 1:
                q = _quartile_rank(g, vals + [g], higher_better=True)
                passed = q == "top"
            value = g
        elif cid == "volatility_top_quartile":
            vol = _metric(m6, "ann_vol") or _metric(m6, "volatility")
            vals = [
                p["ann_vol"] for p in peers if isinstance(p.get("ann_vol"), (int, float))
            ]
            if vol is not None and peer_ok and len(vals) >= min_peers - 1:
                # chuẩn hoá %
                def _vp(x: float) -> float:
                    return x * 100 if abs(x) <= 1.5 else x

                q = _quartile_rank(
                    _vp(vol), [_vp(v) for v in vals] + [_vp(vol)], higher_better=True
                )
                passed = q == "top"
            value = vol
        elif cid == "interest_cover_lt_1_5":
            ebit = _num(ci.get("ebit"))
            if ebit is None:
                # ước ebit ≈ gross_profit - selling - admin nếu có
                gp = _num(ci.get("gross_profit"))
                se = _num(ci.get("selling_expense"))
                ae = _num(ci.get("admin_expense"))
                if gp is not None:
                    ebit = gp - (se or 0) - (ae or 0)
            ie = _num(ci.get("interest_expense"))
            cover = _div(ebit, abs(ie) if ie else None)
            value = cover
            passed = None if cover is None else cover < 1.5
        elif cid == "rsi_overbought_gt_70":
            rsi = _metric(m3, "rsi14") or _metric(m3, "rsi")
            value = rsi
            passed = None if rsi is None else rsi > 70
        elif cid == "rsi_oversold_lt_30":
            rsi = _metric(m3, "rsi14") or _metric(m3, "rsi")
            value = rsi
            passed = None if rsi is None else rsi < 30
        elif cid == "above_ma200":
            sig = _metric(m3, "above_ma200")
            # signals boolean in metrics or price vs ma
            raw = (m3.get("metrics") or {}).get("above_ma200")
            if isinstance(raw, bool):
                passed = raw
            elif isinstance(raw, dict) and isinstance(raw.get("value"), bool):
                passed = raw["value"]
            else:
                px = _metric(m4, "price_close")
                ma = _metric(m3, "ma200")
                passed = None if px is None or ma is None else px > ma
            value = passed
        elif cid == "below_ma200":
            px = _metric(m4, "price_close")
            ma = _metric(m3, "ma200")
            raw = (m3.get("metrics") or {}).get("above_ma200")
            if isinstance(raw, bool):
                passed = not raw
            elif isinstance(raw, dict) and isinstance(raw.get("value"), bool):
                passed = not raw["value"]
            else:
                passed = None if px is None or ma is None else px < ma
            value = passed
        elif cid == "drawdown_gt_35":
            dd = _metric(m6, "max_drawdown") or _metric(m6, "drawdown")
            if dd is None:
                passed = None
            else:
                dd_pct = abs(dd * 100 if abs(dd) <= 1.5 else dd)
                passed = dd_pct > 35
                value = dd
        elif cid == "negative_cfo":
            cfo = _num(ci.get("cfo"))
            value = cfo
            passed = None if cfo is None else cfo < 0
        elif cid == "rev_growth_positive":
            g = _metric(m2, "revenue_yoy") or _metric(m2, "rev_yoy")
            value = g
            passed = None if g is None else g > 0
        elif cid == "profit_growth_positive":
            g = _metric(m2, "ni_yoy") or _metric(m2, "net_income_yoy")
            value = g
            passed = None if g is None else g > 0
        elif cid == "npl_available":
            npl = _num(ci.get("npl_ratio"))
            value = npl
            passed = npl is not None
            if npl is None:
                return  # không đưa vào list nếu không có
        elif cid == "car_available":
            car = _num(ci.get("car"))
            value = car
            passed = car is not None
            if car is None:
                return
        else:
            return

        checks_out.append(_check_result(spec, passed=passed, value=value))

    for spec in cfg.get("checks") or []:
        apply_spec(spec)

    def _count(side: str) -> int:
        return sum(
            1
            for c in checks_out
            if c.get("side") == side
            and c.get("basis") != "info"
            and c.get("passed") is True
        )

    rewards = [c for c in checks_out if c.get("side") == "reward"]
    risks = [c for c in checks_out if c.get("side") == "risk"]
    infos = [c for c in checks_out if c.get("side") == "info"]

    # Rủi ro đã kích hoạt vs đã kiểm và không có vấn đề (cờ rủi ro không xảy ra)
    risks_triggered = [c for c in risks if c.get("passed") is True]
    risks_cleared = [c for c in risks if c.get("passed") is False]
    # "Chưa đạt" chỉ Piotroski / Graham / phân vị ngành (reward fail)
    _not_met_families = {"piotroski", "graham", "sector"}
    not_met = [
        c
        for c in rewards
        if c.get("passed") is False and (c.get("family") in _not_met_families)
    ]
    rewards_failed_all = [c for c in rewards if c.get("passed") is False]

    # Đoạn phương pháp: liệt kê mọi check
    lines = []
    for spec in cfg.get("checks") or []:
        lines.append(f"- {spec.get('label_vi')} ({spec.get('source') or spec.get('basis')})")
    method = (
        "Các phép kiểm đang dùng:\n"
        + "\n".join(lines)
        + "\n\n"
        + str(cfg.get("method_disclaimer") or "")
    )

    tooltips = cfg.get("basis_tooltip") or {}

    return {
        "is_bank": is_bank,
        "checks": checks_out,
        "rewards": [c for c in rewards if c.get("passed") is True],
        "rewards_failed": rewards_failed_all,  # tương thích cũ
        "not_met": not_met,
        "risks": risks_triggered,
        "risks_failed": risks_cleared,  # tương thích: fail = không kích hoạt
        "cleared_risks": risks_cleared,
        "info": infos,
        "rewards_count": _count("reward"),
        "risks_count": _count("risk"),
        "cleared_risks_count": len(risks_cleared),
        "f_score": f_score,
        "method": method,
        "basis_tooltip": tooltips,
        "npl_car_available": {
            "npl_ratio": _num(ci.get("npl_ratio")),
            "car": _num(ci.get("car")),
            "note": "NPL/CAR chỉ hiện nếu có trong snapshot (bank_kpis); hiện tại thường null trên HOSE/HNX nonews.",
        },
    }


def pillar_ranks_in_sector(
    *,
    scores: dict[str, Any],
    peer_scores: list[dict[str, Any]],
    min_peers: int = 8,
) -> dict[str, Any]:
    """Percentile trong ngành cho F,T,V,S và safety=100-R. Null nếu < min_peers scored."""
    out: dict[str, Any] = {}
    n = len(peer_scores)
    if n < min_peers:
        for k in ("F", "T", "V", "S", "safety"):
            out[k] = None
        out["n_sector_scored"] = n
        return out

    def pct_rank(val: float | None, key: str, *, invert: bool = False) -> dict | None:
        if val is None:
            return None
        vals = []
        for p in peer_scores:
            sc = p.get("scores") if isinstance(p.get("scores"), dict) else p
            if invert:
                r = sc.get("R") if isinstance(sc, dict) else None
                if isinstance(r, (int, float)):
                    vals.append(100.0 - float(r))
            else:
                v = sc.get(key) if isinstance(sc, dict) else None
                if isinstance(v, (int, float)):
                    vals.append(float(v))
        if len(vals) < min_peers:
            return None
        # percentile: tỷ lệ peers <= val
        below = sum(1 for x in vals if x <= val)
        pctile = below / len(vals)
        # "top X%" = tốt hơn (1-pctile) nếu higher better — hiển thị top%
        top_pct = max(1, int(round((1 - pctile) * 100))) if pctile < 1 else 1
        return {
            "percentile": round(pctile * 100, 1),
            "top_pct": top_pct,
            "n": len(vals),
            "value": val,
        }

    for k in ("F", "T", "V", "S"):
        out[k] = pct_rank(_num(scores.get(k)), k)
    r = _num(scores.get("R"))
    safety = 100.0 - r if r is not None else None
    out["safety"] = pct_rank(safety, "R", invert=True)
    out["n_sector_scored"] = n
    return out


def build_quarter_summary(snapshot: dict, *, prices_rows: list[dict] | None = None) -> dict[str, Any]:
    """Tóm tắt quý gần nhất + phản ứng giá quanh ngày công bố (chỉ khi không ước lượng)."""
    qs = _quarterly_sorted(snapshot)
    if not qs:
        return {
            "available": False,
            "reason": "no_quarterly",
            "period": None,
            "items": {},
            "yoy": {},
            "qoq": {},
            "published_at": None,
            "published_estimated": None,
            "price_reaction": None,
        }
    latest = qs[0]
    items = _items(latest)
    # cùng kỳ năm trước: period YYYYQn → (Y-1)Qn
    period = str(latest.get("period") or "")
    yoy_period = None
    if len(period) >= 6 and "Q" in period.upper():
        try:
            y = int(period[:4])
            qpart = period[4:]
            yoy_period = f"{y - 1}{qpart}"
        except ValueError:
            yoy_period = None
    prev_y = next((p for p in qs if str(p.get("period")) == yoy_period), None) if yoy_period else None
    prev_q = qs[1] if len(qs) > 1 else None

    def pack(key: str) -> dict[str, Any]:
        cur = _num(items.get(key))
        py = _num(_items(prev_y).get(key)) if prev_y else None
        pq = _num(_items(prev_q).get(key)) if prev_q else None
        return {
            "value": cur,
            "yoy": _pct_change(cur, py),
            "qoq": _pct_change(cur, pq),
        }

    keys = ["revenue", "gross_profit", "net_income", "net_income_parent"]
    company = snapshot.get("company") if isinstance(snapshot.get("company"), dict) else {}
    is_bank = company.get("is_bank") is True
    if is_bank:
        keys = ["revenue", "net_income", "net_income_parent", "net_interest_income", "total_operating_income"]

    packed = {k: pack(k) for k in keys if _num(items.get(k)) is not None or True}
    # chỉ giữ key có trong items bank/non-bank
    packed = {k: v for k, v in packed.items() if k in items or not is_bank}

    published = latest.get("published_at")
    estimated = bool(latest.get("published_at_estimated"))
    reaction = None
    reaction_reason = None
    if estimated:
        reaction_reason = "published_estimated"
    elif not published:
        reaction_reason = "no_published_at"
    else:
        pub = str(published)[:10]
        rows = prices_rows or []
        by_date = {
            str(r.get("date") or r.get("time") or "")[:10]: _num(r.get("close"))
            for r in rows
            if isinstance(r, dict)
        }
        dates = sorted(d for d in by_date if d and by_date[d] is not None)

        def nearest_before(d: str) -> str | None:
            cands = [x for x in dates if x < d]
            return cands[-1] if cands else None

        def nth_after(d: str, n: int) -> str | None:
            cands = [x for x in dates if x > d]
            return cands[n - 1] if len(cands) >= n else None

        t_m1 = nearest_before(pub)
        t_p1 = nth_after(pub, 1)
        t_p5 = nth_after(pub, 5)
        if t_m1 and t_p1 and by_date.get(t_m1) and by_date.get(t_p1):
            c0 = by_date[t_m1]
            c1 = by_date[t_p1]
            assert c0 and c1
            reaction = {
                "t0": pub,
                "close_before": c0,
                "close_after_1d": c1,
                "return_1d": (c1 - c0) / c0,
                "close_after_5d": by_date.get(t_p5) if t_p5 else None,
                "return_5d": (
                    (by_date[t_p5] - c0) / c0 if t_p5 and by_date.get(t_p5) and c0 else None
                ),
            }
        else:
            reaction_reason = "insufficient_price_window"

    return {
        "available": True,
        "period": period,
        "items": packed,
        "published_at": published,
        "published_estimated": estimated,
        "price_reaction": reaction,
        "price_reaction_reason": reaction_reason,
        "is_bank": is_bank,
    }


def map_tone(kind: str, value: float | None) -> str:
    if value is None:
        return "neutral"
    if kind == "higher_better":
        return "good" if value > 0 else ("bad" if value < 0 else "neutral")
    if kind == "lower_better":
        return "good" if value < 15 else ("bad" if value > 30 else "neutral")  # rough for ratios like PE
    if kind == "lower_abs_better":
        return "bad" if abs(value) > 0.35 else "neutral"
    if kind == "band_30_70":
        if value > 70 or value < 30:
            return "bad"
        return "good"
    if kind == "near_one":
        return "neutral"
    return "neutral"


def build_snapshot_stats(snapshot: dict, bundle: dict, cfg: dict | None = None) -> dict[str, Any]:
    cfg = cfg or load_checks_cfg()
    company = bundle.get("company") if isinstance(bundle.get("company"), dict) else {}
    m2 = bundle.get("m2") if isinstance(bundle.get("m2"), dict) else {}
    m3 = bundle.get("m3") if isinstance(bundle.get("m3"), dict) else {}
    m4 = bundle.get("m4") if isinstance(bundle.get("m4"), dict) else {}
    m6 = bundle.get("m6") if isinstance(bundle.get("m6"), dict) else {}
    ann = _annual_sorted(snapshot)
    ci = _items(ann[0] if ann else None)
    price = _metric(m4, "price_close")
    shares = _num(company.get("shares_outstanding"))
    mcap = shares * price if shares and price else None

    # 52w from prices
    rows = []
    pr = snapshot.get("prices") if isinstance(snapshot.get("prices"), dict) else {}
    if isinstance(pr.get("rows"), list):
        rows = [r for r in pr["rows"] if isinstance(r, dict)]
    closes = [_num(r.get("close")) for r in rows]
    closes = [c for c in closes if c is not None]
    hi = max(closes[-252:], default=None) if closes else None
    lo = min(closes[-252:], default=None) if closes else None
    pct_hi = ((price - hi) / hi) if price and hi else None
    pct_lo = ((price - lo) / lo) if price and lo else None

    ma50 = _metric(m3, "ma50")
    ma200 = _metric(m3, "ma200")
    dist50 = ((price - ma50) / ma50) if price and ma50 else None
    dist200 = ((price - ma200) / ma200) if price and ma200 else None

    ebit = _num(ci.get("ebit"))
    ie = _num(ci.get("interest_expense"))
    interest_cover = _div(ebit, abs(ie) if ie else None)

    raw_values: dict[str, float | None] = {
        "pe": _metric(m4, "pe"),
        "pb": _metric(m4, "pb"),
        "eps": _num(ci.get("eps")),
        "roe": _metric(m2, "roe") or _metric(m4, "roe"),
        "roa": _roa(ci),
        "gross_margin": _gross_margin(ci),
        "net_margin": _div(_num(ci.get("net_income")), _num(ci.get("revenue"))),
        "debt_to_equity": _div(
            (_num(ci.get("short_term_debt")) or 0) + (_num(ci.get("long_term_debt")) or 0)
            if _num(ci.get("short_term_debt")) is not None or _num(ci.get("long_term_debt")) is not None
            else None,
            _num(ci.get("total_equity")),
        ),
        "interest_cover": interest_cover,
        "current_ratio": _current_ratio(ci),
        "revenue_yoy": _metric(m2, "revenue_yoy") or _metric(m2, "rev_yoy"),
        "profit_yoy": _metric(m2, "ni_yoy") or _metric(m2, "net_income_yoy"),
        "rsi14": _metric(m3, "rsi14") or _metric(m3, "rsi"),
        "dist_ma50_pct": dist50 * 100 if dist50 is not None else None,
        "dist_ma200_pct": dist200 * 100 if dist200 is not None else None,
        "pct_from_52w_high": pct_hi * 100 if pct_hi is not None else None,
        "pct_from_52w_low": pct_lo * 100 if pct_lo is not None else None,
        "beta": _metric(m6, "beta"),
        "ann_vol": _metric(m6, "ann_vol") or _metric(m6, "volatility"),
        "max_drawdown": _metric(m6, "max_drawdown") or _metric(m6, "drawdown"),
        "avg_volume_1m": _metric(m3, "avg_volume_20") or _metric(m3, "avg_volume_1m"),
        "avg_traded_value_1m": None,
        "market_cap": mcap,
        "shares_outstanding": shares,
        "free_float": _num(company.get("free_float")),
    }
    if price and raw_values.get("avg_volume_1m"):
        raw_values["avg_traded_value_1m"] = price * float(raw_values["avg_volume_1m"])

    items = []
    for spec in cfg.get("snapshot_stats") or []:
        sid = spec["id"]
        val = raw_values.get(sid)
        if val is None and sid == "free_float":
            continue  # ẩn nếu không có
        tone_kind = spec.get("tone") or "neutral"
        # tone mapping chuyên biệt hơn cho % growth
        if sid in ("revenue_yoy", "profit_yoy", "roa", "roe", "gross_margin", "net_margin"):
            tone = "good" if (val or 0) > 0 else ("bad" if val is not None and val < 0 else "neutral")
        elif sid in ("pe", "pb", "debt_to_equity", "ann_vol"):
            tone = map_tone("lower_better", val)
        elif sid == "max_drawdown":
            tone = map_tone("lower_abs_better", val)
        elif sid == "rsi14":
            tone = map_tone("band_30_70", val)
        elif sid == "interest_cover":
            tone = "bad" if val is not None and val < 1.5 else ("good" if val is not None and val >= 2 else "neutral")
        elif sid == "current_ratio":
            tone = "good" if val is not None and val >= 1.5 else ("bad" if val is not None and val < 1 else "neutral")
        else:
            tone = map_tone(tone_kind, val)
        items.append(
            {
                "id": sid,
                "label_vi": spec.get("label_vi"),
                "value": val,
                "unit": spec.get("unit"),
                "tone": tone,
            }
        )
    return {"items": items, "is_bank": company.get("is_bank") is True}
