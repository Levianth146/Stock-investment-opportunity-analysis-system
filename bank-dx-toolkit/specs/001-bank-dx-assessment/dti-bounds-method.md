# Cận chuẩn hóa DTI cố định — phiên bản 2026-10-12

Cấu hình áp dụng: `config/dti_bounds.yaml`, phiên bản `fixed-reference-v1-2026-10-12`.
Khóa cận trước lần tính chính thức tiếp theo. Dự án đã có kết quả nháp trước ngày khóa;
đây không phải tiền đăng ký trước khi nhìn thấy dữ liệu.

## Lựa chọn phương pháp

Dùng biên tự nhiên, mốc đã có trong cấu hình và tham chiếu công bố của ngân hàng ngoài mẫu.
Không dùng MIN/MAX, phân vị hay thứ hạng của Agribank, MB, Techcombank, BIDV, Vietcombank
để chọn hoặc điều chỉnh cận. Các mốc ngoại mẫu là lựa chọn của nghiên cứu, không phải
chuẩn ngành bắt buộc, phân vị 90% của ngành hoặc bằng chứng về mức tối ưu.

DBS được chọn làm ngân hàng tham chiếu do báo cáo công khai cho phép khớp trực tiếp
định nghĩa phần mềm, CIR, thu nhập và nhân sự của code. Santander cung cấp chuỗi khách hàng số.
Dữ liệu tham chiếu kết thúc trước giai đoạn mẫu 2020–2025, nhưng việc chọn ngân hàng tham chiếu
không tạo ra tính đại diện thống kê. Nghiên cứu phải công bố hạn chế dùng một ngân hàng cho
nhiều cận và khác biệt giữa thị trường, cơ cấu kinh doanh, kế toán.

## Bộ cận áp dụng

| Chỉ số | L | U | Chiều tốt hơn | Loại cận |
|---|---:|---:|---|---|
| K-Q1: giao dịch số (%) | 0 | 90 | Tăng | Mốc tham chiếu kế thừa |
| K-Q2: khách hàng số (%) | 0 | 100 | Tăng | Biên tỷ lệ |
| K-Q3: đánh giá ứng dụng (sao) | 1 | 5 | Tăng | Biên thang đo |
| S-Q1: tăng tỷ lệ giao dịch số (điểm %/năm) | 0 | 18 | Tăng | Mục tiêu suy ra kế thừa |
| S-Q2: CAGR khách hàng số (%/năm) | 0 | 24.455463 | Tăng | Tham chiếu ngoại mẫu |
| T-Q1: nguyên giá phần mềm / tài sản bình quân (%) | 0 | 0.303798 | Tăng | Tham chiếu ngoại mẫu |
| T-Q2: phủ nền tảng (%) | 0 | 100 | Tăng | Biên checklist |
| O-Q1: thay đổi CIR (điểm %/năm) | -0.584529 | 0 | Giảm | Tham chiếu ngoại mẫu |
| O-Q2: CAGR thu nhập / nhân sự bình quân (%/năm) | 0 | 1.18425 | Tăng | Tham chiếu ngoại mẫu |
| C-Q1: nhân sự công nghệ (%) | 0 | 100 | Tăng | Biên tỷ lệ |
| C-Q2: đào tạo (giờ/người/năm) | 0 | 38.7 | Tăng | Tham chiếu ngoại mẫu |

Chi tiết nguồn và phép tính nằm ngay trong YAML. Giá trị suy ra làm tròn đến 6 chữ số
sau dấu phẩy. Số liệu đầu vào tham chiếu có tệp, trang và URL tại
`out/dti_bounds_review_2026-10-12/reference_inputs.csv`.

Nguồn chính:
- [Santander Annual Report 2018, trang in 6](https://www.santander.de/content/pdf/investor-relations/geschaeftsberichte/geschaeftsbericht-santander-2018-englisch.pdf);
  [bản nộp SEC](https://www.sec.gov/Archives/edgar/data/891478/000155837019002417/san-20181231x20f.htm).
- [DBS Annual Report 2019](https://www.dbs.com/iwov-resources/images/investors/annual-report/dbs-annual-report-2019.pdf).
- [DBS Annual Report 2015](https://www.dbs.com/annualreports/2015/pdfs/downloads/full-annual-report-2015.pdf).

Các trang DBS kiểm chứng bằng lớp văn bản PDF của nguồn chính thức; công cụ ảnh trang
không tải được. Santander đối chiếu bảng được lập chỉ mục của báo cáo ngân hàng với bản
SEC. Không tuyên bố đã đối chiếu trực quan tất cả trang PDF.

## Cách hiểu điểm

Chỉ số thuận: `z = 100*clip((x-L)/(U-L), 0, 1)`.
Chỉ số nghịch: `z = 100*clip((U-x)/(U-L), 0, 1)`; luôn đặt `L < U`.
Vì vậy CIR không cải thiện được 0, giảm bằng cận L hoặc nhiều hơn được 100.
Thiếu dữ liệu không được điền 0; khóa cận không làm xuất hiện dữ liệu còn thiếu.

S-Q1 và O-Q1 trong code là tốc độ bình quân từ năm đầu có dữ liệu trong khoảng
`--start-year` đến năm chấm, không nhất thiết chênh với năm liền trước.
CAGR cần ít nhất hai năm giữa hai mốc và cùng định nghĩa.
T-Q1 dùng nguyên giá phần mềm cuối kỳ, không dùng giá trị còn lại hoặc chi tiêu IT.
O-Q2 dùng tổng thu nhập hoạt động trên nhân sự bình quân đầu–cuối năm.
Code có thể dùng nhân sự/tài sản cuối kỳ khi thiếu đầu kỳ; cần giữ ghi chú về xấp xỉ này.

C-Q1 dùng 0–100 vì không đủ cơ sở chọn một tỷ lệ nhân sự công nghệ tối ưu.
U=100 chỉ là biên toán học, không phải mục tiêu nhân sự của ngân hàng.
Không dùng thông tin “gần 6.000 chuyên gia công nghệ” để suy ra cận 20% khi phạm vi
nhà thầu/nhân sự nội bộ chưa chắc khớp mẫu số. Lựa chọn biên tự nhiên khiến điểm chỉ số
này thường thấp, ảnh hưởng đến đóng góp thực tế của nó trong trụ cột C.

S-Q1 giữ U=18 theo mục tiêu giả định 90 điểm % trong thời hạn 5 năm lịch.
Khoảng cách từ mốc dữ liệu 2021 đến 2025 chỉ là 4 năm; không dùng phép suy ra này
như phát biểu “NHNN quy định tăng 18 điểm % mỗi năm”.
Ngân hàng đã gần trần giao dịch số có ít dư địa tăng; mô hình hiện tại chưa xử lý bão hòa.

## Hạn chế và kiểm chứng trước công bố

Cận tham chiếu thấp có thể kẹp nhiều quan sát tại 100, đặc biệt T-Q1, O-Q2 và C-Q2.
Điểm 100 nghĩa là đạt/vượt mốc đã chọn, không có nghĩa tối ưu hay dẫn đầu ngành.
Cần báo cáo tỷ lệ kẹp trần/sàn và số chỉ số còn thiếu, không tăng U chỉ để tách thứ hạng.
Khác biệt định nghĩa đào tạo, khách hàng số, nhân sự, phạm vi hợp nhất và vốn hóa phần mềm
phải được ghi trong dữ liệu đầu vào.

Các giả định “nhiều phần mềm/nhân sự công nghệ/giờ đào tạo là tốt hơn” chỉ là giả định đo lường.
Các chỉ số tài chính còn chịu lạm phát, cơ cấu kinh doanh, lãi suất và mua bán/sáp nhập.
Không diễn giải điểm này thành hiệu ứng nhân quả của chuyển đổi số.

Kiểm tra độ nhạy cận cần dùng kịch bản công bố riêng (chẳng hạn 0,8 và 1,2 lần độ rộng
của các cận ngoại mẫu), không thay cấu hình chính sau khi nhìn thấy thứ hạng.
`--weight-scenarios` chỉ kiểm tra trọng số DBI/DTI, chưa kiểm tra độ nhạy của L/U.
Nếu thứ hạng thay đổi đáng kể theo cận hợp lý, báo cáo thứ hạng có điều kiện thay vì
khẳng định một thứ tự tuyệt đối.

Khóa YAML chỉ là cố định tham số để tái lập tính toán. Nó không chứng nhận chất lượng
OCR, xác nhận dữ liệu DTI hay kiểm chứng quy tắc chấm DBI.
