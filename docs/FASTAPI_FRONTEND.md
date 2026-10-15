# Chạy backend FastAPI cùng frontend

Triển khai bản demo miễn phí: xem [hướng dẫn Render](DEPLOY_RENDER.md).

Đã tích hợp code mới từ `origin/develop` ngày 15/10/2026, giữ dashboard tùy chỉnh. Xem [nguồn dữ liệu, bản sao dự phòng và giới hạn sau cập nhật](GITHUB_DATA_INTEGRATION.md). Giá hiện có đến 08/10/2026; snapshot 14/10 không nằm trong Git.

## Trang Danh mục theo dõi

Mục **Danh mục theo dõi** trên sidebar dùng chung `stockai-favorites` với nút sao ở Tổng quan/Cơ hội đầu tư, không dùng danh sách demo. Mã chưa đủ điều kiện xếp hạng vẫn được hiển thị từ catalog giá; mục tiêu/đánh giá chỉ có khi được công bố. Trang gồm:

- **01 · Danh sách theo dõi**: thêm mã từ toàn bộ catalog, bỏ sao, chọn mã, tìm kiếm/sắp xếp, lọc mã có số lượng hoặc chạm cảnh báo, xuất CSV toàn bộ kết quả hoặc mã đã chọn; chọn một dòng để xem khung doanh nghiệp và tin tiêu biểu tương ứng.
- **02 · Phân tích danh mục**: biểu đồ giá trị giữ cố định số lượng đã nhập, so sánh VN-Index cùng ngày gốc, đóng góp theo mã, phân bổ ngành, độ biến động quy đổi năm, Sharpe giả định, mức sụt giảm lớn nhất và bản đồ theo dõi. Có cảnh báo giá và lưu ý theo quy tắc dữ liệu; lịch sự kiện/tái cân bằng AI chưa có nguồn được kiểm chứng nên không tạo số minh họa.

Nhấn bút chì hoặc chuông để nhập số lượng nguyên dương, giá vốn VND/cổ phiếu, ngưỡng giá trên/dưới và ghi chú. Để trống số lượng nếu chỉ theo dõi. Dữ liệu lưu ở `stockai-watchlist-positions-v1` trong localStorage. Bỏ theo dõi không xóa số lượng/giá vốn đã nhập; thêm lại mã sẽ khôi phục thông tin đó. Đây là lưu trên thiết bị, chưa đồng bộ tài khoản và không gửi lệnh giao dịch.

Giá trị = số lượng × giá đóng cửa; lãi/lỗ = giá trị − số lượng × giá vốn. Tổng giá trị/lãi lỗ chỉ hiển thị khi có đủ các đầu vào liên quan; không đổi dữ liệu thiếu thành 0. Biến động theo phiên chỉ tính khi các mã nắm giữ có cùng ngày giá và đủ dữ liệu. Cảnh báo chỉ đối chiếu giá snapshot lúc tải/cập nhật trang, không gửi thông báo nền.

Biểu đồ lịch sử tải tối đa 252 phiên cho các mã đã nhập số lượng, tối đa 4 yêu cầu đồng thời, có hủy yêu cầu khi đổi danh mục/hồ sơ. Chỉ dùng ngày có giá của mọi mã nắm giữ và không sau snapshot; không tự bù ngày thiếu. Đây là mô phỏng số lượng hiện tại giữ cố định suốt khoảng, không phải lợi nhuận giao dịch thực tế/YTD; chưa tính phí, thuế, cổ tức hay biến động số lượng. Biến động năm dùng độ lệch chuẩn mẫu của lợi suất phiên × √252, cần ít nhất 20 lợi suất (21 phiên). Sharpe dùng lãi suất phi rủi ro giả định 0%, chưa tính khi chuỗi có độ lệch chuẩn 0. Đóng góp từng mã tính theo tỷ trọng ngày gốc, tổng bằng thay đổi của danh mục mô phỏng.

Kiểm tra dữ liệu bằng `node --test --test-isolation=none tests/test_watchlist_data.cjs`; kiểm tra thêm/sửa, cảnh báo, lưu sau reload, CSV, hai trang và màn hình điện thoại bằng `node tests/test_dashboard_browser.cjs`.

## Trang Cơ hội đầu tư

Trang dùng `/api/rankings?limit=2000&profile=...` để lọc toàn bộ mã đã xếp hạng, thay cho Top 50. Giá, thay đổi phiên, ngày giá và khối lượng được đối chiếu với catalog snapshot. Có các bộ lọc sàn (HSX hiển thị HOSE), ngành, vốn hóa, điểm tối thiểu, nhóm rủi ro, chênh lệch mục tiêu, khối lượng, khuyến nghị và chất lượng dữ liệu; tìm mã/tên/ngành không dấu. Bộ lọc cập nhật tự động. Chiến lược là điều kiện minh bạch F/T/V ≥ 65, không chạy mô hình AI mới.

Dashboard có thống kê các mã đang lọc, biểu đồ tròn ngành/khuyến nghị, histogram điểm, danh sách Top 3 mỗi ngành, bảng/thẻ, phân trang, xuất CSV theo bộ lọc hoặc mã đã chọn, theo dõi từng mã/nhiều mã và mở phân tích/PDF. Theo dõi lưu chung với danh sách hiện có trong trình duyệt. Chỉ mã đủ điều kiện xếp hạng được hiển thị, kể cả trong tab theo dõi.

Đường giá nhỏ là tối đa 20 phiên đóng cửa hợp lệ từ snapshot, không dựng hình từ điểm số. VN-Index có chuỗi 30 phiên thực tế, đổi xem 5/20/30 phiên và tooltip chuột/bàn phím; không bổ sung HNX/UPCoM giả. Chưa có lịch sử số lượng cơ hội nên hiển thị phân bố điểm hiện tại. Giá mục tiêu chỉ dùng kết quả M7 được công bố, không khôi phục mục tiêu M4 khi bị chặn. Chênh lệch giá mục tiêu không được mô tả thành lợi nhuận dự báo 12 tháng. Nhóm R là quy ước giao diện: dưới 33 thấp, 33 đến dưới 67 trung bình, từ 67 cao; không phải xác suất thua lỗ. Vốn hóa: dưới 2.000 tỷ; 2.000 đến dưới 10.000 tỷ; từ 10.000 tỷ VND. Thiếu dữ liệu không đổi thành 0 khi lọc hoặc tính trung bình.

Kiểm tra thêm bằng `node --test --test-isolation=none tests/test_opportunity_data.cjs`, pytest `tests/test_opportunity_rankings.py` và `node tests/test_dashboard_browser.cjs`.

## Trang Tin tức & Sentiment

Mục **Tin tức** gồm hai trang theo cùng bảng màu của dashboard:

- **Dòng tin tổng quan**: kho tin theo mã đang chọn, phân trang, bộ lọc 7/30/90 ngày hoặc toàn bộ kho, nguồn, chủ đề, từ khóa và sắc thái; mở chi tiết hoặc đọc bài nguồn. Có biểu đồ tỷ lệ sắc thái, chủ đề và số lần mã cổ phiếu xuất hiện trong tiêu đề.
- **Sentiment chuyên sâu**: tin gần nhất, biểu đồ sắc thái cùng giá đóng cửa, bản đồ mã được nhắc, thống kê nguồn, mật độ tin và tương quan Pearson khi đủ dữ liệu. Biểu đồ hỗ trợ rê chuột, chạm và phím mũi tên/Home/End.

`GET /api/tickers/{symbol}/news` giữ `items` cũ (tin tiêu biểu M5), bổ sung `articles` là kho tin snapshot đầy đủ, gộp tiêu đề trùng và bỏ ngày lỗi/tin sau snapshot. Phân loại từng tiêu đề dùng lại lexicon M5; không gọi LLM hay lấy tin từ mạng. Bộ lọc thời gian tính đến **ngày snapshot**, không lấy ngày hiện tại làm mốc. Nguồn chưa thu thập tin sẽ hiển thị trạng thái trống, không mượn tin FPT.

Chỉ số cân bằng trên giao diện là `50 + 50 × (số tin tích cực − số tin tiêu cực) / tổng số tin`, không phải điểm M5 vốn có trọng số thời gian và gộp sự kiện. Đếm theo nguồn/chủ đề/mã chỉ nằm trong kho của mã đang chọn, không đại diện toàn thị trường. Màu heatmap xét sắc thái theo mã đang phân tích, không chấm lại từng mã được nhắc. Tương quan dùng polarity trung bình ngày và giá đóng cửa cùng ngày, cần ít nhất 5 ngày chung và cả hai chuỗi có biến thiên; không suy diễn tác động lên giá. Độ tin cậy nguồn, dự báo tác động và khuyến nghị AI chưa có dữ liệu nên được ghi rõ thay vì tạo số minh họa.

Sau khi cập nhật mã backend cần khởi động lại API; frontend đã build được phục vụ tại cổng 8000. Kiểm tra bổ sung:

```powershell
node --test --test-isolation=none tests/test_news_data.cjs
.\.venv\Scripts\python.exe -m pytest tests/test_news_archive.py tests/test_api_frontend.py -q
node tests/test_dashboard_browser.cjs
```

## Khởi động

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

FastAPI phục vụ `frontend/dist` và API trên cùng cổng, nên không cần chạy npm cho bản build hiện có. Nếu `web/dist/index.html` tồn tại và `web_dist_dir` được cấu hình, backend ưu tiên bản `web`; để dùng dashboard StockAI mới, đặt `web_dist_dir: null` trong `config/api.yaml`. Cấu hình `frontend_dir: frontend/dist` giữ nguyên. Thay đổi cấu hình cần khởi động lại backend.

## Dashboard StockAI nền tối

Source giao diện mới nằm trong `frontend/src/App.tsx`, biểu đồ trong `frontend/src/components/DashboardCharts.tsx`, bảng màu trong `frontend/src/index.css`. Các biến màu dùng bảng màu navy/neon đã chọn. Giao diện có sidebar, bộ tìm kiếm toàn bộ doanh nghiệp (Ctrl+K), hồ sơ Long-term/Swing, điểm F/T/V/S/R, radar, luồng M1–M9, tin tiêu biểu và liên kết xuất PDF thật.

Biểu đồ hỗ trợ nến/đường, khối lượng, phạm vi 1/3/6 tháng/1 năm, MA20/MA50, RSI14, đường MACD(12,26), phóng to và tooltip ngày/giá/khối lượng. Có thể chạm hoặc dùng phím mũi tên khi focus biểu đồ. MA/RSI/MACD trên biểu đồ được tính trong trình duyệt từ tối đa 252 phiên API trả về, không cập nhật điểm pipeline theo phạm vi đang xem. MA cần đủ số phiên; MACD dùng EMA khởi tạo từ phiên đầu của chuỗi sẵn có. Ngày snapshot chỉ đọc vì API phân tích hiện chưa hỗ trợ chọn ngày lịch sử tùy ý.

Mục Cơ hội đầu tư lấy toàn bộ danh sách đã xếp hạng từ `/api/rankings` theo hồ sơ đang chọn để lọc tại giao diện. Lịch sử, mã theo dõi và chế độ hiển thị gọn lưu trên trình duyệt của thiết bị. Không có tài khoản/đăng ký Pro hoặc số liệu thị trường giả. Tin tức dùng sắc thái theo tiêu đề do backend trả về. Khuyến nghị, mục tiêu và điểm dùng đúng dữ liệu backend; thiếu dữ liệu hiển thị `—`.

Các mã chưa đủ điều kiện xếp hạng có thông báo tình trạng nguồn: số phiên giá, số BCTC, tin tức, lý do chặn xếp hạng và ngày giá thực tế. API trả thông tin này trong `data_availability`; catalog cũng có `quality_tier`, `quality_reasons`, `collection_incomplete`. Các thẻ có thể hiển thị điểm riêng từ mô-đun kỹ thuật/rủi ro vẫn tính được, ghi rõ “Điểm riêng · Chưa xếp hạng”; `score`, `scores` tổng hợp và giá mục tiêu vẫn giữ `null` khi quality gate chặn. Xem [báo cáo rà soát toàn bộ 707 mã](TICKER_DATA_AUDIT.md) cho ABR, AMC và các trường hợp thiếu dữ liệu nguồn.

Khung **Tổng quan doanh nghiệp** trên trang tổng quan nằm dưới thông tin cổ phiếu, có mô tả rút gọn, năm thành lập, ngành, sàn và ngày niêm yết. Nút “Xem chi tiết doanh nghiệp” mở toàn bộ mô tả cùng thông tin đang có. `company_profile` trong API lấy dữ liệu công ty trong snapshot và CSV `data/raw/<MÃ>/overview.csv` hoặc `data/raw_ext/<MÃ>/overview.csv`, chỉ chọn dòng đúng mã, không gọi mạng. Không lấy giá/khuyến nghị từ CSV hồ sơ để thay dữ liệu phân tích. Mô tả hồ sơ từ cache không được coi là dữ liệu lịch sử chốt tại ngày giá; nguồn được ghi trong hộp chi tiết. Năm thành lập chỉ hiện nếu có trường nguồn hoặc cụm “thành lập năm …” rõ ràng; thiếu thông tin sẽ ghi “Chưa có dữ liệu”. Hình tòa nhà trong khung là minh họa, không phải ảnh trụ sở. Component nằm trong `frontend/src/components/CompanyOverview.tsx`, phần đọc nguồn trong `src/stockai/api/company_profile.py`.

## Trang Phân tích cổ phiếu

`frontend/src/components/AnalysisPage.tsx` trình bày đồng thời hai khối cơ bản và kỹ thuật theo bố cục navy/neon. Đầu trang có vốn hóa tính từ số cổ phiếu trong snapshot × giá đóng cửa, P/E và EPS từ M4. Nhãn TTM chỉ dùng khi `eps_used.note` của backend xác định nguồn TTM; các thẻ cơ bản luôn ghi rõ năm BCTC đang sử dụng.

Khối cơ bản có 6 thẻ: doanh thu/thu nhập ngân hàng, LNST, ROE, ROA, biên gộp/NIM và tăng trưởng EPS; bảng rút gọn đổi giữa KQKD, cân đối và lưu chuyển tiền tệ; biểu đồ cột 5 năm gần nhất và diễn giải theo quy tắc. ROE lấy từ M2; ROA là LNST chia tài sản bình quân của hai năm liên tiếp; biên gộp là lợi nhuận gộp/doanh thu. Tăng trưởng chỉ tính khi có hai năm liên tiếp và cơ sở so sánh dương. Không cộng tùy ý các quý thành TTM do dữ liệu quý nguồn có thể chứa số lũy kế. Số tiền VND quy đổi sang tỷ; thiếu số liệu vẫn là `—`, không đổi thành 0. Nút **Tải dữ liệu** tải CSV UTF-8 có BOM chứa các BCTC năm được công bố trước snapshot, cùng mã/ngày/đơn vị. Nút **Xem báo cáo tài chính** mở bảng đầy đủ với lựa chọn năm/quý và đơn vị như trước.

Khối kỹ thuật dùng biểu đồ tương tác với các nút riêng SMA20/50/200, Bollinger (20 phiên, 2 độ lệch chuẩn quần thể), Volume và lựa chọn RSI/MACD. Biểu đồ dùng tối đa 252 phiên hiện có; chỉ báo bên phải lấy từ M3 trên toàn bộ lịch sử nguồn. Vùng đỉnh/đáy là high/low quan sát trong tối đa 20 phiên gần nhất, không phải mục tiêu dự báo hay mức hỗ trợ/kháng cự đã được xác nhận. Nhận định cơ bản/kỹ thuật là diễn giải theo quy tắc, không gọi LLM. Định giá, tin tức, rủi ro và Bull/Bear mở từ các nút phía trên; dữ liệu BCTC thiếu ở ABR/AMC vẫn được ghi rõ, không lấy số liệu FPT thay thế.

Các phép tính trình bày nằm trong `frontend/src/analysisData.ts`, CSS trang trong `frontend/src/analysis.css`. Kiểm tra helper bằng Node 24+: `node --test --test-isolation=none tests/test_analysis_data.cjs`. Kiểm thử Chrome còn kiểm tra số doanh thu đối chiếu API, chuyển bảng BCTC, tải CSV, bật SMA200/Bollinger, tắt Volume và bố cục desktop/390px.

### Trang 2/2: Định giá & Rủi ro

Hai nút 01/02 phía trên nội dung chuyển giữa cơ bản/kỹ thuật và định giá/rủi ro. Bấm thẻ Định giá hoặc Rủi ro từ Tổng quan cũng mở trang 2/2. Component ở `frontend/src/components/ValuationRiskPage.tsx`, helper trong `frontend/src/valuationRiskData.ts`, CSS trong `frontend/src/valuationRisk.css`.

Khối định giá có thẻ P/E, P/B, EPS, BVPS, EV/EBITDA năm và PEG theo EPS năm, tab P/E/P/B/DCF/nhóm tham chiếu, ba kịch bản và nút tải CSV. Giá mục tiêu cơ sở/bull/bear **chỉ lấy từ `data.target` do M7 công bố**, không khôi phục target thô của M4 khi quality gate chặn. Tab P/E/P/B chỉ đổi phần giải thích/tham chiếu, không tạo mục tiêu mới hoặc tính trung bình giả giữa ba phương pháp. Giá tham chiếu bằng EPS × median P/E hoặc BVPS × median P/B khi đủ điều kiện; chân P/B đã bị bỏ không được dùng để tạo tham chiếu. Khi có `m4_sector_fallback`, nhãn đổi thành tham chiếu **thị trường**. Nhóm `/api/tickers/{symbol}/peers` được gọi là nhóm tham chiếu từ snapshot, vì mẫu nhỏ có thể chứa mã khác ngành. Tab DCF hiện báo chưa có kết quả thay vì tự tạo mô hình dòng tiền chưa được backend trả về. Nút phương pháp mở giả định M4 hiện có.

EV = vốn hóa theo giá snapshot + tổng nợ vay − tiền; EV/EBITDA dùng EBITDA năm gần nhất (hoặc EBIT + khấu hao nếu thiếu EBITDA nguồn), chỉ tính với đơn vị tiền biết được và các đầu vào đầy đủ, không áp dụng ngân hàng. PEG = P/E / mức tăng EPS năm tính bằng %, chỉ có khi P/E và tăng trưởng EPS dương. Đây là hai tỷ số trình bày bổ sung, không đi vào giá mục tiêu pipeline và không gắn nhãn TTM.

Khối rủi ro hiển thị biến động quy đổi năm của mã/VN-Index, beta, MDD, VaR95, GTGD ước tính bình quân tối đa 20 phiên và điểm M6. GTGD ước tính = close × volume, không phải giá trị khớp lệnh thực tế. MDD/VaR nguồn là độ lớn mức giảm/lỗ, giao diện đặt dấu âm khi trình bày. Radar và thanh điểm dùng đúng 5 subscore M6: volatility, drawdown, VaR, CVaR, beta; không tự gán điểm rủi ro tin tức/cơ bản/thanh khoản hoặc đường trung bình ngành chưa có nguồn. Điểm R cao nghĩa là rủi ro đo được cao; không tự đặt nhãn thấp/trung bình/cao với ngưỡng chưa công bố.

Biểu đồ so sánh gọi `/api/tickers/{symbol}/prices?range=1y&include_index=true`, khớp các ngày có close dương của cả mã và chỉ số, cùng gốc 0% tại ngày chung đầu tiên; có lựa chọn 3/6/12 tháng và hover/chạm/phím mũi tên. Đây là thay đổi giá, không phải đường độ biến động. Request bổ sung hủy khi đổi mã/hồ sơ, kiểm tra `symbol`/`asof`, không trộn response cũ; lỗi có nút thử lại và không chặn các chỉ số M4/M6 có sẵn. Các nhận định là diễn giải theo quy tắc; VaR/CVaR không phải giới hạn lỗ tối đa.

Kiểm tra bằng Node 24+: `node --test --test-isolation=none tests/test_valuation_risk_data.cjs`. Kiểm thử Chrome bao gồm phân trang, target đối chiếu API, DCF trống, nhóm tham chiếu, biểu đồ VN-Index, điểm M6, tải CSV, mở phương pháp, màn hình 390px và các mã không xếp hạng ABR/AMC.

Build từ PowerShell:

```powershell
cd frontend
npm.cmd ci
npm.cmd run lint
npm.cmd run build
```

Vite tự sao chép các adapter từ `frontend/public` vào `frontend/dist`. Các lần build giữ lại asset cũ để tương thích phần kiểm thử/bản build được cung cấp trước đây. Khi sửa báo cáo tài chính hoặc các panel chi tiết, sửa bản trong `frontend/public/api-client.js` hoặc `frontend/public/assets` rồi build lại. `npm.cmd run dev` chạy ở cổng 3000, proxy `/api` sang FastAPI ở cổng 8000. Giao diện luôn gọi API cùng origin.

Sau khi build, tải lại trang FastAPI. Các bundle chính có tên hash; adapter dùng query phiên bản trong `frontend/index.html` (tăng phiên bản khi cập nhật adapter).

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

Bộ tìm kiếm trong dashboard dùng toàn bộ danh sách này, có tìm theo mã/tên/ngành không dấu, hiển thị sàn, giá và ngày snapshot thực tế. Dùng Ctrl+K hoặc Cmd+K để mở bộ tìm kiếm; Enter chọn kết quả đầu, Escape đóng. Danh sách hiển thị tối đa 100 kết quả cùng lúc; nhập thêm từ khóa để tìm mọi mã trong catalog. Mở một mã sẽ gọi `/api/analyze` riêng cho mã đó, chạy và cache các module nếu chưa có kết quả. Không thay tên doanh nghiệp thiếu bằng tên của FPT hoặc cổ phiếu demo trong lúc tải/lỗi.

Dashboard mới gọi `/api/analyze` trong source với hủy request khi đổi mã/hồ sơ, không dùng dữ liệu demo khi tải lỗi. Các panel báo cáo tài chính và phân tích chi tiết tiếp tục sử dụng adapter có source trong `frontend/public`; bản `dist` được tạo bằng Vite. Các component demo cũ trong `frontend/src/components` vẫn được giữ để tham khảo, không nằm trong luồng dashboard mới.

Giao diện lấy giá đóng cửa, biến động giá, khối lượng, điểm nhân tố, khuyến nghị, giá mục tiêu, upside và Bull/Bear từ API khi có dữ liệu. Ba tab Kết quả kinh doanh, Bảng cân đối và Lưu chuyển tiền tệ dùng báo cáo năm/quý từ snapshot qua `/api/analyze`. Có thể chọn 5 kỳ, 8 kỳ hoặc toàn bộ lịch sử và đổi đơn vị tỷ đồng/triệu đồng/VND; EPS giữ VND/cổ phiếu. Mỗi bảng chia nhóm khoản mục, hiển thị ngày công bố và mã nguồn từng kỳ. Ngày công bố ước lượng được đánh dấu. Ngân hàng có nhóm thu nhập lãi thuần, chi phí hoạt động, dự phòng, NIM/CIR, cho vay và tiền gửi khách hàng riêng.

Các dòng có dấu * được tính từ khoản mục nguồn (ưu tiên giá trị trực tiếp nếu đã có), có công thức trong phần mở rộng bên dưới bảng: giá vốn, thuế ròng, lợi nhuận cổ đông không kiểm soát, tài sản/nợ dài hạn, tổng vay/vay ròng, vốn lưu động, biên lợi nhuận, hệ số thanh khoản, tổng dòng tiền ba hoạt động và CFO − |CAPEX|. Thiếu bất kỳ đầu vào nào thì không tính. Tổng dòng tiền ba hoạt động chưa gồm ảnh hưởng tỷ giá. NIM/CIR giữ theo nguồn và đổi từ tỷ lệ thập phân sang %, không tự quy đổi năm. Dữ liệu quý giữ nguyên cách ghi nhận của nguồn, không tự tách lũy kế.

Cột so cùng kỳ so kỳ mới nhất với năm trước hoặc cùng quý năm trước, kể cả khi kỳ đối chiếu nằm ngoài số cột đang hiển thị. Không tính tăng trưởng phần trăm khi kỳ gốc ≤ 0; tỷ lệ % so bằng điểm phần trăm, hệ số so bằng số lần. Khoản mục thiếu hiển thị dấu —, báo cáo thiếu hiển thị thông báo chưa có dữ liệu. Snapshot chỉ lưu các chỉ tiêu chuẩn hóa, chưa phải toàn bộ khoản mục/thuyết minh của BCTC gốc. Phần này không dùng số liệu demo, dự phóng hay xác nhận kiểm toán ghi cứng.

Ba tab kỹ thuật, định giá và rủi ro lấy các kết quả `modules.m3`, `modules.m4`, `modules.m6`, `target`, `validation`, `quality_gate` từ `/api/analyze` theo đúng mã cổ phiếu:

- Kỹ thuật hiển thị MA20/50/200, RSI, MACD, khối lượng, ATR và thành phần điểm. `price_history` chứa tối đa 252 phiên OHLCV không sau ngày snapshot, dùng cho biểu đồ đóng cửa 3/6/12 tháng. Đổi phạm vi biểu đồ không tính lại các chỉ báo tại phiên cuối.
- Định giá hiển thị P/E, P/B, dữ liệu EPS/giá trị sổ sách, thống kê tham chiếu và ba kịch bản giá mục tiêu với giả định do backend trả về. Không dùng các thanh mô phỏng DCF và giá kịch bản ghi cứng cũ. Nếu `target` công bố bị chặn bởi điều kiện chất lượng, không lấy lại target thô trong M4 để hiển thị.
- Rủi ro hiển thị biến động, Beta, drawdown, VaR/CVaR, số phiên và thành phần điểm; phần kiểm tra hiển thị trạng thái, số kiểm tra và từng vấn đề từ `validation`. Không hiển thị tên kiểm toán viên, checksum hoặc tình trạng kiểm toán mẫu. Kiểm tra dữ liệu hệ thống không phải xác nhận kiểm toán BCTC độc lập.

Các tab này chỉ nhận dữ liệu backend khớp mã đang chọn. Khi thiếu dữ liệu hoặc mất kết nối, hiển thị thông báo và dấu —. Phản hồi API của yêu cầu cũ bị bỏ qua khi người dùng chuyển mã liên tục. Một số thống kê tham chiếu hoặc trạng thái có thể giống nhau giữa các mã vì cùng nhóm so sánh; chúng vẫn lấy từ backend.

Tổng quan hiển thị giá đóng cửa, thay đổi so phiên trước, khối lượng, điểm tổng hợp, khuyến nghị, target và điểm F/T/V/S/R thực tế; biểu đồ dùng cùng lịch sử giá với tab kỹ thuật. Bấm thẻ từng nhân tố để mở đúng tab. P/E, P/B, ROE và các chỉ số chi tiết nằm trong các tab phân tích tương ứng, lấy từ module của mã hiện tại.

Tin tức & Sentiment dùng `modules.m5` và `news` trong `/api/analyze`. `news` là tối đa 6 tin tiêu biểu được trích dẫn trong căn cứ M5, kèm `id`, `ref`, `title`, `label` (`pos`/`neg` nếu được phân loại), `summary`, `source`, `url`, `published_at`. Không phải toàn bộ tin trong snapshot hoặc toàn bộ tin được đếm trong các chỉ số M5. Có thể lọc sắc thái và mở liên kết HTTP(S) gốc. Sentiment hiện là lexicon heuristic trên tiêu đề, không gọi LLM hay xác minh toàn văn; độ phủ không phải xác suất đã hiệu chỉnh. Ngày công bố là ngày gốc, không dùng thời gian tương đối ghi cứng.

Bull & Bear hiển thị nguyên các luận điểm `bull`/`bear` của kết quả phân tích, số luận điểm thực tế và tham chiếu chỉ số hoặc bài báo. `news_ref_map` sử dụng cùng ánh xạ n1/n2 từ M5 evidence như bộ tạo debate, không gán theo thứ tự tin trong snapshot. `debate_source: template` cho biết `/api/analyze` dùng luận điểm theo quy tắc; không gọi LLM mới. Không hiển thị tỷ lệ bình chọn, tác động EPS, ngưỡng cắt lỗ hay số công ty chứng khoán ghi cứng.

Dashboard mới dùng danh sách mã và giá từ snapshot, không phải bảng điện trực tiếp. Xuất PDF mở `report_url` do backend trả về. Các phần demo cũ không được gắn vào dashboard mới.

## Kiểm tra

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_api_frontend.py tests/test_api_011.py tests/test_api_011b.py -q
node --test --test-isolation=none tests/test_financial_reports.cjs
node --test --test-isolation=none tests/test_analysis_panels.cjs
node --test --test-isolation=none tests/test_ticker_picker.cjs
node tests/test_dashboard_browser.cjs
```

Kiểm thử trình duyệt cần API đang chạy và Chrome. Mặc định dùng `http://127.0.0.1:8000` và Chrome trong `C:/Program Files/Google/Chrome/Application/chrome.exe`; có thể đặt `BASE_URL`, `CHROME_PATH`. Script mở Chrome headless với hồ sơ kiểm thử riêng, kiểm tra tooltip bằng chuột, đổi mã/hồ sơ đối chiếu backend, BCTC, URL PDF, xếp hạng, lịch sử và màn hình 390px; ảnh kiểm thử lưu dưới `data/web_preview/dashboard-browser` (không commit).
