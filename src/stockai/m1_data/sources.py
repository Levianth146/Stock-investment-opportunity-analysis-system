"""Lớp mỏng gọi vnstock: cache theo ngày, giãn cách request, retry, thử nhiều nguồn.
Chỉ N2 sửa. Mọi hàm trả về pandas.DataFrame GỐC (chưa chuẩn hóa) - việc chuẩn hóa ở normalize.py.
Nếu vnstock đổi API: chỉ sửa file này."""
from __future__ import annotations

import contextlib
import io
import json
import os
import pickle
import time
from datetime import date, datetime
from pathlib import Path

import pandas as pd

_last_call = 0.0


def _throttle(interval: float) -> None:
    global _last_call
    wait = _last_call + interval - time.time()
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()


def _cache_path(cfg: dict, kind: str, ticker: str, key: str) -> Path:
    d = Path(cfg.get("cache_dir", "data/raw"))
    d.mkdir(parents=True, exist_ok=True)
    safe = f"{kind}_{ticker}_{key}_{date.today().isoformat()}".replace("/", "-").replace(" ", "")
    return d / f"{safe}.pkl"


def _export_csv(cfg: dict, kind: str, ticker: str, key: str, out) -> None:
    """Xuất dữ liệu THÔ ra CSV (đọc được bằng Excel, commit được) vào data/raw/<mã>/ + ghi nguồn vào _sources.json.
    File .pkl ở data/raw/ chỉ là cache, không commit. Lỗi xuất file không được làm hỏng luồng chính."""
    try:
        if not (isinstance(out, tuple) and len(out) == 2 and isinstance(out[0], pd.DataFrame)):
            return
        df, provider = out
        d = Path(cfg.get("cache_dir", "data/raw")) / ticker
        d.mkdir(parents=True, exist_ok=True)
        name = f"{kind}.csv" if kind in ("hist", "overview", "news") else f"{kind}_{key}.csv"
        df.to_csv(d / name, index=False, encoding="utf-8-sig")        # utf-8-sig: Excel hiển thị đúng tiếng Việt
        meta_p = d / "_sources.json"
        meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
        meta[name] = {"provider": provider, "library": "vnstock", "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                      "rows": int(len(df)), "columns": [str(c) for c in df.columns][:60]}
        meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _cached(cfg: dict, kind: str, ticker: str, key: str, producer):
    """Gọi producer() qua cache. Đặt STOCKAI_NO_CACHE=1 để bỏ cache."""
    p = _cache_path(cfg, kind, ticker, key)
    if p.exists() and not os.environ.get("STOCKAI_NO_CACHE"):
        out = pickle.loads(p.read_bytes())
        _export_csv(cfg, kind, ticker, key, out)
        return out
    last: Exception | None = None
    for attempt in range(int(cfg.get("retries", 3))):
        try:
            _throttle(float(cfg.get("request_interval_sec", 3.5)))
            with contextlib.redirect_stdout(io.StringIO()):     # vnstock in banner quảng cáo mỗi lần gọi
                out = producer()
            p.write_bytes(pickle.dumps(out))
            _export_csv(cfg, kind, ticker, key, out)
            return out
        except ImportError:   # thiếu vnstock: thử lại vô ích -> báo ngay
            raise
        except Exception as e:  # noqa: BLE001 - mạng/giới hạn tốc độ: thử lại có backoff
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{kind}({ticker}) lỗi sau {cfg.get('retries', 3)} lần thử: {last}")


def _stock(ticker: str, source: str):
    from vnstock import Vnstock  # import muộn để module import được khi chưa cài vnstock (test offline)
    return Vnstock().stock(symbol=ticker, source=source)


def _try_sources(cfg: dict, label: str, fn):
    """fn(source) -> DataFrame. Trả (df, source) của nguồn đầu tiên có dữ liệu."""
    errs = []
    for src in cfg.get("vnstock_sources", ["VCI"]):
        try:
            df = fn(src)
            if df is not None and len(df) > 0:
                return df, src
            errs.append(f"{src}: rỗng")
        except ImportError:
            raise
        except Exception as e:  # noqa: BLE001
            errs.append(f"{src}: {e}")
    raise RuntimeError(f"{label}: " + " | ".join(errs))


def get_history(ticker: str, start: str, end: str, cfg: dict) -> tuple[pd.DataFrame, str]:
    def go(src):
        return _stock(ticker, src).quote.history(start=start, end=end, interval="1D")
    return _cached(cfg, "hist", ticker, f"{start}_{end}", lambda: _try_sources(cfg, f"giá {ticker}", go))


def _fin_call(stock, kind: str, period: str):
    f = stock.finance
    fn = {"income": f.income_statement, "balance": f.balance_sheet, "cashflow": f.cash_flow, "ratio": f.ratio}[kind]
    for kwargs in ({"period": period, "lang": "en"}, {"period": period}):   # tương thích nhiều bản vnstock
        try:
            df = fn(**kwargs)
            if isinstance(df, pd.DataFrame) and isinstance(df.columns, pd.MultiIndex):
                df.columns = [" | ".join(str(x) for x in c if str(x) != "") for c in df.columns]
            return df
        except TypeError:
            continue
    return fn()


def get_finance(ticker: str, kind: str, period: str, cfg: dict) -> tuple[pd.DataFrame, str]:
    """kind: income | balance | cashflow | ratio ; period: year | quarter"""
    def go(src):
        return _fin_call(_stock(ticker, src), kind, period)
    return _cached(cfg, f"fin-{kind}", ticker, period, lambda: _try_sources(cfg, f"{kind}/{period} {ticker}", go))


def get_overview(ticker: str, cfg: dict) -> tuple[pd.DataFrame, str]:
    def go(src):
        return _stock(ticker, src).company.overview()
    return _cached(cfg, "overview", ticker, "x", lambda: _try_sources(cfg, f"overview {ticker}", go))


def get_news(ticker: str, cfg: dict) -> tuple[pd.DataFrame, str]:
    def go(src):
        return _stock(ticker, src).company.news()
    return _cached(cfg, "news", ticker, "x", lambda: _try_sources(cfg, f"tin {ticker}", go))


def get_industry_peers(ticker: str, cfg: dict) -> list[str]:
    """Dự phòng khi ticker không có trong peers_map: cùng ngành ICB cấp 3 nếu nguồn cho phép. Có thể trả []."""
    try:
        from vnstock import Vnstock
        lst = Vnstock().stock(symbol=ticker, source=cfg.get("vnstock_sources", ["VCI"])[0]).listing
        df = lst.symbols_by_industries()
        cols = {c.lower(): c for c in df.columns}
        sym, ind = cols.get("symbol"), cols.get("icb_name3") or cols.get("icb_name2")
        if not sym or not ind:
            return []
        mine = df.loc[df[sym] == ticker, ind]
        if mine.empty:
            return []
        peers = df.loc[df[ind] == mine.iloc[0], sym].tolist()
        return [p for p in peers if p != ticker][: int(cfg.get("max_peers", 8))]
    except Exception:  # noqa: BLE001
        return []


def get_exchange_map(cfg: dict) -> dict:
    """{mã: sàn}. Overview của VCI không có cột sàn nên tra thêm từ danh sách niêm yết. Lỗi -> {} (chỉ thiếu trường exchange)."""
    def go():
        from vnstock import Listing
        df = Listing(source=cfg.get("vnstock_sources", ["VCI"])[0]).symbols_by_exchange()
        cols = {c.lower(): c for c in df.columns}
        return dict(zip(df[cols["symbol"]], df[cols["exchange"]]))
    try:
        return _cached(cfg, "exchmap", "ALL", "x", go)
    except Exception:  # noqa: BLE001
        return {}
