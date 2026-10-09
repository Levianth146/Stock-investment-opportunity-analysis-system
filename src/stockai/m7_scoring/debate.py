"""M7 - Bull/Bear (N5). Chưa làm thật: trả về luận điểm giả.
Quy tắc: LLM chỉ được dùng số có trong upstream (m2..m6) và news đã có id; KHÔNG tự đặt giá mục tiêu."""


def run_debate(snapshot: dict, upstream: dict, cfg: dict) -> tuple[list[dict], list[dict]]:
    return ([{"text": "[stub] luận điểm tích cực chưa triển khai"}],
            [{"text": "[stub] luận điểm tiêu cực chưa triển khai"}])
