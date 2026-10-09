"""m3 - điểm T. Người làm chỉ sửa trong thư mục này (m3_technical/).

Giữ nguyên chữ ký run(snapshot, upstream, cfg) -> dict. Đầu ra phải qua validate(out, "module_out").
Chưa làm thật thì để status="stub"; khi xong đổi thành "ok" hoặc "partial" (thiếu dữ liệu, kèm flags).
"""
from stockai.contracts.helpers import stub_out


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    out = stub_out("m3")

    return out
