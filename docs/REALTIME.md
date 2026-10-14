# Realtime (feature 017a / 017a-fix2)

Giá phiên DNSE chỉ để **hiển thị** và **phân tích trong phiên (tạm tính)**. Điểm M2–M7 luôn dùng giá **đóng cửa EOD** từ snapshot — không bao giờ dùng tick.

## Kiến trúc

```
DNSE WS (tick.G1.json + security_definition, ≤200 mã/kết nối)
        │
        ▼
  RealtimeHub (thread nền, RAM cache)
        │
        ├── GET /api/quotes          (poll fallback)
        ├── GET /api/stream          (SSE, max 20 mã, heartbeat 15s)
        ├── GET /api/realtime/status
        └── GET /api/realtime/market (breadth / lists / heatmap / valuation tạm tính)
```

- Nhóm subscribe mặc định: `quality_tier` full + limited (~235–248), trần `realtime.max_symbols`.
- Mã đang xem (SSE) tăng refcount; về 0 và ngoài liquid → bỏ subscribe.
- Không key / lỗi kết nối / `realtime.enabled=false` → `SnapshotQuoteProvider`, `state=no_realtime`, API không crash.
- Không gọi accounts / orders / positions / trading-token / OTP. Không in key/secret/chữ ký.

## Giá tham chiếu cho % thay đổi (017a-fix2)

**Không** so giá live với snapshot lỗi thời. Ưu tiên:

| Thứ tự | Nguồn | `prev_close_source` |
|--------|--------|---------------------|
| a | `SecurityDefinition.basicPrice` (kênh `subscribe_sec_def`) — Trade/OHLC DNSE **không** có field prev close | `tick` |
| b | Đóng cửa snapshot **chỉ khi** `store.asof` == phiên giao dịch đã đóng gần nhất (`session_clock.sessions_behind == 0`) | `snapshot` |
| c | Không có tham chiếu hợp lệ → `change` / `change_pct` = `null`; UI hiện **—** và nhãn **chưa có giá tham chiếu** | `none` |

Sau `refresh_daily` (asof mới = phiên đóng gần nhất), nhánh (b) tự bật — không cần restart logic riêng nếu hub đọc `store.asof` động.

`GET /api/realtime/status` thêm: `prev_close_source`, `snapshot_asof`, `sessions_behind`.

## Cấu hình

`config/api.yaml` → khối `realtime`:

| Khóa | Ý nghĩa |
|------|---------|
| `enabled` | `false` tắt hẳn realtime |
| `max_symbols` | Trần subscribe |
| `max_per_connection` | 200 (SDK) |
| `price_scale` | Nhân `matchPrice` → VND: số cố định (khoá ngay) hoặc `"auto"` |
| `sse_max_per_ip` | Giới hạn kết nối SSE / IP |

### Bảo vệ đơn vị giá (017a-fix / 017a-fix2)

- **Auto** (`price_scale: auto`): với mỗi mã, `r = tick_raw / snapshot_close`; scale ứng viên = `10^(-round(log10(r)))` nếu `|log10(r) - round(log10(r))| ≤ 0.35` (~0.45×–2.2× quanh lũy thừa 10). **Không** dùng `prev_close` %. Khi ≥20 mã có phiếu và một scale ≥90% → khoá hệ thống; chỉ log scale đã chọn. Snapshot lệch vài phiên + giá dịch ±20% vẫn nhận đúng scale.
- **Drop**:
  - Có tham chiếu hợp lệ (`tick` \| `snapshot` tươi): `|scaled/prev_close - 1| > 0.30` → bỏ tick.
  - Chưa có ref: `|scaled/snapshot_close - 1| > 0.60` → bỏ tick (ngưỡng rộng hơn).
- **unit_mismatch**: >5% mã bị drop trong 1 phút → `state=unit_mismatch`; API/UI trả giá EOD kèm nhãn rõ.
- `GET /api/realtime/status` có: `price_scale_effective`, `dropped_ticks`, `symbols_subscribed`, `last_tick_age_seconds`, `prev_close_source`, `snapshot_asof`, `sessions_behind`.

### Phân tích trong phiên

Breadth / lists chỉ mã có `prev_close` hợp lệ; số mã bị loại nằm ở `breadth.excluded_no_ref`.

Tắt nhanh: `realtime.enabled: false` rồi restart API.

Biến môi trường (chỉ market data): `DNSE_API_KEY`, `DNSE_API_SECRET_KEY` (hoặc `DNSE_API_SECRET`).

Gói Python: `dnse-sdk-openapi>=2.0` (import `dnse`). **Không** cài PyPI package tên `dnse` 0.5.x — khác SDK.

## Đo thực tế (giờ giao dịch)

Chạy: `python scripts/_probe_realtime.py` trong **09:00–15:00 ICT T2–T6**.

| Chỉ số | Kết quả |
|--------|---------|
| Symbols subscribed | chưa đo |
| Tick latency | chưa đo |
| Tick rate (msg/s) | chưa đo |
| Đơn vị giá (VND / nghìn / snapshot close) | chưa đo |
| 429 / disconnects | chưa đo |
| Kênh `market_index` / `session` / `security_definition` | chưa đo |

(Lần ghi tài liệu này: ngoài giờ giao dịch — 2026-10-15.)

## Daily refresh

```bash
python scripts/refresh_daily.py --as-of YYYY-MM-DD
python scripts/refresh_daily.py --as-of YYYY-MM-DD --prefetch-debate 10
```

Windows Task Scheduler (16:00 T2–T6):

```powershell
.\scripts\schedule_refresh.ps1 -Register
```

Ghi `data/api_cache/_refreshed_at.json` → `/api/meta.refreshed_at`. File lock chống chạy trùng. Asof mới → `sessions_behind=0` → % thay đổi dùng đóng cửa snapshot (nhánh b).

## Nhãn UI

Mọi số live phải hiện **tạm tính**. `basis`: `"live"` | `"eod"` kèm `as_of_ts`.

Khi `prev_close_source=none`: `change_pct=null` → hiện **—**, nhãn **chưa có giá tham chiếu** (`ref_label` / `label` trên quote).
