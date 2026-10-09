"""m4 - điểm V. Người làm chỉ sửa trong thư mục này (m4_valuation/).

Giữ nguyên chữ ký run(snapshot, upstream, cfg) -> dict. Đầu ra phải qua validate(out, "module_out").
Chưa làm thật thì để status="stub"; khi xong đổi thành "ok" hoặc "partial" (thiếu dữ liệu, kèm flags).
"""
from stockai.contracts.helpers import stub_out

def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    out = stub_out("m4")
    out["target"] = None  # M4 điền {"base","bull","bear","method","assumptions"} khi làm thật
    return out
