# M4 – DCF (FCFF hai giai đoạn)

Bật bằng `m4.enable_dcf: true` trong `config/valuation.yaml` (spec 008 từng để tắt nên tab DCF trên giao diện chỉ là khung rỗng).

- Mô hình: FCFF = CFO + chi phí lãi sau thuế − CAPEX; dự phóng `stage_years` năm, tăng trưởng giảm dần về `terminal_growth`; chiết khấu theo WACC (CAPM: `risk_free` + beta × `equity_risk_premium`).
- Không áp dụng: ngân hàng, chứng khoán, bảo hiểm (FCFF không có nghĩa). Trạng thái: `ok`, `not_applicable`, `insufficient`, `not_meaningful`.
- Cổng hợp lý: nếu giá trị DCF / giá thị trường ngoài [`plausible_ratio_min`, `plausible_ratio_max`] thì vẫn hiển thị nhưng `usable_for_target=false` (không đưa vào giá mục tiêu).
- Giá mục tiêu: 70% định giá tương đối (P/E, P/B) + 30% DCF khi dùng được (`blend_weight`). Điểm V không đổi.
- Kết quả nằm ở `modules.m4.dcf` (API `/api/analyze`), tab DCF của giao diện và trang Định giá của PDF.
- Mọi giả định nằm trong `config/valuation.yaml` (`m4.dcf`), hiển thị đầy đủ cùng kết quả.

# Dữ liệu hôm nay và cập nhật liên tục

- Realtime (giá, %, khối lượng, VN-Index, độ rộng): DNSE hub, SSE hoặc poll 8s/30s; cần key DNSE trong `.env` của từng máy.
- EOD: `scripts/refresh_daily.py` (16:00 ICT T2–T6, `schedule_refresh.ps1`) ghi snapshot ngày mới vào `snapshots_dir` của `config/api.yaml`; với `asof: auto` API tự quét lại thư mục mỗi 60 giây, không cần restart.
- `/api/meta` trả `expected_asof` và `eod_stale`; giao diện hiện cảnh báo khi EOD cũ hơn phiên gần nhất.
- PDF: mỗi lần xuất tạo file riêng, ngày xuất theo giờ ICT, kèm khối dữ liệu thời gian thực tại thời điểm xuất (nếu hub có dữ liệu).
