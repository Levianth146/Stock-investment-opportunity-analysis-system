"""Debate LLM theo yêu cầu — cache API → rate limit/quota → LLM → TEMPLATE."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import yaml

from stockai.api.ratelimit import DebateRateLimiter
from stockai.api.store import DISCLAIMER, ResultStore, repo_root
from stockai.llm.generate import (
    _circuit_is_open,
    _has_key,
    _models_for,
    circuit_retry_after_sec,
    load_dotenv_keys,
    load_llm_cfg,
)
from stockai.llm.payload import build_debate_payload
from stockai.llm.quota_state import default_quota_path, format_blocked_until, is_blocked
from stockai.m7_scoring.debate_template import build_template_debate
from stockai.m7_scoring.run import run as run_m7


def _ai_attempt(
    state: str,
    reason_code: str | None = None,
    retry_after: float | int | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"state": state}
    if reason_code:
        out["reason_code"] = reason_code
    if retry_after is not None:
        out["retry_after"] = int(max(0, round(float(retry_after))))
    return out


def _models_availability() -> dict[str, Any]:
    """Quét provider/model: usable? blocked quota? circuit open?"""
    load_dotenv_keys()
    cfg = load_llm_cfg()
    debate = cfg.get("debate") if isinstance(cfg.get("debate"), dict) else {}
    providers = list(debate.get("providers") or [])
    cache_dir = debate.get("cache_dir") or "data/llm_cache"
    qpath = default_quota_path(cache_dir)

    usable: list[tuple[str, str]] = []
    blocked_quota: list[tuple[str, str, Any]] = []
    circuit_open: list[tuple[str, str, float | None]] = []
    missing_key: list[str] = []
    earliest_blocked = None
    earliest_circuit_retry: float | None = None

    for provider in providers:
        p = str(provider)
        if not _has_key(p):
            missing_key.append(p)
            continue
        for model in _models_for(p, debate):
            blocked, until = is_blocked(p, model, path=qpath)
            if blocked and until is not None:
                blocked_quota.append((p, model, until))
                if earliest_blocked is None or until < earliest_blocked:
                    earliest_blocked = until
                continue
            if _circuit_is_open(p, model, debate):
                ra = circuit_retry_after_sec(p, model)
                circuit_open.append((p, model, ra))
                if ra is not None and (earliest_circuit_retry is None or ra < earliest_circuit_retry):
                    earliest_circuit_retry = ra
                continue
            usable.append((p, model))

    has_key = bool(
        os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("ZAI_API_KEY", "").strip()
    )
    return {
        "debate": debate,
        "providers": providers,
        "has_key": has_key,
        "usable": usable,
        "blocked_quota": blocked_quota,
        "circuit_open": circuit_open,
        "missing_key": missing_key,
        "earliest_blocked": earliest_blocked,
        "earliest_circuit_retry": earliest_circuit_retry,
    }


def llm_public_status() -> dict[str, Any]:
    """Trạng thái LLM công khai — không lộ key / body lỗi.

    ``state``: ok | quota_blocked | circuit_open | no_key
    """
    info = _models_availability()
    usable = info["usable"]
    earliest_blocked = info["earliest_blocked"]
    earliest_circuit_retry = info["earliest_circuit_retry"]
    has_key = info["has_key"]
    providers = info["providers"]
    debate = info["debate"]

    if not has_key:
        state = "no_key"
        blocked_until = None
    elif usable:
        state = "ok"
        blocked_until = None
    elif info["blocked_quota"] and not info["circuit_open"]:
        state = "quota_blocked"
        blocked_until = earliest_blocked.isoformat() if earliest_blocked is not None else None
    elif info["circuit_open"] and not info["blocked_quota"]:
        state = "circuit_open"
        blocked_until = None
    elif info["blocked_quota"] or info["circuit_open"]:
        # Vừa quota vừa circuit — ưu tiên quota nếu không còn model nào
        if info["blocked_quota"] and not usable:
            # Còn model chỉ bị circuit? đã nằm trong usable=empty
            if info["circuit_open"] and earliest_circuit_retry is not None and (
                earliest_blocked is None
                or earliest_circuit_retry < max(0.0, (earliest_blocked.timestamp() - time.time()) if earliest_blocked else 1e9)
            ):
                state = "circuit_open"
                blocked_until = None
            else:
                state = "quota_blocked"
                blocked_until = earliest_blocked.isoformat() if earliest_blocked is not None else None
        else:
            state = "quota_blocked"
            blocked_until = earliest_blocked.isoformat() if earliest_blocked is not None else None
    else:
        state = "no_key"
        blocked_until = None

    display_provider: str | None = usable[0][0] if usable else None
    display_model: str | None = usable[0][1] if usable else None
    if display_provider is None and providers:
        display_provider = str(providers[0])
    if display_model is None and display_provider and isinstance(debate.get(display_provider), dict):
        display_model = debate[display_provider].get("model")

    out: dict[str, Any] = {
        "state": state,
        "provider": display_provider,
        "model": display_model,
        "key_configured": has_key,
        "blocked_until": blocked_until,
        "blocked_until_local": format_blocked_until(earliest_blocked) if earliest_blocked else None,
    }
    if state == "circuit_open" and earliest_circuit_retry is not None:
        out["retry_after"] = int(max(1, round(earliest_circuit_retry)))
    return out


def _quota_or_no_key() -> bool:
    """True chỉ khi thiếu key hoặc mọi model đều hết hạn mức (không chặn sớm 1 model)."""
    st = llm_public_status()
    return st.get("state") in ("no_key", "quota_blocked")


def _all_live_unavailable() -> tuple[bool, str | None, float | None]:
    """True khi không còn model nào gọi được (quota hoặc circuit).

    Trả (blocked, reason_code, retry_after_sec).
    """
    st = llm_public_status()
    state = st.get("state")
    if state == "ok":
        return False, None, None
    if state == "no_key":
        return True, "no_key", None
    if state == "circuit_open":
        return True, "circuit_open", st.get("retry_after")
    if state == "quota_blocked":
        retry = None
        iso = st.get("blocked_until")
        if iso:
            try:
                from datetime import datetime

                until = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
                retry = max(0.0, until.timestamp() - time.time())
            except ValueError:
                retry = None
        return True, "quota_blocked", retry
    return True, "unavailable", None


def _load_scoring_llm_cfg(profile: str) -> dict[str, Any]:
    root = repo_root()
    cfg: dict[str, Any] = {}
    for name in ("scoring", "llm"):
        fp = root / "config" / f"{name}.yaml"
        chunk = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
        if isinstance(chunk, dict):
            cfg.update(chunk)
    cfg["profile"] = profile
    return cfg


def _template_sides(snapshot: dict, upstream: dict, cfg: dict) -> tuple[list, list, list[str]]:
    score = (upstream.get("m7") or {}).get("score")
    rating = (upstream.get("m7") or {}).get("rating")
    scores = (upstream.get("m7") or {}).get("scores")
    payload = build_debate_payload(
        snapshot,
        upstream,
        cfg,
        score=score,
        rating=rating,
        scores=scores,
    )
    bull, bear, flags = build_template_debate(payload, cfg=cfg)
    return list(bull), list(bear), list(flags)


def _sanitize_flags(flags: list[str]) -> list[str]:
    out: list[str] = []
    for f in flags:
        if not isinstance(f, str):
            continue
        low = f.lower()
        if any(x in low for x in ("api_key", "traceback", "gemini_api_key", "zai_api_key")):
            continue
        out.append(f[:200] if len(f) > 200 else f)
    return out


class DebateService:
    def __init__(self, store: ResultStore, limiter: DebateRateLimiter) -> None:
        self.store = store
        self.limiter = limiter
        self.debate_cache_dir = Path(store.cache_dir) / "debate"
        self.debate_cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_file(self, symbol: str, profile: str) -> Path:
        snap_path = self.store.snapshot_path(symbol)
        mtime = snap_path.stat().st_mtime_ns
        raw = f"{symbol}|{profile}|{self.store.asof}|{mtime}"
        h = hashlib.sha256(raw.encode()).hexdigest()[:16]
        return self.debate_cache_dir / f"{symbol}_{profile}_{self.store.asof}_{h}.json"

    def _read_cache(self, symbol: str, profile: str) -> dict | None:
        path = self._cache_file(symbol, profile)
        if not path.is_file():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        if data.get("source") not in ("LLM", "CACHE"):
            return None
        if not isinstance(data.get("bull"), list) or not isinstance(data.get("bear"), list):
            return None
        return data

    def read_cached(self, symbol: str, profile: str) -> dict | None:
        """Bản debate LLM đã lưu (nếu có) — chỉ đọc đĩa, không gọi LLM (dùng cho xuất PDF)."""
        return self._read_cache(symbol, profile)

    def _write_cache(self, symbol: str, profile: str, payload: dict) -> None:
        path = self._cache_file(symbol, profile)
        try:
            path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=1, default=str),
                encoding="utf-8",
            )
        except OSError:
            pass

    def run(
        self,
        symbol: str,
        *,
        profile: str,
        refresh: bool = False,
        client_ip: str = "unknown",
    ) -> dict[str, Any]:
        """Trả debate kèm source LLM|CACHE|TEMPLATE — không 5xx vì LLM."""
        bundle = self.store.get_bundle(symbol, profile, debate_mode="template")
        snapshot = self.store.load_snapshot(symbol)
        upstream = {
            "m2": bundle.get("m2"),
            "m3": bundle.get("m3"),
            "m4": bundle.get("m4"),
            "m5": bundle.get("m5"),
            "m6": bundle.get("m6"),
            "m7": bundle.get("m7"),
        }
        cfg = _load_scoring_llm_cfg(profile)
        st = llm_public_status()

        # 1) Cache hợp lệ (không refresh)
        if not refresh:
            cached = self._read_cache(symbol, profile)
            if cached is not None:
                return self._with_quota(
                    {
                        "asof": self.store.asof,
                        "disclaimer": DISCLAIMER,
                        "symbol": symbol,
                        "profile": profile,
                        "source": "CACHE",
                        "model": cached.get("model") or st.get("model"),
                        "provider": cached.get("provider"),
                        "created_at": cached.get("created_at"),
                        "flags": _sanitize_flags(list(cached.get("flags") or []) + ["debate_api_cache_hit"]),
                        "reason": None,
                        "bull": list(cached.get("bull") or []),
                        "bear": list(cached.get("bear") or []),
                        "score": cached.get("score"),
                        "rating": cached.get("rating"),
                        "ai_attempt": _ai_attempt("skipped", "cache_hit"),
                    }
                )

        # 2) refresh chỉ khi còn ngân sách
        if refresh and not self.limiter.budget_ok(client_ip):
            bull, bear, tflags = _template_sides(snapshot, upstream, cfg)
            return self._template_pack(
                symbol,
                profile,
                bull,
                bear,
                tflags + ["debate_refresh_denied_no_budget"],
                "refresh_denied_no_budget",
                st,
                ai_attempt=_ai_attempt("skipped", "refresh_denied_no_budget"),
            )

        from stockai.m7_scoring import debate as debate_mod

        using_mock = debate_mod._generate_fn is not None

        # 3) quota / thiếu key → TEMPLATE (tests monkeypatch `_quota_or_no_key`)
        if not using_mock and _quota_or_no_key():
            bull, bear, tflags = _template_sides(snapshot, upstream, cfg)
            return self._template_pack(
                symbol,
                profile,
                bull,
                bear,
                tflags + ["debate_quota_or_missing_key"],
                "quota_or_missing_key",
                st,
                ai_attempt=_ai_attempt("skipped", "quota_or_missing_key"),
            )

        # 3b) Circuit mở hết model: không gọi, không trừ budget
        if not using_mock and st.get("state") == "circuit_open":
            bull, bear, tflags = _template_sides(snapshot, upstream, cfg)
            ra = st.get("retry_after")
            return self._template_pack(
                symbol,
                profile,
                bull,
                bear,
                tflags + ["debate_circuit_open"],
                "circuit_open",
                st,
                ai_attempt=_ai_attempt("skipped", "circuit_open", ra),
            )

        # 4) rate limit — chỉ giữ slot; hoàn lại nếu LLM không dùng thật
        ok, lim_reason = self.limiter.try_acquire(client_ip)
        if not ok:
            bull, bear, tflags = _template_sides(snapshot, upstream, cfg)
            return self._template_pack(
                symbol,
                profile,
                bull,
                bear,
                tflags + [f"debate_{lim_reason or 'rate_limit'}"],
                lim_reason or "rate_limit",
                st,
                ai_attempt=_ai_attempt("skipped", lim_reason or "rate_limit"),
            )
        acquired = True

        # 5) LLM live
        try:
            cfg_llm = copy.deepcopy(cfg)
            llm_l = dict(cfg_llm.get("llm") or {})
            d_l = dict(llm_l.get("debate") or {})
            d_l["mode"] = "llm"
            llm_l["debate"] = d_l
            cfg_llm["llm"] = llm_l
            cfg_llm["debate"] = d_l
            cfg_llm["_debate_flags"] = []
            m7_live = run_m7(snapshot, {**upstream}, cfg_llm)
            dflags = list(cfg_llm.get("_debate_flags") or []) + list(m7_live.get("flags") or [])
            bull = list(m7_live.get("bull") or [])
            bear = list(m7_live.get("bear") or [])

            if "m7_debate_llm_used" in dflags:
                # Chỉ giữ budget khi LLM thật sự dùng
                source = "CACHE" if "debate_cache_hit" in dflags else "LLM"
                real_model = cfg_llm.get("_debate_model") or st.get("model")
                real_provider = cfg_llm.get("_debate_provider")
                from datetime import datetime, timezone

                created = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                packed = {
                    "asof": self.store.asof,
                    "disclaimer": DISCLAIMER,
                    "symbol": symbol,
                    "profile": profile,
                    "source": source,
                    "model": real_model,
                    "provider": real_provider,
                    "created_at": created,
                    "flags": _sanitize_flags(dflags),
                    "reason": None,
                    "bull": bull,
                    "bear": bear,
                    "score": m7_live.get("score"),
                    "rating": m7_live.get("rating"),
                    "ai_attempt": _ai_attempt("ok"),
                }
                if source == "LLM":
                    self._write_cache(symbol, profile, packed)
                acquired = False  # đã dùng — không refund
                return self._with_quota(packed)

            # validator fail / fallback template → hoàn budget
            self.limiter.release(client_ip)
            acquired = False
            reason = next(
                (f.split(":", 1)[-1] for f in dflags if f.startswith("debate_fallback_reason:")),
                "llm_fallback_template",
            )
            reason_code = "llm_fallback_template"
            if "all_providers_failed" in str(reason):
                reason_code = "all_providers_failed"
            elif "circuit" in str(reason).lower():
                reason_code = "circuit_open"
            return self._template_pack(
                symbol,
                profile,
                bull,
                bear,
                dflags,
                reason,
                st,
                score=m7_live.get("score"),
                rating=m7_live.get("rating"),
                ai_attempt=_ai_attempt("failed", reason_code),
            )
        except Exception as e:
            if acquired:
                self.limiter.release(client_ip)
                acquired = False
            bull, bear, tflags = _template_sides(snapshot, upstream, cfg)
            return self._template_pack(
                symbol,
                profile,
                bull,
                bear,
                tflags + ["debate_llm_exception_template"],
                f"llm_error:{type(e).__name__}",
                st,
                ai_attempt=_ai_attempt("failed", f"llm_error:{type(e).__name__}"),
            )

    def _quota_remaining(self) -> int | None:
        """Số lượt live còn lại trong cửa sổ giờ (toàn cục). Không có limiter → None."""
        try:
            return int(self.limiter.global_limiter.remaining())
        except Exception:
            return None

    def _with_quota(self, payload: dict[str, Any]) -> dict[str, Any]:
        rem = self._quota_remaining()
        if rem is not None:
            payload["quota_remaining"] = rem
        return payload

    def _template_pack(
        self,
        symbol: str,
        profile: str,
        bull: list,
        bear: list,
        flags: list[str],
        reason: str | None,
        st: dict,
        *,
        score: Any = None,
        rating: Any = None,
        ai_attempt: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._with_quota(
            {
                "asof": self.store.asof,
                "disclaimer": DISCLAIMER,
                "symbol": symbol,
                "profile": profile,
                "source": "TEMPLATE",
                "model": st.get("model"),
                "flags": _sanitize_flags(flags),
                "reason": reason,
                "bull": bull,
                "bear": bear,
                "score": score,
                "rating": rating,
                "ai_attempt": ai_attempt
                or _ai_attempt("skipped", reason or "template"),
            }
        )
