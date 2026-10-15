"""017a-fix4: refresh_daily — mẫu số phủ (bỏ early-exit), UTF-8, --skip-fetch re-score."""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "refresh_daily.py"


def _load_rd():
    spec = importlib.util.spec_from_file_location("refresh_daily_017a", SCRIPT)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


rd = _load_rd()


@pytest.fixture(autouse=True)
def _no_side_effects(monkeypatch, tmp_path):
    """Không chạy script con thật (sync_shares/build thống kê ngành) và không ghi config/api.yaml thật."""
    monkeypatch.setattr(rd, "_run", lambda cmd, **kw: 0)
    fake_yaml = tmp_path / "_api_default.yaml"
    fake_yaml.write_text("asof: 2026-01-01\n", encoding="utf-8")
    monkeypatch.setattr(rd, "API_YAML", fake_yaml)


def _touch_snap(
    dir_: Path,
    ticker: str,
    asof: str,
    *,
    body: dict | None = None,
    flags: list[str] | None = None,
) -> Path:
    dir_.mkdir(parents=True, exist_ok=True)
    path = dir_ / f"{ticker}_{asof}.json"
    if body is not None:
        payload = body
    else:
        payload = {
            "meta": {
                "ticker": ticker,
                "as_of": asof,
                "flags": list(flags or []),
            }
        }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def test_parse_snapshot_filename():
    assert rd.parse_snapshot_filename("AAA_2026-10-08.json") == ("AAA", "2026-10-08")
    assert rd.parse_snapshot_filename("vcb_2026-10-14.json") == ("VCB", "2026-10-14")
    assert rd.parse_snapshot_filename("_meta_2026-10-08.json") is None
    assert rd.parse_snapshot_filename("notes.txt") is None
    assert rd.parse_snapshot_filename("AAA.json") is None
    assert rd.parse_snapshot_filename("AAA_2026-10-08_bak.json") is None


def test_collect_tickers_one_per_ticker_multi_asof(tmp_path):
    """Nhiều ngày asof + file lệch → một entry/mã; bỏ _*."""
    old, new = "2026-10-08", "2026-10-14"
    for t in ("AAA", "BBB", "CCC"):
        _touch_snap(tmp_path, t, old)
    _touch_snap(tmp_path, "AAA", new)  # AAA có 2 ngày
    _touch_snap(tmp_path, "DDD", new)
    (tmp_path / "_ignore_2026-10-08.json").write_text("{}", encoding="utf-8")
    (tmp_path / "weird.json").write_text("{}", encoding="utf-8")
    (tmp_path / "FOO_not-a-date.json").write_text("{}", encoding="utf-8")

    # Mặc định: unique mọi ngày (dùng cho refresh)
    assert rd.collect_tickers(tmp_path, as_of=new) == ["AAA", "BBB", "CCC", "DDD"]
    assert rd.collect_tickers(tmp_path, as_of=None) == ["AAA", "BBB", "CCC", "DDD"]

    # only_asof: chỉ mã đã có file đúng ngày
    assert rd.collect_tickers(tmp_path, as_of=new, only_asof=True) == ["AAA", "DDD"]
    assert rd.collect_tickers(tmp_path, as_of=old, only_asof=True) == ["AAA", "BBB", "CCC"]


def test_chunk_707_tickers_eight_batches():
    tickers = [f"T{i:04d}" for i in range(707)]
    batches = rd.chunk_tickers(tickers, 100)
    assert len(batches) == 8
    assert sum(len(b) for b in batches) == 707
    assert [len(b) for b in batches] == [100, 100, 100, 100, 100, 100, 100, 7]


def test_run_fetch_batches_isolates_failure(tmp_path):
    """Một lô lỗi không dừng lô khác; failed_tickers ghi đủ mã lô đó."""
    tickers = [f"T{i:03d}" for i in range(250)]  # 3 lô: 100+100+50
    calls: list[list[str]] = []

    def fake_fetch(batch: list[str], as_of: str) -> int:
        calls.append(list(batch))
        # Lô thứ 2 (index 1) luôn fail
        if batch and batch[0] == "T100":
            return 1
        # Lô ok → ghi file as_of giả
        for t in batch:
            _touch_snap(tmp_path, t, as_of)
        return 0

    batches, failed = rd.run_fetch_batches(
        tickers, "2026-10-15", fetch_fn=fake_fetch, batch_size=100
    )
    assert len(batches) == 3
    assert len(calls) == 3
    assert failed == tickers[100:200]
    # Lô 1 và 3 vẫn chạy
    assert (tmp_path / "T000_2026-10-15.json").is_file()
    assert (tmp_path / "T249_2026-10-15.json").is_file()
    assert not (tmp_path / "T100_2026-10-15.json").is_file()


def test_coverage_below_threshold_skips_build_api_cache(tmp_path, monkeypatch, capsys):
    """Dưới ngưỡng → không chạy build_api_cache (kể cả khi không --skip-cache)."""
    as_of = "2026-10-15"
    old = "2026-10-08"
    for i in range(20):
        _touch_snap(tmp_path, f"T{i:02d}", old)

    def fake_fetch(batch: list[str], _as_of: str) -> int:
        # Chỉ 10/20 = 50%
        for t in batch[:10]:
            _touch_snap(tmp_path, t, as_of)
        return 0

    ran_cache = {"n": 0}

    def fake_run(cmd: list[str], *, retries: int = 3, sleep_fn=None) -> int:  # noqa: ARG001
        if "build_api_cache.py" in " ".join(cmd):
            ran_cache["n"] += 1
        return 0

    monkeypatch.setattr(rd, "_run", fake_run)
    monkeypatch.setattr(rd, "LOCK_PATH", tmp_path / "_lock")
    monkeypatch.setattr(rd, "REFRESHED_PATH", tmp_path / "_refreshed.json")
    monkeypatch.setattr(rd, "API_YAML", tmp_path / "no_api.yaml")

    rc = rd.main(
        [
            "--as-of",
            as_of,
            "--snapshots-dir",
            str(tmp_path),
            "--allow-before-close",
            "--retries",
            "1",
            "--min-coverage",
            "0.95",
        ],
        fetch_fn=fake_fetch,
        sleep_fn=lambda _s: None,
    )
    assert rc == 1
    assert ran_cache["n"] == 0
    assert "đã cập nhật 10/20" in capsys.readouterr().out


def test_full_coverage_707_fake_fetch_eight_batches(tmp_path, monkeypatch, capsys):
    """707 mã → 8 lô; phủ đủ → tiếp tục (skip-cache để không mạng)."""
    as_of = "2026-10-15"
    old = "2026-10-08"
    tickers = [f"T{i:04d}" for i in range(707)]
    for t in tickers:
        _touch_snap(tmp_path, t, old)

    call_sizes: list[int] = []

    def fake_fetch(batch: list[str], _as_of: str) -> int:
        call_sizes.append(len(batch))
        for t in batch:
            _touch_snap(tmp_path, t, as_of)
        return 0

    monkeypatch.setattr(rd, "LOCK_PATH", tmp_path / "_lock")
    monkeypatch.setattr(rd, "REFRESHED_PATH", tmp_path / "_refreshed.json")
    monkeypatch.setattr(rd, "API_YAML", tmp_path / "no_api.yaml")

    rc = rd.main(
        [
            "--as-of",
            as_of,
            "--snapshots-dir",
            str(tmp_path),
            "--skip-cache",
            "--allow-before-close",
            "--retries",
            "1",
            "--batch-size",
            "100",
        ],
        fetch_fn=fake_fetch,
        sleep_fn=lambda _s: None,
    )
    assert rc == 0
    assert call_sizes == [100, 100, 100, 100, 100, 100, 100, 7]
    out = capsys.readouterr().out
    assert "đã cập nhật 707/707" in out
    assert (tmp_path / "_refreshed.json").is_file()


def test_no_500_cap_in_source():
    """Đảm bảo không còn tickers[:500] trong script."""
    text = SCRIPT.read_text(encoding="utf-8")
    assert "tickers[:500]" not in text
    assert "BATCH_SIZE = 100" in text


def test_classify_early_exit_excluded_from_denominator(tmp_path):
    """skipped_early_exit không tính vào mẫu số; failed liệt kê riêng."""
    as_of = "2026-10-15"
    old = "2026-10-08"
    # 8 mã thường + 2 early-exit
    for i in range(8):
        _touch_snap(tmp_path, f"T{i:02d}", old, flags=["quality_tier_full"])
    for t in ("ILL1", "ILL2"):
        _touch_snap(
            tmp_path,
            t,
            old,
            flags=["fetch_skipped_early", "quality_tier_insufficient", "quality_illiquid"],
        )
    # Chỉ cập nhật 8 mã thường
    for i in range(8):
        _touch_snap(tmp_path, f"T{i:02d}", as_of, flags=["quality_tier_full"])

    tickers = [f"T{i:02d}" for i in range(8)] + ["ILL1", "ILL2"]
    cov = rd.classify_refresh_coverage(tmp_path, as_of, tickers)
    assert cov["updated"] == 8
    assert cov["denominator"] == 8  # 10 - 2 early-exit
    assert sorted(cov["skipped_early_exit"]) == ["ILL1", "ILL2"]
    assert cov["failed"] == []
    assert cov["missing_full_limited"] == []
    assert rd.coverage_ok(cov["updated"], cov["denominator"], 0.95)


def test_full_limited_missing_forces_nonzero_exit(tmp_path, monkeypatch, capsys):
    """Thiếu dù chỉ 1 mã full/limited → exit ≠ 0 dù phủ tổng vẫn cao."""
    as_of = "2026-10-15"
    old = "2026-10-08"
    for i in range(20):
        _touch_snap(tmp_path, f"T{i:02d}", old, flags=["quality_tier_full"])

    def fake_fetch(batch: list[str], _as_of: str) -> int:
        # Cập nhật 19/20 — đủ 95% nhưng thiếu 1 full
        for t in batch:
            if t == "T19":
                continue
            _touch_snap(tmp_path, t, as_of, flags=["quality_tier_full"])
        return 0

    ran_cache = {"n": 0}

    def fake_run(cmd: list[str], *, retries: int = 3, sleep_fn=None) -> int:  # noqa: ARG001
        if "build_api_cache.py" in " ".join(cmd):
            ran_cache["n"] += 1
        return 0

    monkeypatch.setattr(rd, "_run", fake_run)
    monkeypatch.setattr(rd, "LOCK_PATH", tmp_path / "_lock")
    monkeypatch.setattr(rd, "REFRESHED_PATH", tmp_path / "_refreshed.json")
    monkeypatch.setattr(rd, "API_YAML", tmp_path / "no_api.yaml")

    rc = rd.main(
        [
            "--as-of",
            as_of,
            "--snapshots-dir",
            str(tmp_path),
            "--allow-before-close",
            "--retries",
            "1",
            "--min-coverage",
            "0.95",
        ],
        fetch_fn=fake_fetch,
        sleep_fn=lambda _s: None,
    )
    assert rc == 1
    assert ran_cache["n"] == 0
    out = capsys.readouterr().out
    assert "full+limited thiếu cập nhật" in out
    assert "T19" in out


def test_early_exit_not_counted_missing_in_main_log(tmp_path, monkeypatch, capsys):
    """Log: đã cập nhật X/Y với Y = total - skipped_early_exit."""
    as_of = "2026-10-15"
    old = "2026-10-08"
    for i in range(18):
        _touch_snap(tmp_path, f"T{i:02d}", old, flags=["quality_tier_limited"])
    for t in ("ILL1", "ILL2"):
        _touch_snap(
            tmp_path,
            t,
            old,
            flags=["fetch_skipped_early", "quality_tier_insufficient"],
        )

    def fake_fetch(batch: list[str], _as_of: str) -> int:
        for t in batch:
            if t.startswith("ILL"):
                continue  # mô phỏng skipped_early_exit — không ghi file mới
            _touch_snap(tmp_path, t, as_of, flags=["quality_tier_limited"])
        return 0

    monkeypatch.setattr(rd, "LOCK_PATH", tmp_path / "_lock")
    monkeypatch.setattr(rd, "REFRESHED_PATH", tmp_path / "_refreshed.json")
    monkeypatch.setattr(rd, "API_YAML", tmp_path / "no_api.yaml")

    rc = rd.main(
        [
            "--as-of",
            as_of,
            "--snapshots-dir",
            str(tmp_path),
            "--skip-cache",
            "--allow-before-close",
            "--retries",
            "1",
        ],
        fetch_fn=fake_fetch,
        sleep_fn=lambda _s: None,
    )
    assert rc == 0
    out = capsys.readouterr().out
    assert "đã cập nhật 18/18" in out
    assert "skipped_early_exit: 2" in out


def test_safe_print_vietnamese_on_cp1252_stdout(monkeypatch):
    """In chữ 'đ' với stdout cp1252 không raise UnicodeEncodeError."""
    buf = io.BytesIO()
    narrow = io.TextIOWrapper(buf, encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", narrow)
    # Không reconfigure — buộc đi qua nhánh replace của _safe_print
    rd._safe_print("đã cập nhật 10/10")
    narrow.flush()
    # Không exception là đủ; nội dung có thể bị thay thế ascii
    assert True


def test_skip_fetch_updates_asof_before_build_cache(tmp_path, monkeypatch):
    """--skip-fetch: api.yaml asof đổi TRƯỚC khi gọi build_api_cache (re-score ngày mới)."""
    as_of = "2026-10-15"
    api_yaml = tmp_path / "api.yaml"
    api_yaml.write_text("asof: 2026-10-08\n", encoding="utf-8")

    order: list[tuple[str, str]] = []

    def fake_run(cmd: list[str], *, retries: int = 3, sleep_fn=None) -> int:  # noqa: ARG001
        if "build_api_cache.py" in " ".join(cmd):
            text = api_yaml.read_text(encoding="utf-8")
            seen = ""
            for line in text.splitlines():
                if line.lstrip().startswith("asof:"):
                    seen = line.split(":", 1)[1].strip()
                    break
            order.append(("build_api_cache", seen))
            # Giả lập re-score M3–M7 với asof mới
            order.append(("rescore_m3_m7", seen))
        return 0

    monkeypatch.setattr(rd, "_run", fake_run)
    monkeypatch.setattr(rd, "LOCK_PATH", tmp_path / "_lock")
    monkeypatch.setattr(rd, "REFRESHED_PATH", tmp_path / "_refreshed.json")
    monkeypatch.setattr(rd, "API_YAML", api_yaml)

    rc = rd.main(
        [
            "--as-of",
            as_of,
            "--snapshots-dir",
            str(tmp_path),
            "--skip-fetch",
            "--allow-before-close",
            "--retries",
            "1",
        ],
        sleep_fn=lambda _s: None,
    )
    assert rc == 0
    assert order == [
        ("build_api_cache", as_of),
        ("rescore_m3_m7", as_of),
    ]
    assert f"asof: {as_of}" in api_yaml.read_text(encoding="utf-8")
    assert (tmp_path / "_refreshed.json").is_file()
