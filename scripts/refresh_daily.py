#!/usr/bin/env python3
"""Làm mới dữ liệu hàng ngày (feature 017a).

Quy trình (sau 15:30 ICT khuyến nghị):
1. Khoá file chống chạy trùng
2. Làm mới giá/chỉ số (và tin tùy chọn) incremental qua fetch_universe --refresh-news-prices
   — chia lô 100 mã; một lô lỗi không dừng các lô khác
3. Kiểm phủ ≥95% trên mẫu số = mã KHÔNG bị skipped_early_exit (thanh khoản thấp cố ý bỏ);
   full+limited phải cập nhật 100%; dưới ngưỡng → thoát lỗi, KHÔNG build cache
4. Cập nhật ``config/api.yaml`` asof rồi chạy lại scoring (build_api_cache → M2–M8 template)
   — ``--skip-fetch`` vẫn chạy bước này độc lập
5. Ghi ``data/api_cache/_refreshed_at.json``
6. (tuỳ chọn) ``--prefetch-debate N``

Retry mạng: mỗi lô thử lại với backoff. Log rõ; không in secret.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
ICT = ZoneInfo("Asia/Ho_Chi_Minh")
LOCK_PATH = ROOT / "data" / "api_cache" / "_refresh_daily.lock"
REFRESHED_PATH = ROOT / "data" / "api_cache" / "_refreshed_at.json"
API_YAML = ROOT / "config" / "api.yaml"

# Tên file snapshot hợp lệ: TICKER_YYYY-MM-DD.json (bỏ _* và tên lệch)
_SNAP_NAME_RE = re.compile(r"^([A-Z0-9]+)_(\d{4}-\d{2}-\d{2})\.json$", re.IGNORECASE)

BATCH_SIZE = 100
MIN_COVERAGE = 0.95
_SCORED_TIERS = frozenset({"full", "limited"})
_EARLY_EXIT_FLAG = "fetch_skipped_early"

_log = logging.getLogger("refresh_daily")

# Kiểu gọi fetch một lô: (tickers, as_of, ...) → exit code (0 = ok)
FetchBatchFn = Callable[[list[str], str], int]


def _configure_stdio_utf8() -> None:
    """Ép stdout/stderr UTF-8 để in tiếng Việt an toàn trên Windows cp1252."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if not callable(reconfigure):
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _safe_print(msg: str) -> None:
    """In ra console — không chết vì UnicodeEncodeError (cp1252)."""
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode("ascii", "replace").decode("ascii"), flush=True)


def _parse(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Daily refresh (prices → score → cache)")
    p.add_argument("--as-of", default="", help="YYYY-MM-DD (mặc định: hôm nay ICT)")
    p.add_argument("--profile", default="long_term")
    p.add_argument(
        "--snapshots-dir",
        default="data/snapshots_ext",
        help="Thư mục snapshot (wide)",
    )
    p.add_argument(
        "--universe",
        default="HOSE",
        help="Universe cho refresh-news-prices (mặc định HOSE)",
    )
    p.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Bỏ fetch giá; vẫn cập nhật asof rồi re-score M3–M7 + build_api_cache",
    )
    p.add_argument(
        "--skip-cache",
        action="store_true",
        help="Bỏ build_api_cache",
    )
    p.add_argument(
        "--prefetch-debate",
        type=int,
        default=0,
        metavar="N",
        help="Sau scoring: chạy run_debate_batch --top N (0 = bỏ qua)",
    )
    p.add_argument("--pause-sec", type=float, default=2.0)
    p.add_argument("--max-live-calls", type=int, default=12)
    p.add_argument("--retries", type=int, default=3)
    p.add_argument("--timeout-per-ticker", type=float, default=20.0)
    p.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help=f"Số mã mỗi lần gọi fetch_universe (mặc định {BATCH_SIZE})",
    )
    p.add_argument(
        "--min-coverage",
        type=float,
        default=MIN_COVERAGE,
        help=f"Ngưỡng phủ file as_of trước khi build cache (mặc định {MIN_COVERAGE})",
    )
    p.add_argument(
        "--allow-before-close",
        action="store_true",
        help="Cho phép chạy trước 15:30 ICT (mặc định cảnh báo)",
    )
    return p.parse_args(argv)

class FileLock:
    """Khoá file đơn giản (Windows/POSIX) — không dùng portalocker để giảm phụ thuộc."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._fd: int | None = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self.path.exists():
                # stale lock > 6h → xoá
                age = time.time() - self.path.stat().st_mtime
                if age > 6 * 3600:
                    self.path.unlink(missing_ok=True)
                else:
                    return False
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
            self._fd = os.open(str(self.path), flags)
            os.write(
                self._fd,
                f"pid={os.getpid()} started={datetime.now(ICT).isoformat()}\n".encode(),
            )
            return True
        except FileExistsError:
            return False
        except OSError as e:
            _log.error("lock fail: %s", type(e).__name__)
            return False

    def release(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass


def parse_snapshot_filename(name: str) -> tuple[str, str] | None:
    """Trả (TICKER, YYYY-MM-DD) nếu tên khớp; bỏ qua _* và tên lệch."""
    if not name or name.startswith("_"):
        return None
    m = _SNAP_NAME_RE.fullmatch(name)
    if not m:
        return None
    return m.group(1).upper(), m.group(2)


def collect_tickers(
    snap_dir: Path,
    as_of: str | None = None,
    *,
    only_asof: bool = False,
) -> list[str]:
    """Danh sách mã duy nhất từ file ``TICKER_YYYY-MM-DD.json``.

    Mặc định: mọi ngày asof, một entry/mã (phù hợp refresh sang ngày mới / re-run).
    ``only_asof=True``: chỉ mã đã có file đúng ``as_of``.
    Bỏ tên bắt đầu ``_`` và file không khớp pattern.
    """
    if not snap_dir.is_dir():
        return []
    by_asof: set[str] = set()
    all_tickers: set[str] = set()
    for p in snap_dir.iterdir():
        if not p.is_file():
            continue
        parsed = parse_snapshot_filename(p.name)
        if parsed is None:
            continue
        ticker, d = parsed
        all_tickers.add(ticker)
        if as_of and d == as_of:
            by_asof.add(ticker)
    if only_asof:
        if not as_of:
            raise ValueError("only_asof requires as_of")
        return sorted(by_asof)
    return sorted(all_tickers)

def chunk_tickers(tickers: list[str], batch_size: int = BATCH_SIZE) -> list[list[str]]:
    """Chia danh sách mã thành các lô kích thước ``batch_size``."""
    if batch_size <= 0:
        raise ValueError("batch_size must be > 0")
    return [tickers[i : i + batch_size] for i in range(0, len(tickers), batch_size)]


def count_asof_files(
    snap_dir: Path, as_of: str, tickers: list[str]
) -> tuple[int, list[str]]:
    """Đếm bao nhiêu mã trong ``tickers`` đã có ``{T}_{as_of}.json``.

    Trả (số đã có, danh sách thiếu đã sắp xếp).
    """
    missing: list[str] = []
    ok = 0
    for t in tickers:
        path = snap_dir / f"{t}_{as_of}.json"
        if path.is_file():
            ok += 1
        else:
            missing.append(t)
    return ok, missing


def latest_snapshot_path(snap_dir: Path, ticker: str) -> Path | None:
    """File snapshot mới nhất (theo ngày trong tên) của một mã."""
    best: Path | None = None
    best_date = ""
    if not snap_dir.is_dir():
        return None
    prefix = f"{ticker}_"
    for p in snap_dir.iterdir():
        if not p.is_file() or not p.name.upper().startswith(prefix.upper()):
            continue
        parsed = parse_snapshot_filename(p.name)
        if parsed is None:
            continue
        t, d = parsed
        if t != ticker.upper():
            continue
        if d > best_date:
            best_date = d
            best = p
    return best


def _read_meta_flags(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return []
    flags = (data.get("meta") or {}).get("flags") or []
    return [f for f in flags if isinstance(f, str)]


def quality_tier_from_snapshot_file(path: Path) -> str | None:
    """Đọc ``quality_tier_*`` từ file snapshot; None nếu thiếu."""
    for f in _read_meta_flags(path):
        if f.startswith("quality_tier_"):
            return f[len("quality_tier_") :] or None
    return None


def is_skipped_early_exit(snap_dir: Path, ticker: str) -> bool:
    """True nếu snapshot mới nhất còn ``fetch_skipped_early`` (bỏ refresh cố ý)."""
    path = latest_snapshot_path(snap_dir, ticker)
    if path is None:
        return False
    return _EARLY_EXIT_FLAG in _read_meta_flags(path)


def classify_refresh_coverage(
    snap_dir: Path, as_of: str, tickers: list[str]
) -> dict[str, object]:
    """Phân loại phủ sau fetch.

    Mẫu số phủ = mã không thuộc skipped_early_exit.
    Trả dict: updated (int), skipped_early_exit (list), failed (list),
    denominator (int), missing_full_limited (list).
    """
    updated_set: set[str] = set()
    missing: list[str] = []
    for t in tickers:
        if (snap_dir / f"{t}_{as_of}.json").is_file():
            updated_set.add(t)
        else:
            missing.append(t)

    skipped: list[str] = []
    failed: list[str] = []
    for t in missing:
        if is_skipped_early_exit(snap_dir, t):
            skipped.append(t)
        else:
            failed.append(t)

    missing_full_limited: list[str] = []
    for t in tickers:
        if t in updated_set:
            continue
        # Bậc từ snapshot mới nhất (early-exit thường insufficient)
        path = latest_snapshot_path(snap_dir, t)
        if path is None:
            continue
        tier = quality_tier_from_snapshot_file(path)
        if tier in _SCORED_TIERS:
            missing_full_limited.append(t)

    denom = len(tickers) - len(skipped)
    return {
        "updated": len(updated_set),
        "skipped_early_exit": skipped,
        "failed": failed,
        "denominator": denom,
        "missing_full_limited": missing_full_limited,
    }


def _run(cmd: list[str], *, retries: int = 3, sleep_fn: Callable[[float], None] | None = None) -> int:
    sleeper = sleep_fn or time.sleep
    last = 1
    for attempt in range(1, retries + 1):
        _log.info("run[%s/%s]: %s", attempt, retries, " ".join(cmd))
        last = int(subprocess.call(cmd, cwd=str(ROOT)))
        if last == 0:
            return 0
        _log.warning("exit=%s — retry sau %ss", last, 5 * attempt)
        sleeper(5 * attempt)
    return last


def make_fetch_batch_fn(
    *,
    snap_dir: Path,
    universe: str,
    retries: int,
    sleep_fn: Callable[[float], None] | None = None,
) -> FetchBatchFn:
    """Tạo hàm gọi ``fetch_universe --refresh-news-prices --in-place`` cho một lô."""

    def _fetch(batch: list[str], as_of: str) -> int:
        cmd = [
            sys.executable,
            str(ROOT / "scripts" / "fetch_universe.py"),
            "--as-of",
            as_of,
            "--universe",
            universe,
            "--refresh-news-prices",
            "--in-place",
            "--out-dir",
            str(snap_dir),
            "--no-google",
            "--tickers",
            ",".join(batch),
        ]
        return _run(cmd, retries=retries, sleep_fn=sleep_fn)

    return _fetch


def run_fetch_batches(
    tickers: list[str],
    as_of: str,
    *,
    fetch_fn: FetchBatchFn,
    batch_size: int = BATCH_SIZE,
) -> tuple[list[list[str]], list[str]]:
    """Gọi fetch theo lô; lô lỗi không dừng các lô khác.

    Trả (danh_sách_lô, failed_tickers).
    """
    batches = chunk_tickers(tickers, batch_size)
    failed: list[str] = []
    _log.info(
        "fetch: %s mã → %s lô (size≤%s)",
        len(tickers),
        len(batches),
        batch_size,
    )
    for i, batch in enumerate(batches, start=1):
        _log.info("lô %s/%s (%s mã): %s…%s", i, len(batches), len(batch), batch[0], batch[-1])
        rc = fetch_fn(batch, as_of)
        if rc != 0:
            _log.error("lô %s/%s thất bại exit=%s — tiếp tục lô khác", i, len(batches), rc)
            failed.extend(batch)
        else:
            _log.info("lô %s/%s ok", i, len(batches))
    if failed:
        _log.warning("mã thuộc lô thất bại (%s): %s", len(failed), ",".join(failed[:40]))
    return batches, failed


def coverage_ok(updated: int, total: int, min_coverage: float = MIN_COVERAGE) -> bool:
    if total <= 0:
        return False
    return (updated / total) >= min_coverage


def _write_refreshed_at(as_of: str) -> None:
    REFRESHED_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "asof": as_of,
        "refreshed_at": datetime.now(ICT).isoformat(timespec="seconds"),
    }
    REFRESHED_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    _log.info("wrote %s", REFRESHED_PATH)


def _update_api_asof(as_of: str) -> None:
    """Cập nhật dòng asof trong config/api.yaml (giữ nguyên phần còn lại)."""
    if not API_YAML.is_file():
        return
    text = API_YAML.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    done = False
    for line in lines:
        if not done and line.lstrip().startswith("asof:"):
            indent = line[: len(line) - len(line.lstrip())]
            # giữ comment sau nếu có
            comment = ""
            if "#" in line:
                comment = "  #" + line.split("#", 1)[1].rstrip("\n")
                if comment.endswith("\r"):
                    comment = comment[:-1]
            out.append(f"{indent}asof: {as_of}{comment}\n")
            done = True
        else:
            out.append(line if line.endswith("\n") else line + "\n")
    if done:
        API_YAML.write_text("".join(out), encoding="utf-8")
        _log.info("api.yaml asof → %s", as_of)


def main(
    argv: list[str] | None = None,
    *,
    fetch_fn: FetchBatchFn | None = None,
    sleep_fn: Callable[[float], None] | None = None,
) -> int:
    _configure_stdio_utf8()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    args = _parse(argv)
    as_of = (args.as_of or "").strip() or date.today().isoformat()
    now = datetime.now(ICT)
    if now.hour < 15 or (now.hour == 15 and now.minute < 30):
        if not args.allow_before_close:
            _log.warning(
                "Chưa tới 15:30 ICT (hiện %s) — tiếp tục; dùng --allow-before-close để im lặng",
                now.strftime("%H:%M"),
            )

    lock = FileLock(LOCK_PATH)
    if not lock.acquire():
        _log.error("Đang có refresh khác chạy (lock %s)", LOCK_PATH)
        return 2

    try:
        snap_dir = Path(args.snapshots_dir)
        if not snap_dir.is_absolute():
            snap_dir = ROOT / snap_dir

        batch_size = int(args.batch_size or BATCH_SIZE)
        min_cov = float(args.min_coverage if args.min_coverage is not None else MIN_COVERAGE)

        if not args.skip_fetch:
            # Unique mọi ngày — không giới hạn as_of hiện có (tránh bỏ sót khi re-run)
            tickers = collect_tickers(snap_dir, as_of=as_of, only_asof=False)
            if not tickers:
                _log.error("Không có snapshot hợp lệ trong %s", snap_dir)
                return 1

            runner = fetch_fn or make_fetch_batch_fn(
                snap_dir=snap_dir,
                universe=args.universe,
                retries=int(args.retries),
                sleep_fn=sleep_fn,
            )
            batches, failed_batch = run_fetch_batches(
                tickers,
                as_of,
                fetch_fn=runner,
                batch_size=batch_size,
            )
            _log.info("đã gọi %s lô fetch", len(batches))

            cov = classify_refresh_coverage(snap_dir, as_of, tickers)
            updated = int(cov["updated"])  # type: ignore[arg-type]
            skipped = list(cov["skipped_early_exit"])  # type: ignore[arg-type]
            failed = list(cov["failed"])  # type: ignore[arg-type]
            denom = int(cov["denominator"])  # type: ignore[arg-type]
            missing_fl = list(cov["missing_full_limited"])  # type: ignore[arg-type]

            # Gộp mã thuộc lô subprocess fail (chưa có trong failed nếu đã có file)
            for t in failed_batch:
                if t not in failed and t not in skipped and not (snap_dir / f"{t}_{as_of}.json").is_file():
                    failed.append(t)

            fail_preview = failed[:50]
            fail_more = f" (+{len(failed) - 50})" if len(failed) > 50 else ""
            msg = (
                f"đã cập nhật {updated}/{denom}"
                f" (skipped_early_exit={len(skipped)}, failed={len(failed)})"
            )
            _log.info("%s", msg)
            _safe_print(msg)
            _safe_print(f"skipped_early_exit: {len(skipped)}")
            _safe_print(f"failed: {fail_preview}{fail_more}")
            if failed_batch:
                fb_preview = failed_batch[:50]
                fb_more = f" (+{len(failed_batch) - 50})" if len(failed_batch) > 50 else ""
                fail_msg = f"lô thất bại ({len(failed_batch)} mã): {fb_preview}{fb_more}"
                _log.warning("%s", fail_msg)
                _safe_print(fail_msg)

            if missing_fl:
                fl_preview = missing_fl[:50]
                fl_more = f" (+{len(missing_fl) - 50})" if len(missing_fl) > 50 else ""
                err = (
                    f"full+limited thiếu cập nhật ({len(missing_fl)}): "
                    f"{fl_preview}{fl_more}"
                )
                _log.error("%s", err)
                _safe_print(err)
                return 1

            if not coverage_ok(updated, denom, min_cov):
                _log.error(
                    "phủ %s/%s < %.0f%% — bỏ build_api_cache (tránh cache asof lẫn)",
                    updated,
                    denom,
                    min_cov * 100,
                )
                return 1
        else:
            _log.info("skip fetch — vẫn re-score M3–M7 + build_api_cache với as_of=%s", as_of)

        # asof phải vào api.yaml TRƯỚC build_api_cache để M3–M7 chạy đúng ngày mới
        _update_api_asof(as_of)
        _log.info("re-score M3–M7 + build_api_cache as_of=%s", as_of)

        if not args.skip_cache:
            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "build_api_cache.py"),
                "--timeout",
                str(args.timeout_per_ticker),
                "--profiles",
                "long_term,swing",
            ]
            rc = _run(cmd, retries=max(1, int(args.retries) - 1), sleep_fn=sleep_fn)
            if rc != 0:
                _log.error("build_api_cache thất bại exit=%s", rc)
                return rc
        else:
            _log.info("skip cache")

        _write_refreshed_at(as_of)

        if int(args.prefetch_debate or 0) > 0:
            cmd = [
                sys.executable,
                str(ROOT / "scripts" / "run_debate_batch.py"),
                "--as-of",
                as_of,
                "--profile",
                args.profile,
                "--top",
                str(int(args.prefetch_debate)),
                "--pause-sec",
                str(args.pause_sec),
                "--max-live-calls",
                str(args.max_live_calls),
            ]
            rc = _run(cmd, retries=1, sleep_fn=sleep_fn)
            if rc != 0:
                _log.warning("prefetch-debate exit=%s (không fail cả job)", rc)
        else:
            _log.info("skip prefetch-debate")

        _log.info("refresh_daily xong as_of=%s", as_of)
        return 0
    finally:
        lock.release()


if __name__ == "__main__":
    raise SystemExit(main())