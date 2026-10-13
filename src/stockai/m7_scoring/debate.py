"""Build traceable Bull/Bear statements from completed module evidence."""


def run_debate(snapshot: dict, upstream: dict, cfg: dict) -> tuple[list[dict], list[dict]]:
    bull, bear = [], []
    for module_name in ("m2", "m3", "m4", "m5", "m6"):
        module = upstream.get(module_name, {})
        score = module.get("score")
        evidence = module.get("evidence", [])
        if not isinstance(score, (int, float)):
            continue
        for item in evidence[:2]:
            if not isinstance(item, dict) or not item.get("text"):
                continue
            if module_name == "m5":
                text = item["text"]
                side = bull if text.startswith("Tin Tích cực:") else bear if text.startswith("Tin Tiêu cực:") else None
                claim = {"text": text}
            elif module_name == "m6":
                side = bull if score < 40 else bear if score >= 60 else None
                claim = {"text": f"{module_name.upper()} ({score:.0f}/100): {item['text']}"}
            else:
                side = bull if score >= 60 else bear if score < 40 else None
                claim = {"text": f"{module_name.upper()} ({score:.0f}/100): {item['text']}"}
            if side is None:
                continue
            if item.get("source_id"):
                claim["source_id"] = item["source_id"]
            if item.get("news_id"):
                claim["news_id"] = item["news_id"]
            side.append(claim)
    if not bull:
        bull.append({"text": "Chưa có chỉ báo tích cực đủ mạnh từ các module đã tính."})
    if not bear:
        bear.append({"text": "Chưa có chỉ báo rủi ro nổi bật từ các module đã tính."})
    return bull, bear
