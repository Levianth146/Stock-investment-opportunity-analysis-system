"""M1 - thu thập dữ liệu (N2). Người làm chỉ sửa trong m1_data/.

Việc cần làm theo thứ tự (mỗi cái 1 hàm, 1 commit nhỏ):
  1. fetch_prices      -> snapshot["prices"], giá ĐÃ ĐIỀU CHỈNH, cửa sổ 5 năm lùi từ as_of
  2. fetch_index       -> snapshot["index"]   (VNINDEX)
  3. fetch_financials  -> snapshot["financials"] (annual + quarterly, published_at là ngày công bố)
  4. fetch_company     -> snapshot["company"], snapshot["peers"]  (is_bank để M2/M4 rẽ nhánh)
  5. fetch_news        -> snapshot["news"]
Mỗi nguồn dùng phải thêm 1 dòng vào snapshot["sources"] (id, name, url, fetched_at).
Lỗi 1 khối thì set data_status[khối]="missing"/"partial" + flags, KHÔNG làm sập cả snapshot.
Trước khi lưu: check_no_lookahead(snapshot) phải trả về [].
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from stockai.contracts.helpers import check_no_lookahead
from stockai.contracts.schemas import assert_valid


def _window_start(as_of: str, years: int) -> str:
    d = datetime.strptime(as_of, "%Y-%m-%d")
    return (d - timedelta(days=365 * years)).strftime("%Y-%m-%d")


def fetch_prices(ticker: str, start: str, as_of: str, cfg: dict) -> tuple[dict, dict]:
    """TODO(N2): trả về (prices_block, source_dict). Hiện chưa làm."""
    raise NotImplementedError


def fetch_index(symbol: str, start: str, as_of: str, cfg: dict) -> tuple[dict, dict]:
    raise NotImplementedError


def fetch_financials(ticker: str, as_of: str, cfg: dict) -> tuple[dict, list[dict]]:
    raise NotImplementedError


def fetch_company(ticker: str, as_of: str, cfg: dict) -> tuple[dict, list[dict], dict]:
    """Trả về (company, peers, source)."""
    raise NotImplementedError


def fetch_news(ticker: str, start: str, as_of: str, cfg: dict) -> tuple[list[dict], dict]:
    raise NotImplementedError


def build_snapshot(ticker: str, as_of: str, cfg: dict) -> dict:
    """Ghép 5 khối thành snapshot. Khối nào lỗi thì đánh dấu thiếu, vẫn trả về snapshot hợp lệ."""
    years = cfg.get("window_years", 5)
    start = _window_start(as_of, years)
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    snap = {
        "meta": {"schema_version": "1.0", "ticker": ticker, "as_of": as_of, "window_start": start,
                 "fetched_at": now, "synthetic": False, "flags": [],
                 "data_status": {k: "missing" for k in ("prices", "index", "financials", "company", "peers", "news")}},
        "company": {"name": ticker, "exchange": "", "sector": "", "is_bank": False},
        "prices": {"adjusted": True, "source_id": "", "rows": []},
        "index": {"symbol": cfg.get("index_symbol", "VNINDEX"), "source_id": "", "rows": []},
        "financials": {"unit": cfg.get("financial_unit", "VND"), "annual": [], "quarterly": []},
        "peers": [], "news": [], "sources": [],
    }
    steps = [
        ("prices", lambda: fetch_prices(ticker, start, as_of, cfg)),
        ("index", lambda: fetch_index(snap["index"]["symbol"], start, as_of, cfg)),
        ("financials", lambda: fetch_financials(ticker, as_of, cfg)),
        ("company", lambda: fetch_company(ticker, as_of, cfg)),
        ("news", lambda: fetch_news(ticker, start, as_of, cfg)),
    ]
    for name, fn in steps:
        try:
            res = fn()
        except NotImplementedError:
            snap["meta"]["flags"].append(f"m1_{name}_not_implemented")
            continue
        except Exception as e:  # noqa: BLE001 - 1 nguồn lỗi không được làm sập pipeline
            snap["meta"]["flags"].append(f"m1_{name}_error: {e}")
            continue
        if name == "prices":
            snap["prices"], src = res; snap["sources"].append(src)
            snap["meta"]["data_status"]["prices"] = "ok" if snap["prices"]["rows"] else "missing"
        elif name == "index":
            snap["index"], src = res; snap["sources"].append(src)
            snap["meta"]["data_status"]["index"] = "ok" if snap["index"]["rows"] else "missing"
        elif name == "financials":
            snap["financials"], srcs = res; snap["sources"].extend(srcs)
            snap["meta"]["data_status"]["financials"] = "ok" if snap["financials"]["annual"] else "missing"
        elif name == "company":
            snap["company"], snap["peers"], src = res; snap["sources"].append(src)
            snap["meta"]["data_status"]["company"] = "ok"
            snap["meta"]["data_status"]["peers"] = "ok" if snap["peers"] else "missing"
        elif name == "news":
            snap["news"], src = res; snap["sources"].append(src)
            snap["meta"]["data_status"]["news"] = "ok" if snap["news"] else "missing"
    assert_valid(snap, "snapshot")
    bad = check_no_lookahead(snap)
    if bad:
        raise ValueError("Snapshot vi phạm as_of (look-ahead): " + "; ".join(bad[:5]))
    return snap


def save_snapshot(snap: dict, out_dir: str = "data/snapshots") -> Path:
    p = Path(out_dir) / f"{snap['meta']['ticker']}_{snap['meta']['as_of']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    return p


def load_snapshot(path: str) -> dict:
    snap = json.loads(Path(path).read_text(encoding="utf-8"))
    assert_valid(snap, "snapshot")
    return snap
