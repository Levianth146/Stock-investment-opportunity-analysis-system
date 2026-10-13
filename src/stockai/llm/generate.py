"""Façade ``generate_json`` — Gemini/GLM qua requests, cache, failover."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable

import yaml

from stockai.llm.cache import cache_key, cache_path, read_cache, write_cache
from stockai.llm.payload import payload_hash
from stockai.llm.providers import gemini_rest, glm_rest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CFG = _REPO_ROOT / "config" / "llm.yaml"

_rpm_lock = threading.Lock()
_rpm_times: list[float] = []

# Retry cùng model: rate-limit 429 + 5xx; backoff 2s, 4s, 8s (tối đa 3 lần)
# Quota exhausted → KHÔNG backoff, failover ngay
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_BACKOFF_SEC = (2.0, 4.0, 8.0)

# Circuit breaker: provider:model → state
_circuit_lock = threading.Lock()
_circuit: dict[str, dict[str, Any]] = {}
# Thống kê lý do lỗi theo provider (batch in bảng cuối)
_error_reasons: dict[str, dict[str, int]] = {}


def load_dotenv_keys(env_path: str | Path | None = None) -> None:
    """Nạp GEMINI_API_KEY / ZAI_API_KEY từ .env nếu chưa có trong environ.

    Không in giá trị khóa. Chỉ parse dòng KEY=VALUE đơn giản.
    """
    path = Path(env_path) if env_path else _REPO_ROOT / ".env"
    if not path.is_file():
        return
    wanted = {"GEMINI_API_KEY", "ZAI_API_KEY"}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for line in lines:
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        name, _, val = s.partition("=")
        name = name.strip()
        if name not in wanted:
            continue
        if os.environ.get(name):
            continue
        val = val.strip().strip('"').strip("'")
        if val:
            os.environ[name] = val


def load_llm_cfg(path: str | Path | None = None) -> dict:
    """Đọc config/llm.yaml."""
    p = Path(path) if path else _DEFAULT_CFG
    if not p.is_file():
        return {"debate": {}}
    data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {"debate": {}}


def _debate_section(cfg: dict) -> dict:
    d = cfg.get("debate") if isinstance(cfg, dict) else None
    return d if isinstance(d, dict) else {}


def reset_circuit_state() -> None:
    """Xóa circuit breaker + bảng lỗi (dùng trong test / đầu batch)."""
    with _circuit_lock:
        _circuit.clear()
        _error_reasons.clear()


def error_reason_table() -> dict[str, dict[str, int]]:
    """Bản sao bảng đếm lý do lỗi theo provider."""
    with _circuit_lock:
        return {p: dict(reasons) for p, reasons in _error_reasons.items()}


def format_error_reason_table() -> str:
    """Chuỗi in cuối batch: provider → reason → count."""
    table = error_reason_table()
    if not table:
        return "ERROR_REASONS (none)"
    lines = ["ERROR_REASONS by provider:"]
    for prov in sorted(table):
        parts = [f"{r}={c}" for r, c in sorted(table[prov].items(), key=lambda x: (-x[1], x[0]))]
        lines.append(f"  {prov}: " + ", ".join(parts))
    return "\n".join(lines)


def _cb_key(provider: str, model: str) -> str:
    return f"{provider}:{model}"


def _cb_cfg(debate: dict) -> tuple[int, float]:
    cb = debate.get("circuit_breaker") if isinstance(debate.get("circuit_breaker"), dict) else {}
    thr = int(cb.get("consecutive_failures") or 3)
    mins = float(cb.get("cooldown_minutes") or 15)
    return max(1, thr), max(0.0, mins) * 60.0


def _circuit_is_open(provider: str, model: str, debate: dict) -> bool:
    key = _cb_key(provider, model)
    with _circuit_lock:
        st = _circuit.get(key)
        if not st:
            return False
        until = float(st.get("open_until") or 0.0)
        if until <= 0:
            return False
        if time.monotonic() >= until:
            # hết cooldown — cho thử lại, giữ fails=0
            st["open_until"] = 0.0
            st["fails"] = 0
            return False
        return True


def _circuit_record_success(provider: str, model: str) -> None:
    key = _cb_key(provider, model)
    with _circuit_lock:
        _circuit[key] = {"fails": 0, "open_until": 0.0, "last_reason": ""}


def _circuit_record_failure(provider: str, model: str, reason: str, debate: dict) -> bool:
    """Ghi thất bại; trả True nếu vừa mở circuit."""
    thr, cooldown = _cb_cfg(debate)
    key = _cb_key(provider, model)
    opened = False
    with _circuit_lock:
        st = _circuit.setdefault(key, {"fails": 0, "open_until": 0.0, "last_reason": ""})
        st["fails"] = int(st.get("fails") or 0) + 1
        st["last_reason"] = reason[:120]
        if st["fails"] >= thr and cooldown > 0:
            st["open_until"] = time.monotonic() + cooldown
            opened = True
        reasons = _error_reasons.setdefault(provider, {})
        reasons[reason] = int(reasons.get(reason) or 0) + 1
    return opened


def _wait_rpm(limit: int) -> None:
    if limit <= 0:
        return
    with _rpm_lock:
        now = time.monotonic()
        while _rpm_times and now - _rpm_times[0] > 60.0:
            _rpm_times.pop(0)
        if len(_rpm_times) >= limit:
            sleep_for = 60.0 - (now - _rpm_times[0]) + 0.05
            if sleep_for > 0:
                time.sleep(sleep_for)
            now = time.monotonic()
            while _rpm_times and now - _rpm_times[0] > 60.0:
                _rpm_times.pop(0)
        _rpm_times.append(time.monotonic())


def _has_key(provider: str) -> bool:
    if provider == "gemini":
        return bool(os.environ.get("GEMINI_API_KEY", "").strip())
    if provider == "glm":
        return bool(os.environ.get("ZAI_API_KEY", "").strip())
    return False


def _models_for(provider: str, debate: dict) -> list[str]:
    """Danh sách model theo thứ tự failover trong config."""
    if provider == "gemini":
        g = debate.get("gemini") or {}
        models = g.get("models")
        if isinstance(models, list) and models:
            return [str(m) for m in models if m]
        return [str(g.get("model") or gemini_rest.DEFAULT_MODEL)]
    if provider == "glm":
        g = debate.get("glm") or {}
        models = g.get("models")
        if isinstance(models, list) and models:
            return [str(m) for m in models if m]
        return [str(g.get("model") or glm_rest.DEFAULT_MODEL)]
    return []


def estimate_cost_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    debate: dict | None = None,
) -> float:
    """Ước tính USD từ bảng pricing (USD/1M token)."""
    debate = debate or {}
    pricing = debate.get("pricing") or {}
    row = pricing.get(model) or {}
    pin = float(row.get("input") or 0.0)
    pout = float(row.get("output") or 0.0)
    return (input_tokens * pin + output_tokens * pout) / 1_000_000.0


def _call_provider_model(
    provider: str,
    prompt: str,
    *,
    model: str,
    debate: dict,
    temperature: float,
    timeout_sec: float,
    schema_hint: dict | None,
) -> tuple[dict, dict[str, int]]:
    """Gọi một model; trả (parsed_without_usage, usage)."""
    if provider == "gemini":
        out = gemini_rest.generate_content_json(
            prompt,
            model=model,
            temperature=temperature,
            timeout_sec=timeout_sec,
            schema_hint=schema_hint,
        )
    elif provider == "glm":
        g = debate.get("glm") or {}
        base = g.get("base_url") or glm_rest.DEFAULT_BASE_URL
        out = glm_rest.chat_completions_json(
            prompt,
            model=model,
            base_url=base,
            temperature=temperature,
            timeout_sec=timeout_sec,
        )
    else:
        raise RuntimeError(f"unknown_provider:{provider}")
    usage = {}
    if isinstance(out, dict) and isinstance(out.get("_usage"), dict):
        usage = dict(out.pop("_usage"))
    return out, usage


def _is_quota_exhausted(exc: Exception) -> bool:
    if getattr(exc, "quota_exhausted", False):
        return True
    msg = str(exc).lower()
    return "quota_exhausted" in msg


def _is_retryable(exc: Exception) -> bool:
    """Chỉ backoff cho rate-limit từng phút / 5xx / timeout — không cho quota."""
    if _is_quota_exhausted(exc):
        return False
    code = getattr(exc, "status_code", None)
    msg = str(exc)
    if code in _RETRYABLE_STATUS:
        # 429 quota đã bị loại ở trên
        return True
    if msg == "timeout" or "rate_limited" in msg:
        return True
    if code is None and msg.startswith("http_"):
        try:
            sc = int(msg.split("_", 1)[1])
            return sc in _RETRYABLE_STATUS
        except ValueError:
            return False
    return False


def _reason_tag(exc: Exception) -> str:
    if _is_quota_exhausted(exc):
        return "quota_exhausted"
    msg = str(exc)
    if "rate_limited" in msg:
        return "rate_limited"
    if msg == "timeout":
        return "timeout"
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return f"http_{code}"
    return (msg.split(":", 1)[0] or "error")[:40]


def generate_json(
    prompt: str,
    schema_hint: dict | None = None,
    *,
    cfg: dict | None = None,
    cache_key_parts: dict | None = None,
    use_cache: bool = True,
    provider_filter: str | None = None,
) -> dict:
    """Gọi LLM theo thứ tự provider → model; parse JSON object.

    Retry rate-limit 429/500/502/503/504 + timeout trên cùng model (backoff 2/4/8s, max 3).
    Quota exhausted → không backoff; skip model/provider ngay + flag ``llm_quota_exhausted:<provider>``.
    Circuit breaker: cùng provider/model lỗi liên tiếp N lần → bỏ qua cooldown phút.
    Meta gắn ``_meta``: provider, model, flags, cache_hit, usage, cost_usd.
    """
    load_dotenv_keys()
    full_cfg = cfg if cfg is not None else load_llm_cfg()
    debate = _debate_section(full_cfg)
    providers = list(debate.get("providers") or ["gemini", "glm"])
    if provider_filter:
        providers = [p for p in providers if p == provider_filter]
    temperature = float(debate.get("temperature", 0))
    timeout_sec = float(debate.get("timeout_sec", 45))
    max_retries = int(debate.get("max_retries_per_call", 3))
    max_retries = max(1, min(max_retries, 3))
    rpm = int(debate.get("rpm_limit", 30))
    cache_dir = debate.get("cache_dir") or "data/llm_cache"
    parts = dict(cache_key_parts or {})
    prompt_version = str(parts.get("prompt_version") or debate.get("prompt_version") or "v1")
    flags: list[str] = []
    ticker = str(parts.get("ticker") or "")
    as_of = str(parts.get("as_of") or "")
    p_hash = str(parts.get("payload_hash") or "")
    model_for_key = str(parts.get("model") or "debate")

    can_cache = bool(use_cache and ticker and as_of and p_hash)
    key = cache_key(
        ticker=ticker,
        as_of=as_of,
        model=model_for_key,
        prompt_version=prompt_version,
        payload_hash=p_hash or payload_hash({"prompt": prompt[:200]}),
    )

    if can_cache:
        cached, cflags = read_cache(cache_dir, key)
        flags.extend(cflags)
        if cached is not None:
            raw = cached.get("raw")
            if isinstance(raw, dict):
                out = dict(raw)
            else:
                out = {"bull": cached.get("bull") or [], "bear": cached.get("bear") or []}
            out["_meta"] = {
                "provider": cached.get("provider") or "cache",
                "model": cached.get("model") or model_for_key,
                "flags": flags + ["debate_cache_hit"],
                "cache_hit": True,
                "usage": cached.get("usage") or {},
                "cost_usd": float(cached.get("cost_usd") or 0.0),
            }
            return out

    last_err: Exception | None = None
    last_reason = "all_providers_failed"
    for provider in providers:
        if not _has_key(provider):
            flags.append(f"llm_missing_key_{provider}")
            continue
        provider_quota = False
        for model in _models_for(provider, debate):
            if _circuit_is_open(provider, model, debate):
                flags.append(f"llm_circuit_open_{provider}_{model}")
                continue
            for attempt in range(max_retries):
                try:
                    _wait_rpm(rpm)
                    parsed, usage = _call_provider_model(
                        provider,
                        prompt,
                        model=model,
                        debate=debate,
                        temperature=temperature,
                        timeout_sec=timeout_sec,
                        schema_hint=schema_hint,
                    )
                    in_tok = int(usage.get("input_tokens") or 0)
                    out_tok = int(usage.get("output_tokens") or 0)
                    cost = estimate_cost_usd(model, in_tok, out_tok, debate)
                    _circuit_record_success(provider, model)
                    if can_cache:
                        write_cache(
                            cache_dir,
                            key,
                            bull=list(parsed.get("bull") or []) if isinstance(parsed.get("bull"), list) else [],
                            bear=list(parsed.get("bear") or []) if isinstance(parsed.get("bear"), list) else [],
                            provider=provider,
                            model=model,
                            flags=flags,
                        )
                        try:
                            path = cache_path(cache_dir, key)
                            existing = json.loads(path.read_text(encoding="utf-8"))
                            if isinstance(existing, dict):
                                existing["raw"] = {k: v for k, v in parsed.items()}
                                existing["usage"] = usage
                                existing["cost_usd"] = cost
                                path.write_text(
                                    json.dumps(existing, ensure_ascii=False, indent=2),
                                    encoding="utf-8",
                                )
                        except (OSError, ValueError):
                            pass
                    meta_flags = list(flags)
                    if attempt > 0:
                        meta_flags.append(f"llm_retry_ok_{provider}_{model}")
                    parsed["_meta"] = {
                        "provider": provider,
                        "model": model,
                        "flags": meta_flags,
                        "cache_hit": False,
                        "usage": usage,
                        "cost_usd": cost,
                        "attempts_on_model": attempt + 1,
                    }
                    return parsed
                except (gemini_rest.GeminiRestError, glm_rest.GlmRestError, RuntimeError) as e:
                    last_err = e
                    last_reason = str(e)
                    reason = _reason_tag(e)
                    opened = _circuit_record_failure(provider, model, reason, debate)
                    if opened:
                        flags.append(f"llm_circuit_open_{provider}_{model}")

                    if _is_quota_exhausted(e):
                        # Không backoff — bỏ toàn bộ model còn lại của provider
                        flag = f"llm_quota_exhausted:{provider}"
                        if flag not in flags:
                            flags.append(flag)
                        provider_quota = True
                        flags.append(f"llm_model_exhausted_{provider}_{model}")
                        break

                    if _is_retryable(e) and attempt + 1 < max_retries:
                        sleep_for = _BACKOFF_SEC[min(attempt, len(_BACKOFF_SEC) - 1)]
                        time.sleep(sleep_for)
                        continue
                    # hết retry trên model này → model tiếp theo
                    flags.append(f"llm_model_exhausted_{provider}_{model}")
                    break
            if provider_quota:
                break
            # next model
        flags.append(f"llm_provider_exhausted_{provider}")
    err = RuntimeError(f"all_providers_failed:{last_err}")
    setattr(err, "flags", flags + [f"debate_llm_final_reason:{last_reason}"])
    raise err


def generate_json_with_fn(
    prompt: str,
    call_fn: Callable[[str], dict],
    *,
    flags: list[str] | None = None,
) -> dict:
    """Helper test: gọi hàm mock thay provider."""
    out = call_fn(prompt)
    if not isinstance(out, dict):
        raise RuntimeError("mock_not_dict")
    out.setdefault(
        "_meta",
        {"provider": "mock", "model": "mock", "flags": list(flags or []), "cache_hit": False},
    )
    return out
