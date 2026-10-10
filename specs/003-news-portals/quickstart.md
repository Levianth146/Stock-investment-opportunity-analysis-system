# Quickstart: News portals (003)

Offline validation after implementation (no network).

## Prerequisites

- Python 3.10+ / `PYTHONPATH=src`
- Spec clarifications locked in [spec.md](./spec.md)
- `news_portals_enabled` defaults **false** in `config/data_sources.yaml`
- Fixtures under `tests/fixtures/news_portals/` = **HTML thật từ spike** (không tự viết markup)
- Phạm vi cổng: **CafeF** + **VnEconomy** + **TinNhanhChungKhoan** (lọc `\bTICKER\b`; xem `research.md`)

## Run tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_m1_news_portals.py
python -m pytest -q
```

### Expected

- Fixture CafeF / TNCK → news contract-valid, URL gốc (không Google redirect).
- Undated (meta stripped) / look-ahead bị loại; date-only + ISO cùng ngày `as_of` được giữ.
- Google dup / vnstock `url="n/a"` → giữ bản cổng (title-only khi URL n/a).
- `news_portal_ok` theo bài **sau lọc, trước** cắt `max_news`.
- SC-005: đủ tin portal → không còn `quality_news_few` chỉ vì thiếu Google.
- Flag off / `universe_name=custom` / HOSE → không gọi portal.
- Một cổng lỗi → `news_portal_failed:<slug>`; cổng còn lại tiếp tục.
- Cache hit → không fetch lại URL đã cache.
- Full suite green.

## Manual smoke (optional, network)

Only when intentionally enabled:

```powershell
$env:PYTHONPATH = "src"
# news_portals_enabled: true và --universe VN30 hoặc VN100 (không dùng --tickers)
python scripts/fetch_universe.py --universe VN30 --as-of 2026-10-08 --limit 1
```

`--tickers` / `--tickers-file` đặt `universe_name=custom` → portal không chạy.

Do **not** use as CI gate.

## References

- Plan: [plan.md](./plan.md)
- Research: [research.md](./research.md)
- Data model: [data-model.md](./data-model.md)
- Flags / merge: [contracts/news-portals.md](./contracts/news-portals.md)
- Spike: [../../tests/fixtures/news_portals/SPIKE_NOTES.md](../../tests/fixtures/news_portals/SPIKE_NOTES.md)
