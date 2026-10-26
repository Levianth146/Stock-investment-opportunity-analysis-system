# Triển khai StockAI trên Render Free

Dự án được đóng gói thành một Docker Web Service: FastAPI phục vụ API và
dashboard đã build trong `frontend/dist` trên cùng URL HTTPS. `render.yaml`
chọn nhánh `develop`, vùng Singapore và **plan: free**.

## Đưa lên Render

1. Đưa các file `Dockerfile`, `.dockerignore`, `render.yaml`, `deploy/` và tài
   liệu này lên nhánh `develop` của repository GitHub. Nếu không có quyền ghi,
   fork repository, push vào fork rồi đổi `repo` trong `render.yaml` sang fork.
2. Đăng nhập [Render](https://dashboard.render.com/) bằng GitHub và cấp quyền
   truy cập repository.
3. Chọn **New → Blueprint**, chọn repository và nhánh **develop**.
   Kiểm tra dịch vụ `stockai` có gói **Free**, rồi chọn **Deploy Blueprint**.
4. Chờ build/deploy thành công, mở URL `https://<tên-dịch-vụ>.onrender.com`
   được Render cấp. Tên/URL thực tế phụ thuộc tên còn trống.
5. Kiểm tra `/api/health` trả HTTP 200, sau khi warmup `status` là `ok`;
   mở `/`, danh sách cổ phiếu, phân tích một mã và xuất PDF.

Nếu dùng **New → Web Service** thay vì Blueprint: chọn repository, branch
`develop`, Language **Docker**, Dockerfile `./Dockerfile`, instance **Free**,
Health Check Path `/api/health`. Không dùng `scripts/run_api.py` trên cloud vì
script đó chỉ bind localhost; Docker tự bind `0.0.0.0` và biến `PORT` của Render.

## Dữ liệu và tính năng

- Không cần API key để xem và phân tích dữ liệu snapshot đã commit trong Git.
  Dữ liệu không tự cập nhật theo thời gian thực hay tự chạy pipeline mỗi ngày.
- Container dùng bản build đã commit ở `frontend/dist`. Khi sửa giao diện,
  build bằng `npm ci` và `npm run build` trong `frontend/`, commit bản build
  cùng source trước khi deploy.
- Realtime cần `DNSE_API_KEY` và `DNSE_API_SECRET_KEY` trong **Environment**
  của Render; thiếu khóa sẽ dùng snapshot. LLM tùy chọn cần `GEMINI_API_KEY`
  hoặc `ZAI_API_KEY`. Không cần nhập các khóa này cho bản demo miễn phí.
  Dịch vụ API bên ngoài có thể tính phí theo tài khoản của bạn.
- Không commit `.env`; Docker loại các file môi trường khỏi build context.
- `deploy/requirements.txt` chỉ chứa thư viện cho API, phân tích snapshot,
  realtime và renderer PDF hiện tại. Pipeline thu thập dữ liệu và Streamlit
  vẫn dùng `requirements.txt` ở thư mục gốc trên máy phát triển.
- `deploy/api.render.yaml` thay cấu hình API **trong image**; cấu hình local
  không đổi. Chạy một worker để tránh nhân đôi cache trong bộ nhớ.
- Build tính sẵn cache xếp hạng cho hai hồ sơ từ snapshot, giúp giảm công việc
  trên CPU nhỏ của gói Free. Bước này có thể kéo dài vài phút khi build.

## Giới hạn miễn phí

- Render Free có 512 MB RAM, tạm ngủ sau 15 phút không có truy cập; lượt mở
  tiếp theo cần chờ khởi động. Đây là phương án demo, cần đo RAM thực tế sau
  khi deploy, nhất là khi xuất PDF hoặc nhiều người phân tích đồng thời.
- Filesystem không bền vững: cache, dữ liệu intraday, báo cáo và bộ đếm giới
  hạn LLM ghi trong container có thể mất khi restart/redeploy. Snapshot đã
  commit trong Git được đưa lại vào image mỗi lần build.
- Giới hạn LLM lưu trên disk có thể reset khi restart. Chỉ thêm khóa LLM cho
  dịch vụ public khi bạn đã đặt hạn mức phù hợp tại nhà cung cấp.
- Danh mục theo dõi lưu localStorage trên trình duyệt; không đồng bộ tài khoản.
- Không cấu hình database, disk hoặc cron có trả phí trong Blueprint này.

Tham khảo: [Render Free](https://render.com/docs/free),
[Docker](https://render.com/docs/docker),
[Blueprint](https://render.com/docs/blueprint-spec).

## Kiểm tra Docker tại máy (cần Docker Desktop đang chạy)

```powershell
docker build -t stockai .
docker run --rm -p 10000:10000 stockai
```

Mở `http://localhost:10000/` và `http://localhost:10000/api/health`.
