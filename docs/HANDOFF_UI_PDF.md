# Bàn giao: chỉnh giao diện web và PDF (nhánh 014-web)

## Chạy local
```
# 1) Dữ liệu (snapshots_ext KHÔNG nằm trong git → lấy từ Nam hoặc chạy M1)
python scripts/build_company_profiles.py                      # hồ sơ công ty + logo/intro
python scripts/fetch_dividends.py                             # lịch sử cổ tức (vnstock KBS/VCI)
python scripts/sync_shares_from_profile.py --asof 2026-10-14 --apply   # sửa số CP cũ
python scripts/build_m4_sector_stats.py --as-of 2026-10-14
# 2) API + web
python scripts/run_api.py                                     # http://127.0.0.1:8000
cd web && npm install && npm run build                        # API phục vụ web/dist
cd web && npm run dev                                         # dev server (proxy tới API)
```
Realtime cần `DNSE_API_KEY` / `DNSE_API_SECRET_KEY` trong `.env` (không commit). Không có khoá thì web chạy ở chế độ EOD.

## Web (React + Vite + TS strict) — `web/src`
| Việc | File |
|---|---|
| Trang chủ: heatmap, độ rộng, movers, VN-Index | `home/HomeMarketDashboard.tsx`, `SectorHeatmap.tsx`, `BreadthBars.tsx`, `MoversGrid.tsx`, `IndexStrip.tsx` |
| Luồng realtime (SSE, fallback polling) | `live/marketStream.ts`, `useMarketStream.ts`, `LiveContext.tsx` |
| Trang mã: Tổng quan, Cơ bản, Kỹ thuật, Cổ tức, Tin tức | `pages/TickerPage.tsx` (các tab trong cùng file) |
| Giới thiệu + logo công ty | `components/CompanyProfileCard.tsx` |
| Chỉ báo kỹ thuật + diễn giải | `technical/indicators.ts`, `narrative.ts`, `components/TechnicalSummary.tsx` |
| Phân tích cơ bản | `fundamental/analysis.ts`, `components/FundamentalSummary.tsx` |
| Cổ tức | `components/DividendHistory.tsx` |
| Màu, khoảng cách, theme | `styles/theme.css`, `theme.tsx`, `home/colorScale.ts` |

Quy tắc giao diện đang theo: không card/đổ bóng/gradient, số dùng `tabular-nums`, tôn trọng `prefers-reduced-motion`, chạy được ở 360px, có sáng/tối, thang màu diverging an toàn cho mù màu. Kiểm tra: `cd web && npx tsc --noEmit && npx vitest run`.

## PDF — `src/stockai/m9_report`
`data.py` gom dữ liệu · `layout.py` bố cục · `charts.py` biểu đồ · `text.py` văn bản · `theme.py` màu/phông · `fmt.py` định dạng số · `run.py` điểm vào. Cấu hình ở `config/report.yaml`. Test: `tests/test_m9_*.py` (cần `reportlab`, `jsonschema`, `requests`).
Lưu ý: PDF đã tạo trước 15/10 mang khuyến nghị cũ; tạo lại sau khi chạy lại pipeline.

## Điều cần biết về số liệu
- Điểm M2–M7 tính theo giá đóng cửa (EOD). Realtime chỉ ảnh hưởng giá, %, khối lượng, độ rộng, heatmap, VN-Index và các tỷ số suy ra từ giá (P/E, P/B, vốn hoá, chỉ báo kỹ thuật).
- Khuyến nghị có chốt chặn dữ liệu (`config/scoring.yaml`, khối `data_gate`): mã thanh khoản thấp tối đa "Mua"; giá mục tiêu cao hơn giá >100% thì tối đa "Nắm giữ". Điểm số không đổi, chỉ nhãn.
- Tin tức: nguồn VCI không có link bài viết. Nhãn tin ngoài M5 lấy theo từ khoá tiêu đề và không tính vào điểm.
- Điểm số minh hoạ, chưa hiệu chỉnh/kiểm định; không phải lời khuyên đầu tư.

## Việc còn mở
Lưu giá trong phiên qua lần khởi động lại API, trang Compare/Method, kiểm tra giá TRC ở M1, xác thực lại giá cả mã khi chạy M1 mới.
