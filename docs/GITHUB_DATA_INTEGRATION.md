# Cập nhật GitHub và kết nối dữ liệu — 15/10/2026

Đã fetch `https://github.com/Levianth146/Stock-investment-opportunity-analysis-system.git` và merge `origin/develop` tại `7fab679` vào nhánh local `frontend`. Merge commit: `7002f6e`. Bản này cũng chứa `origin/main` tại thời điểm cập nhật. Đã xử lý xung đột cấu hình, route và kho kết quả; không còn file Git bị unmerged.

Các chỉnh sửa giao diện đã được lưu tạm và áp dụng lại sau khi tích hợp. Stash `backup frontend and data integration before origin-develop 2026-10-15` vẫn được giữ dự phòng; không cần apply lại. Bản sao file và patch: `data/web_preview/git-backups/20261015-152051/`. Thay đổi riêng ở `CompanyLogo.tsx` cũng được giữ lại. Toàn bộ phần tùy chỉnh giao diện và kết nối dữ liệu được commit và đưa lên nhánh `develop` theo yêu cầu tiếp theo của người dùng.

## Nguồn dữ liệu đang sử dụng

| Nguồn | Trạng thái |
|---|---|
| `data/snapshots` | 707 mã ở ngày 08/10/2026; tất cả `/api/analyze` đã trả HTTP 200 |
| `data/snapshots_ext` | Không có trên máy; hướng dẫn upstream xác nhận kho snapshot này không nằm trong Git |
| `data/company_profiles/profiles.json` | 254 hồ sơ từ repo mới; nối vào catalog, giới thiệu và chi tiết doanh nghiệp |
| `data/dividends/dividends.json` | 708 bản ghi, 689 bản ghi có sự kiện trong kho nguồn; giao diện chỉ hiện ngày GDKHQ không sau snapshot |
| `data/valuation_sector_stats.json` | Dựng lại offline cho ngày 08/10/2026, từ 235 mã full/limited, 19 nhóm kể cả thị trường |

Bảng thống kê định giá upstream ban đầu không chứa mã nào vì trỏ tới `snapshots_ext` không có trên máy. Bản upstream được lưu ở `data/web_preview/git-backups/20261015-152051/incoming_valuation_sector_stats.json` trước khi dựng lại:

```powershell
.\.venv\Scripts\python.exe scripts/build_m4_sector_stats.py --as-of 2026-10-08 --snapshots-dir data/snapshots
```

`config/api.yaml` giữ `snapshots_dir: data/snapshots`, `asof: auto`, `frontend_dir: frontend/dist`, `web_dist_dir: null`. Dashboard tùy chỉnh tiếp tục chạy ở cổng 8000. Code `web/src` mới vẫn có đủ trong repo nhưng không thay thế giao diện đang dùng. SDK DNSE trên máy đúng phiên bản 2.4.1 theo requirements mới.

## Kết nối và kiểm tra

- Giữ quy tắc chặn khuyến nghị mới của M7: dữ liệu hạn chế/giá mục tiêu bất thường không được nâng nhãn quá mức cấu hình.
- Hồ sơ mới đọc chung với cache overview cũ; trường thiếu dùng snapshot. Tên hợp lệ trong snapshot được giữ, tên đầy đủ có trong profile/catalog. `issue_share` của hồ sơ mới không ghi đè số cổ phiếu của snapshot lịch sử vì ngày hồ sơ có thể sau ngày giá.
- `/api/analyze` bổ sung `dividends`, giữ hợp đồng cũ. Xem cổ tức ở nút **Cổ tức** trong Phân tích cổ phiếu hoặc chi tiết doanh nghiệp. Đây là lịch sử từ kho nguồn, không phải lịch dự báo hoặc nguồn được chốt công bố đúng ngày quá khứ.
- Cache kết quả xét cấu hình pipeline và bảng thống kê định giá để tránh dùng kết quả cũ sau khi đổi nguồn. Kho cổ tức có cache theo mtime.
- `/news` giữ `items`, `other_items` của upstream và `articles` của dashboard; chỉ phân loại tiêu đề một lần, không nạp lexicon lại cho mỗi bài. Lần đo với FPT: khoảng 29 giây trước tối ưu, khoảng 0,6 giây sau tối ưu.
- Đã kiểm tra 707/707 mã qua HTTP, bộ kiểm thử backend/chấm điểm/hồ sơ/cổ tức/tin, 57 kiểm thử frontend và Chrome thực trên các trang, gồm watchlist và màn hình điện thoại.

## Giới hạn còn lại

Không có snapshot 14/10 trong Git nên không đổi nhãn giá 08/10 thành giá mới. Mã thiếu BCTC/tin vẫn hiển thị đúng trạng thái thiếu. Muốn chuyển ngày mới cần cung cấp snapshot tương ứng hoặc chạy thu thập M1 rồi dựng lại thống kê theo ngày đó.

Chưa có đủ `DNSE_API_KEY` / `DNSE_API_SECRET_KEY` trên máy; backend dùng nguồn snapshot. Không có khóa/trạng thái phù hợp thì không coi giá là realtime. Các trang tiếp tục ghi rõ nguồn snapshot.
