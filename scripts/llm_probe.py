"""Probe tối giản từng model trong config/llm.yaml — chẩn đoán quota/circuit.

Gọi thật qua providers/gemini_rest.py và glm_rest.py.
KHÔNG in API key. Chỉ in: HTTP status, error class, latency, 1 dòng message đã lọc.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO / "src"))

from stockai.llm.generate import load_dotenv_keys, load_llm_cfg  # noqa: E402
from stockai.llm.providers import gemini_rest, glm_rest  # noqa: E402
from stockai.llm.quota_state import (  # noqa: E402
    default_quota_path,
    format_blocked_until,
    is_blocked,
    load_quota_state,
)

_PROMPT = 'Trả về đúng JSON object: {"ok": true, "n": 1}'


def _sanitize(msg: str, limit: int = 160) -> str:
    """Một dòng, bỏ chuỗi giống key."""
    s = (msg or "").replace("\n", " ").replace("\r", " ")
    low = s.lower()
    for bad in ("api_key", "apikey", "bearer ", "x-goog-api-key", "authorization:"):
        if bad in low:
            return "[sanitized: possible secret in body]"
    # Rút gọn JSON lỗi Gemini/GLM — giữ code/message/status
    if len(s) > limit:
        s = s[: limit - 1] + "…"
    return s


def _classify(exc: BaseException) -> str:
    if getattr(exc, "quota_exhausted", False) or "quota_exhausted" in str(exc):
        return "quota_exhausted"
    if getattr(exc, "empty_output", False) or "llm_empty_output" in str(exc):
        fr = getattr(exc, "finish_reason", None)
        if fr:
            return f"empty/finishReason={fr}"
        return "empty"
    msg = str(exc)
    if "rate_limited" in msg:
        return "rate_limit"
    if msg == "timeout" or "timeout" in msg.lower():
        return "timeout"
    if "parse_json" in msg or "parse_fail" in msg:
        return "parse_fail"
    code = getattr(exc, "status_code", None)
    if isinstance(code, int) and code >= 500:
        return "5xx"
    if isinstance(code, int) and code >= 400:
        return f"http_{code}"
    if "finishReason" in msg or "finish_reason" in msg.lower():
        return "finishReason"
    return (msg.split(":", 1)[0] or type(exc).__name__)[:40]


def _probe_gemini(model: str, *, timeout_sec: float, max_out: int, thinking: str) -> dict:
    t0 = time.perf_counter()
    status: int | None = None
    err_class = "ok"
    message = "ok"
    try:
        out = gemini_rest.generate_content_json(
            _PROMPT,
            model=model,
            temperature=0.0,
            timeout_sec=timeout_sec,
            schema_hint=None,
            max_output_tokens=max_out,
            thinking_level=thinking,
        )
        message = _sanitize(str(out)[:120])
        status = 200
    except gemini_rest.GeminiRestError as e:
        status = e.status_code
        err_class = _classify(e)
        body = getattr(e, "body", "") or str(e)
        message = _sanitize(body or str(e))
    except Exception as e:  # noqa: BLE001 — probe phải in mọi lỗi
        err_class = type(e).__name__
        message = _sanitize(str(e))
    ms = (time.perf_counter() - t0) * 1000.0
    return {
        "provider": "gemini",
        "model": model,
        "http_status": status,
        "error_class": err_class,
        "latency_ms": round(ms, 1),
        "message": message,
    }


def _probe_glm(model: str, *, timeout_sec: float, base_url: str) -> dict:
    t0 = time.perf_counter()
    status: int | None = None
    err_class = "ok"
    message = "ok"
    try:
        out = glm_rest.chat_completions_json(
            _PROMPT,
            model=model,
            base_url=base_url,
            temperature=0.0,
            timeout_sec=timeout_sec,
        )
        message = _sanitize(str(out)[:120])
        status = 200
    except glm_rest.GlmRestError as e:
        status = e.status_code
        err_class = _classify(e)
        body = getattr(e, "body", "") or str(e)
        message = _sanitize(body or str(e))
    except Exception as e:  # noqa: BLE001
        err_class = type(e).__name__
        message = _sanitize(str(e))
    ms = (time.perf_counter() - t0) * 1000.0
    return {
        "provider": "glm",
        "model": model,
        "http_status": status,
        "error_class": err_class,
        "latency_ms": round(ms, 1),
        "message": message,
    }


def main() -> int:
    load_dotenv_keys()
    cfg = load_llm_cfg()
    debate = cfg.get("debate") if isinstance(cfg.get("debate"), dict) else {}
    qpath = default_quota_path(debate.get("cache_dir") or "data/llm_cache")
    st = load_quota_state(qpath)

    print("=== llm_probe ===")
    print(f"quota_file: {qpath}")
    print(f"quota_entries: {len(st)}")
    for k, v in sorted(st.items()):
        blocked, until = is_blocked(*k.split("/", 1), path=qpath) if "/" in k else (False, None)
        until_s = format_blocked_until(until) if until else v
        print(f"  {k}: blocked={blocked} until={until_s}")
    print()

    import os

    print(
        "keys: GEMINI=%s ZAI=%s"
        % (
            "yes" if os.environ.get("GEMINI_API_KEY", "").strip() else "no",
            "yes" if os.environ.get("ZAI_API_KEY", "").strip() else "no",
        )
    )
    print()

    gemini = debate.get("gemini") if isinstance(debate.get("gemini"), dict) else {}
    glm = debate.get("glm") if isinstance(debate.get("glm"), dict) else {}
    models_g = list(gemini.get("models") or [gemini.get("model") or "gemini-3.8-flash"])
    models_z = list(glm.get("models") or [glm.get("model") or "glm-4.7-flash"])
    max_out = int(gemini.get("max_output_tokens") or debate.get("max_output_tokens") or 2048)
    thinking = str(gemini.get("thinking_level") or debate.get("thinking_level") or "lowest")
    g_to = float(gemini.get("timeout_sec") or debate.get("timeout_sec") or 90)
    z_to = float(glm.get("timeout_sec") or debate.get("timeout_sec") or 120)
    base = str(glm.get("base_url") or glm_rest.DEFAULT_BASE_URL)

    rows: list[dict] = []
    for m in models_g:
        print(f"--- probing gemini/{m} ---", flush=True)
        row = _probe_gemini(str(m), timeout_sec=g_to, max_out=max_out, thinking=thinking)
        rows.append(row)
        print(
            f"provider={row['provider']} model={row['model']} "
            f"http={row['http_status']} class={row['error_class']} "
            f"latency_ms={row['latency_ms']} msg={row['message']}",
            flush=True,
        )
    for m in models_z:
        print(f"--- probing glm/{m} ---", flush=True)
        row = _probe_glm(str(m), timeout_sec=z_to, base_url=base)
        rows.append(row)
        print(
            f"provider={row['provider']} model={row['model']} "
            f"http={row['http_status']} class={row['error_class']} "
            f"latency_ms={row['latency_ms']} msg={row['message']}",
            flush=True,
        )

    print()
    print("=== summary ===")
    for r in rows:
        print(
            f"{r['provider']}/{r['model']}: {r['error_class']} "
            f"(http={r['http_status']}, {r['latency_ms']}ms)"
        )
    ok_n = sum(1 for r in rows if r["error_class"] == "ok")
    print(f"ok={ok_n}/{len(rows)}")
    return 0 if ok_n else 1


if __name__ == "__main__":
    raise SystemExit(main())
