"""Debate LLM theo yêu cầu — cache API → rate limit/quota → LLM → TEMPLATE."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml

from stockai.api.ratelimit import DebateRateLimiter
from stockai.api.store import DISCLAIMER, ResultStore, repo_root
from stockai.llm.generate import load_dotenv_keys, load_llm_cfg
from stockai.llm.payload import build_debate_payload
from stockai.llm.quota_state import default_quota_path, format_blocked_until, is_blocked, load_quota_state
from stockai.m7_scoring.debate_template import build_template_debate
from stockai.m7_scoring.run import run as run_m7


def llm_public_status() -> dict[str, Any]:
    """Trạng thái LLM công khai — không lộ key / body lỗi."""
    load_dotenv_keys()
    cfg = load_llm_cfg()
    debate = cfg.get("debate") if isinstance(cfg.get("debate"), dict) else {}
    providers = list(debate.get("providers") or [])
    primary = providers[0] if providers else None
    model = None
    if primary and isinstance(debate.get(primary), dict):
        model = debate[primary].get("model")
    has_key = bool(
        os.environ.get("GEMINI_API_KEY", "").strip()
        or os.environ.get("ZAI_API_KEY", "").strip()
    )
    blocked_until = None
    try:
        cache_dir = debate.get("cache_dir") or "data/llm_cache"
        qpath = default_quota_path(cache_dir)
        if primary and model:
            blocked, until = is_blocked(primary, model, path=qpath)
            if blocked and until is not None:
                blocked_until = format_blocked_until(until)
        else:
            state = load_quota_state(path=qpath)
            if isinstance(state, dict):
                for key in state:
                    parts = str(key).split("/", 1)
                    if len(parts) != 2:
                        continue
                    blocked, until = is_blocked(parts[0], parts[1], path=qpath)
                    if blocked and until is not None:
                        blocked_until = format_blocked_until(until)
                        break
    except Exception:
        blocked_until = None

    return {
        "provider": primary,
        "model": model,
        "key_configured": has_key,
        "blocked_until": blocked_until,
    }


def _quota_or_no_key() -> bool:
    st = llm_public_status()
    if not st.get("key_configured"):
        return True
    return bool(st.get("blocked_until"))


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
        reason: str | None = None
        st = llm_public_status()

        # 1) Cache hợp lệ (không refresh)
        if not refresh:
            cached = self._read_cache(symbol, profile)
            if cached is not None:
                return {
                    "asof": self.store.asof,
                    "disclaimer": DISCLAIMER,
                    "symbol": symbol,
                    "profile": profile,
                    "source": "CACHE",
                    "model": cached.get("model") or st.get("model"),
                    "flags": _sanitize_flags(list(cached.get("flags") or []) + ["debate_api_cache_hit"]),
                    "reason": None,
                    "bull": list(cached.get("bull") or []),
                    "bear": list(cached.get("bear") or []),
                    "score": cached.get("score"),
                    "rating": cached.get("rating"),
                }

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
            )

        # 3) quota / thiếu key → TEMPLATE (bỏ qua khi pytest gắn mock generate_fn)
        from stockai.m7_scoring import debate as debate_mod

        using_mock = debate_mod._generate_fn is not None
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
            )

        # 4) rate limit
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
            )

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
                source = "CACHE" if "debate_cache_hit" in dflags else "LLM"
                model = st.get("model")
                packed = {
                    "asof": self.store.asof,
                    "disclaimer": DISCLAIMER,
                    "symbol": symbol,
                    "profile": profile,
                    "source": source,
                    "model": model,
                    "flags": _sanitize_flags(dflags),
                    "reason": None,
                    "bull": bull,
                    "bear": bear,
                    "score": m7_live.get("score"),
                    "rating": m7_live.get("rating"),
                }
                if source == "LLM":
                    self._write_cache(symbol, profile, packed)
                return packed

            # validator fail / fallback template
            reason = next(
                (f.split(":", 1)[-1] for f in dflags if f.startswith("debate_fallback_reason:")),
                "llm_fallback_template",
            )
            return self._template_pack(
                symbol, profile, bull, bear, dflags, reason, st, score=m7_live.get("score"), rating=m7_live.get("rating")
            )
        except Exception as e:
            bull, bear, tflags = _template_sides(snapshot, upstream, cfg)
            return self._template_pack(
                symbol,
                profile,
                bull,
                bear,
                tflags + ["debate_llm_exception_template"],
                f"llm_error:{type(e).__name__}",
                st,
            )

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
    ) -> dict[str, Any]:
        return {
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
        }

