# Feature 010 — M7 score centering

## Problem

Công thức cũ `Score = clamp(Σ w·X − λ·R, 0, 100)` lệch cấu trúc: mean R ≈ 45 kéo điểm xuống ≈ λ·R (≈9 long_term / ≈13.5 swing) trong khi ngưỡng 75/60/45/30 giả định trung tính = 50. Hệ quả: phân bố label nghiêng Bán/Giảm, gần như không có "Mua mạnh".

Đo trên 235 mã có điểm (472 "Không xếp hạng" là đúng quality gate):

| Profile | mean | Bán / Giảm / Giữ / Mua / Mua mạnh |
|---------|------|-----------------------------------|
| long_term (cũ) | 41.4 | 43 / 92 / 87 / 13 / 0 |
| swing (cũ) | 33.3 | 101 / 76 / 49 / 6 / 0 |

## Decision

- **Đổi công thức** sang v2 centered:  
  `Score = clamp(50 + Σ w_k·(X_k − 50) − λ_R·(R − R_ref), 0, 100)` với `R_ref = risk_reference = 50`.  
  Khi Σw = 1: tương đương cũ + λ_R·R_ref → **thứ hạng giữ nguyên**, chỉ dịch mức tuyệt đối (label đổi theo ngưỡng cũ).
- **Không đổi** trọng số F/T/V/S, `λ_R`, ngưỡng rating, risk gate.
- **Không xử lý** trong 010: S phân tán thấp (std≈5, ~126/235 S=null).

## Expected after (cùng ngưỡng)

| Profile | mean | Bán / Giảm / Giữ / Mua / Mua mạnh |
|---------|------|-----------------------------------|
| long_term | ≈51.4 | 10 / 61 / 108 / 52 / 4 |
| swing | ≈48.3 | 15 / 89 / 76 / 49 / 6 |

Nếu đếm label lệch >3 mã so với kỳ vọng → điều tra, **không** chỉnh ngưỡng.

## Scope

- `config/scoring.yaml` (`risk_reference`), `m7_scoring/scoring.py`, consumers `contributions` / `module_polarity`, M8 validate độc lập, docs/tests/script phân bố.
- Không sửa M1–M6; không đổi schema trừ khi bắt buộc (schema `contributions` vẫn là object tự do).
