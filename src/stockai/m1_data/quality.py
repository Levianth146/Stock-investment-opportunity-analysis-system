"""Cổng chất lượng dữ liệu cho universe rộng (HOSE/HNX/UpCom). Chỉ N2 sửa.

Mỗi snapshot được xếp 1 trong 3 bậc, ghi vào meta.flags (không thêm trường mới nên không đụng schema):
  full         đủ dữ liệu để chấm điểm bình thường
  limited      chấm được nhưng thiếu một phần (ít BCTC, ít tin, thanh khoản thấp, ngành đặc thù ...)
  insufficient KHÔNG nên chấm điểm/xếp hạng (quá ít giá, quá ít BCTC, gần như không giao dịch)
Cờ: quality_tier_<bậc> và quality_<lý do> (ví dụ quality_prices_lt_750, quality_illiquid).
Ngưỡng chỉnh trong config/data_sources.yaml mục `quality`."""
from __future__ import annotations

DEFAULTS = {
    "min_price_rows": 750,            # ~3 năm phiên giao dịch; dưới mức này -> insufficient
    "min_annual": 3,                  # số năm BCTC tối thiểu; dưới mức này -> insufficient
    "min_avg_value_vnd": 1e9,         # GTGD bình quân 60 phiên gần nhất; dưới mức này -> insufficient
    "limited_avg_value_vnd": 5e9,     # dưới mức này -> limited
    "limited_annual": 5,
    "limited_news": 10,
    "liquidity_sessions": 60,
}
SPECIAL_FLAGS = ("securities_firm_needs_special_metrics",)


def avg_traded_value(rows: list[dict], sessions: int) -> float | None:
    tail = [r for r in rows[-sessions:] if r.get("close") is not None and r.get("volume") is not None]
    return sum(r["close"] * r["volume"] for r in tail) / len(tail) if tail else None


def assess(snap: dict, cfg: dict | None = None) -> dict:
    q = {**DEFAULTS, **((cfg or {}).get("quality") or {})}
    rows, annual = snap["prices"]["rows"], snap["financials"]["annual"]
    bad, soft = [], []
    if len(rows) < q["min_price_rows"]:
        bad.append(f"prices_lt_{q['min_price_rows']}")
    if len(annual) < q["min_annual"]:
        bad.append(f"annual_lt_{q['min_annual']}")
    val = avg_traded_value(rows, int(q["liquidity_sessions"]))
    if val is None or val < q["min_avg_value_vnd"]:
        bad.append("illiquid")
    elif val < q["limited_avg_value_vnd"]:
        soft.append("low_liquidity")
    if len(annual) < q["limited_annual"] and "annual_lt_%d" % q["min_annual"] not in bad:
        soft.append(f"annual_lt_{q['limited_annual']}")
    if len(snap["news"]) < q["limited_news"]:
        soft.append("news_few")
    if not snap["company"].get("sector"):
        soft.append("sector_missing")
    if not snap["company"].get("shares_outstanding"):
        soft.append("shares_missing")
    if any(x in snap["meta"]["flags"] for x in SPECIAL_FLAGS):
        soft.append("special_sector_metrics")
    tier = "insufficient" if bad else ("limited" if soft else "full")
    return {"tier": tier, "reasons": bad + soft, "avg_value_vnd": val}


def apply(snap: dict, cfg: dict | None = None) -> dict:
    """Gắn cờ chất lượng vào snapshot (ghi đè cờ cũ của chính mô-đun này) và trả kết quả đánh giá."""
    res = assess(snap, cfg)
    flags = [x for x in snap["meta"]["flags"] if not x.startswith("quality_")]
    flags.append(f"quality_tier_{res['tier']}")
    flags += [f"quality_{r}" for r in res["reasons"]]
    snap["meta"]["flags"] = flags
    return res


def tier_of(snap: dict) -> str | None:
    for x in snap["meta"]["flags"]:
        if x.startswith("quality_tier_"):
            return x[len("quality_tier_"):]
    return None
