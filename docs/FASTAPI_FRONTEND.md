# Chạy backend FastAPI cùng frontend

Từ thư mục gốc dự án, dùng PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/run_api.py
```

Nếu đã có môi trường `.venv` và thư viện, chỉ cần lệnh cuối.

- Giao diện: http://127.0.0.1:8000/
- Swagger API: http://127.0.0.1:8000/docs
- Kiểm tra backend: http://127.0.0.1:8000/api/health

FastAPI phục vụ `frontend/dist` và API trên cùng cổng, nên không cần chạy npm cho bản build hiện có. Có thể đổi cổng, đường dẫn snapshot và frontend trong `config/api.yaml`. CORS cho phép `localhost:5173` và `127.0.0.1:5173` khi phát triển frontend riêng; lúc đó cần proxy `/api` sang backend hoặc cấu hình URL API trong source frontend.

## Phân tích cổ phiếu

```powershell
$body = @{ ticker = 'FPT'; profile = 'long_term' } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/analyze -Method Post -ContentType 'application/json' -Body $body
```

`POST /api/analyze` nhận:

```json
{"ticker": "FPT", "profile": "long_term"}
```

`profile`: `long_term` hoặc `swing`. `as_of` là tùy chọn; nếu truyền phải khớp ngày snapshot hiện có, nếu không API trả 409. Bỏ trường này để dùng snapshot mới nhất. Mã không tồn tại trả 404; body sai trả 422.

Kết quả gồm `ticker`, `as_of`, `score`, `scores`, `recommendation`, `current_price`, `target_price`, `upside`, `bull`, `bear`, `modules`, `quality_gate`, `validation`, `financial_reports`, `report_url`, `disclaimer`. `financial_reports` gồm `unit`, `is_bank`, `published_at_note` và hai danh sách `annual`, `quarterly` theo kỳ tăng dần. Mỗi kỳ có `period`, `published_at`, `published_at_estimated`, `source_id`, `items`; chỉ lấy báo cáo có ngày công bố không sau snapshot, giữ nguyên đơn vị nguồn và trả `null` cho số liệu không hợp lệ. Giá và giá mục tiêu dùng VND/cổ phiếu. Giá là giá đóng cửa snapshot, không phải giá trực tiếp. Trường thiếu dữ liệu trả `null`. Điểm và giá mục tiêu được tính bởi pipeline hiện có, không gọi LLM mới.

API khác: `GET /api/tickers`, `/api/rankings`, `/api/sectors`, `/api/tickers/{symbol}`, `/api/tickers/{symbol}/prices`, `/api/tickers/{symbol}/news`, `/api/quotes?symbols=FPT,HPG`, `POST /api/tickers/{symbol}/debate`, `GET /api/report/{symbol}.pdf?profile=long_term`.

## Dữ liệu và giới hạn giao diện hiện tại

Backend đọc `data/snapshots/**/*_YYYY-MM-DD.json`, gồm cả file ngay trong thư mục gốc và các thư mục con. `asof: auto` chọn ngày mới nhất trên toàn cây thư mục và chỉ lấy các mã thuộc ngày đó, không trộn ngày snapshot. Khi một mã cùng ngày có nhiều bản, ưu tiên file gần thư mục gốc được cấu hình nhất; cùng độ sâu thì chọn theo thứ tự đường dẫn. Thay đổi snapshot hoặc cấu hình cần khởi động lại backend. Cache pipeline nằm ở `data/api_cache`.

`GET /api/tickers` trả toàn bộ danh sách mã có snapshot tại ngày đang chọn: `total`, `items`, `asof`. Mỗi mục có mã, tên doanh nghiệp, sàn, ngành, ngày giá, giá đóng cửa (VND/cổ phiếu), biến động so phiên trước, khối lượng và tình trạng dữ liệu. Endpoint này chỉ đọc snapshot và cache metadata trong bộ nhớ, không chạy chấm điểm toàn thị trường, không lọc bỏ mã chưa đủ dữ liệu để xếp hạng và không giới hạn 10/500 mã. Giá tương lai so với ngày snapshot bị loại. Snapshot không đọc được vẫn có mục báo lỗi; mã đó không thể chọn từ bộ chọn.

Bộ tìm kiếm mã và Bảng giá snapshot dùng danh sách này qua `frontend/dist/assets/ticker-picker.js`, có tìm theo mã/tên/ngành không dấu, lọc sàn, giá và ngày snapshot thực tế. Dùng Ctrl+K hoặc Cmd+K để mở bộ tìm kiếm; Enter chọn kết quả đầu, Escape đóng. Mở một mã sẽ gọi `/api/analyze` riêng cho mã đó, chạy và cache các module nếu chưa có kết quả. Các tab dùng dữ liệu phân tích theo mã như mô tả bên dưới. Không thay tên doanh nghiệp thiếu bằng tên của FPT hoặc cổ phiếu demo trong lúc tải/lỗi.

Thư mục frontend được cung cấp chỉ có `dist` và `node_modules`, chưa có source React hoặc `package.json`. Phần kết nối được đặt trong `frontend/dist/api-client.js` (gồm component `FinancialReports`), `frontend/dist/assets/analysis-panels.js` (các tab phân tích còn lại và khối thông tin đầu trang) và đoạn gọi API/component của bundle hiện có. Khi khôi phục source React, cần chuyển các thay đổi này vào source vì build lại sẽ ghi đè `dist`.

Giao diện lấy giá đóng cửa, biến động giá, khối lượng, điểm nhân tố, khuyến nghị, giá mục tiêu, upside và Bull/Bear từ API khi có dữ liệu. Ba tab Kết quả kinh doanh, Bảng cân đối và Lưu chuyển tiền tệ dùng báo cáo năm/quý từ snapshot qua `/api/analyze`. Có thể chọn 5 kỳ, 8 kỳ hoặc toàn bộ lịch sử và đổi đơn vị tỷ đồng/triệu đồng/VND; EPS giữ VND/cổ phiếu. Mỗi bảng chia nhóm khoản mục, hiển thị ngày công bố và mã nguồn từng kỳ. Ngày công bố ước lượng được đánh dấu. Ngân hàng có nhóm thu nhập lãi thuần, chi phí hoạt động, dự phòng, NIM/CIR, cho vay và tiền gửi khách hàng riêng.

Các dòng có dấu * được tính từ khoản mục nguồn (ưu tiên giá trị trực tiếp nếu đã có), có công thức trong phần mở rộng bên dưới bảng: giá vốn, thuế ròng, lợi nhuận cổ đông không kiểm soát, tài sản/nợ dài hạn, tổng vay/vay ròng, vốn lưu động, biên lợi nhuận, hệ số thanh khoản, tổng dòng tiền ba hoạt động và CFO − |CAPEX|. Thiếu bất kỳ đầu vào nào thì không tính. Tổng dòng tiền ba hoạt động chưa gồm ảnh hưởng tỷ giá. NIM/CIR giữ theo nguồn và đổi từ tỷ lệ thập phân sang %, không tự quy đổi năm. Dữ liệu quý giữ nguyên cách ghi nhận của nguồn, không tự tách lũy kế.

Cột so cùng kỳ so kỳ mới nhất với năm trước hoặc cùng quý năm trước, kể cả khi kỳ đối chiếu nằm ngoài số cột đang hiển thị. Không tính tăng trưởng phần trăm khi kỳ gốc ≤ 0; tỷ lệ % so bằng điểm phần trăm, hệ số so bằng số lần. Khoản mục thiếu hiển thị dấu —, báo cáo thiếu hiển thị thông báo chưa có dữ liệu. Snapshot chỉ lưu các chỉ tiêu chuẩn hóa, chưa phải toàn bộ khoản mục/thuyết minh của BCTC gốc. Phần này không dùng số liệu demo, dự phóng hay xác nhận kiểm toán ghi cứng.

Ba tab kỹ thuật, định giá và rủi ro lấy các kết quả `modules.m3`, `modules.m4`, `modules.m6`, `target`, `validation`, `quality_gate` từ `/api/analyze` theo đúng mã cổ phiếu:

- Kỹ thuật hiển thị MA20/50/200, RSI, MACD, khối lượng, ATR và thành phần điểm. `price_history` chứa tối đa 252 phiên OHLCV không sau ngày snapshot, dùng cho biểu đồ đóng cửa 3/6/12 tháng. Đổi phạm vi biểu đồ không tính lại các chỉ báo tại phiên cuối.
- Định giá hiển thị P/E, P/B, dữ liệu EPS/giá trị sổ sách, thống kê tham chiếu và ba kịch bản giá mục tiêu với giả định do backend trả về. Không dùng các thanh mô phỏng DCF và giá kịch bản ghi cứng cũ. Nếu `target` công bố bị chặn bởi điều kiện chất lượng, không lấy lại target thô trong M4 để hiển thị.
- Rủi ro hiển thị biến động, Beta, drawdown, VaR/CVaR, số phiên và thành phần điểm; phần kiểm tra hiển thị trạng thái, số kiểm tra và từng vấn đề từ `validation`. Không hiển thị tên kiểm toán viên, checksum hoặc tình trạng kiểm toán mẫu. Kiểm tra dữ liệu hệ thống không phải xác nhận kiểm toán BCTC độc lập.

Các tab này chỉ nhận dữ liệu backend khớp mã đang chọn. Khi thiếu dữ liệu hoặc mất kết nối, hiển thị thông báo và dấu —. Phản hồi API của yêu cầu cũ bị bỏ qua khi người dùng chuyển mã liên tục. Một số thống kê tham chiếu hoặc trạng thái có thể giống nhau giữa các mã vì cùng nhóm so sánh; chúng vẫn lấy từ backend.

Tổng quan hiển thị giá đóng cửa, thay đổi so phiên trước, khối lượng, điểm tổng hợp, khuyến nghị, target và điểm F/T/V/S/R thực tế; biểu đồ dùng cùng lịch sử giá với tab kỹ thuật. Nút chi tiết từng nhân tố mở đúng tab. Khối P/E, P/B và ROE đầu trang cũng lấy từ module của mã hiện tại, không dùng trường dự phòng demo.

Tin tức & Sentiment dùng `modules.m5` và `news` trong `/api/analyze`. `news` là tối đa 6 tin tiêu biểu được trích dẫn trong căn cứ M5, kèm `id`, `ref`, `title`, `label` (`pos`/`neg` nếu được phân loại), `summary`, `source`, `url`, `published_at`. Không phải toàn bộ tin trong snapshot hoặc toàn bộ tin được đếm trong các chỉ số M5. Có thể lọc sắc thái và mở liên kết HTTP(S) gốc. Sentiment hiện là lexicon heuristic trên tiêu đề, không gọi LLM hay xác minh toàn văn; độ phủ không phải xác suất đã hiệu chỉnh. Ngày công bố là ngày gốc, không dùng thời gian tương đối ghi cứng.

Bull & Bear hiển thị nguyên các luận điểm `bull`/`bear` của kết quả phân tích, số luận điểm thực tế và tham chiếu chỉ số hoặc bài báo. `news_ref_map` sử dụng cùng ánh xạ n1/n2 từ M5 evidence như bộ tạo debate, không gán theo thứ tự tin trong snapshot. `debate_source: template` cho biết `/api/analyze` dùng luận điểm theo quy tắc; không gọi LLM mới. Không hiển thị tỷ lệ bình chọn, tác động EPS, ngưỡng cắt lỗ hay số công ty chứng khoán ghi cứng.

Danh mục, các modal công cụ và thao tác xuất PDF trong giao diện vẫn có phần demo. Bảng giá snapshot dùng danh sách mã và giá từ snapshot, không phải bảng điện trực tiếp. Báo cáo PDF thật có thể tải qua `report_url` hoặc Swagger.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api_frontend.py tests/test_api_011.py tests/test_api_011b.py -q
node --test --test-isolation=none tests/test_financial_reports.cjs
node --test --test-isolation=none tests/test_analysis_panels.cjs
node --test --test-isolation=none tests/test_ticker_picker.cjs
```
