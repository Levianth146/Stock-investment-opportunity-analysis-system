# Quy trình Git (đọc 3 phút)

## Nhánh
| Nhánh | Dùng để | Ai merge |
|---|---|---|
| `main` | Bản NỘP BÀI, luôn chạy được. Chỉ nhận merge từ `develop` ở các mốc | N1 |
| `develop` | Tích hợp. Mọi người merge vào đây | Tác giả tự merge sau khi CI xanh |
| `feat/<module>` | Mỗi người 1 nhánh theo module của mình | Chủ nhánh |

Nhánh theo người: `feat/core-pipeline`(N1) · `feat/m1-data`(N2) · `feat/m2-fundamental`, `feat/m4-valuation`(N3) · `feat/m3-technical`, `feat/m6-risk`(N4) · `feat/m5-sentiment`, `feat/m7-scoring`(N5) · `feat/m8-validate`, `feat/m9-report`(N6).
Hai người cùng module thì tách tiếp, ví dụ `feat/m1-data-news`.

## 4 luật để không conflict
1. **Mỗi người chỉ sửa thư mục module của mình** (xem `docs/OWNERSHIP.md`). Muốn đổi file của người khác -> nhắn owner, đừng tự sửa.
2. **File dùng chung chỉ N1 sửa:** `contracts/`, `pipeline.py`, `main.py`, `requirements.txt`, `fixtures/`. Cần thêm trường dữ liệu hoặc thư viện -> nhắn N1.
3. **PR nhỏ, merge mỗi 20-30 phút**, đừng giữ code cả tiếng rồi mới đẩy.
4. **Rebase trước khi push**, không merge ngược `develop` vào nhánh mình.

## Vòng làm việc mỗi lần
```bash
git checkout feat/m3-technical
git pull --rebase origin develop      # lấy code mới của người khác
# ... code, chạy: pytest -q ...
git add src/stockai/m3_technical tests/test_m3_*.py
git commit -m "m3: thêm RSI(14) + test"
git pull --rebase origin develop      # lần nữa trước khi đẩy
git push origin feat/m3-technical
# mở PR feat/m3-technical -> develop, CI xanh thì tự merge (Squash and merge)
```
Sau khi merge, **kéo `develop` về ngay** (`git pull --rebase origin develop`) để lần sau không lệch.

## Commit message
`<module>: <việc ngắn gọn>` - ví dụ `m1: fetch_prices có điều chỉnh giá`, `m7: bull/bear prompt`.

## Mốc tích hợp (N1 điều phối, `develop` -> `main`)
| Giờ | Mốc |
|---|---|
| 09:30 | Mọi người đã `git clone`, chạy được `python main.py DEMO --snapshot fixtures/snapshot_DEMO.json` |
| 10:15 | Mỗi module thay stub bằng code thật, đã merge vào `develop` ít nhất 1 lần |
| 10:45 | N1 chạy end-to-end trên snapshot thật (≥1 mã) |
| 11:15 | **Đóng băng**: chỉ sửa lỗi, N1 merge `develop` -> `main`, tạo tag `submit-v1`, xuất PDF mẫu |

## Cứu hộ nhanh
- Conflict khi rebase: `git status` xem file nào -> sửa -> `git add` -> `git rebase --continue`. Không rõ thì `git rebase --abort` và hỏi N1.
- Lỡ commit nhầm file của người khác: `git restore --source=origin/develop <file>` rồi commit lại.
- Lỡ commit `.env`/key: báo N1 NGAY, đổi key luôn (xóa commit chưa đủ).
