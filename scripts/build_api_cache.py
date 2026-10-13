"""Xây cache API M2–M8 (debate.mode=template) cho cả hai profile — chỉ mã scored."""
from __future__ import annotations

import argparse
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from stockai.api.store import PROFILES, ResultStore, load_api_cfg  # noqa: E402
from stockai.contracts.helpers import quality_tier  # noqa: E402


def _is_scored_snapshot(store: ResultStore, ticker: str) -> bool:
    try:
        snap = store.load_snapshot(ticker)
    except Exception:
        return False
    tier = quality_tier(snap)
    return tier != "insufficient"


def _build_one(store: ResultStore, ticker: str, profile: str, timeout_sec: float) -> str | None:
    """Trả None nếu ok, hoặc chuỗi lỗi ngắn."""

    def _job() -> None:
        store.get_bundle(ticker, profile, debate_mode="template", force=True)

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_job)
        try:
            fut.result(timeout=timeout_sec)
            return None
        except FuturesTimeout:
            return f"{ticker}/{profile}: timeout>{timeout_sec}s"
        except Exception as e:  # noqa: BLE001
            return f"{ticker}/{profile}: {type(e).__name__}: {str(e)[:120]}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build data/api_cache cho FastAPI")
    parser.add_argument("--timeout", type=float, default=15.0, help="Timeout mỗi mã (giây)")
    parser.add_argument(
        "--profiles",
        default="long_term,swing",
        help="Danh sách profile, cách nhau bởi dấu phẩy",
    )
    parser.add_argument("--limit", type=int, default=0, help="Giới hạn số mã (0=all)")
    args = parser.parse_args(argv)

    cfg = load_api_cfg(_ROOT / "config" / "api.yaml")
    store = ResultStore(cfg)
    profiles = [p.strip() for p in str(args.profiles).split(",") if p.strip()]
    for p in profiles:
        if p not in PROFILES:
            print(f"Profile không hợp lệ: {p}")
            return 2

    tickers = [t for t in store.list_tickers() if _is_scored_snapshot(store, t)]
    if args.limit and args.limit > 0:
        tickers = tickers[: args.limit]

    def _log(msg: str) -> None:
        print(msg, flush=True)

    _log(f"asof={store.asof} scored={len(tickers)} profiles={profiles} timeout={args.timeout}s")
    errors: list[str] = []
    done = 0
    t0 = time.monotonic()
    total = len(tickers) * len(profiles)
    for profile in profiles:
        for i, ticker in enumerate(tickers, 1):
            err = _build_one(store, ticker, profile, args.timeout)
            done += 1
            if err:
                errors.append(err)
                _log(f"[{done}/{total}] FAIL {err}")
            else:
                _log(f"[{done}/{total}] ok {ticker} {profile}")
    elapsed = time.monotonic() - t0
    _log(f"Done: {done} jobs, {len(errors)} errors, {elapsed:.1f}s")
    if errors:
        _log("--- Errors ---")
        for e in errors[:50]:
            _log(e)
        if len(errors) > 50:
            _log(f"... and {len(errors) - 50} more")
    return 1 if errors else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
