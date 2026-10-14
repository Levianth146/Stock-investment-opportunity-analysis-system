"""Hàng đợi job debate AI bất đồng bộ — không chặn HTTP request."""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable

from stockai.api.debate_service import DebateService


@dataclass
class DebateJob:
    """Trạng thái một job tạo luận điểm AI."""

    job_id: str
    symbol: str
    profile: str
    state: str = "queued"  # queued|running|ok|failed
    attempt: int = 0
    reason_code: str | None = None
    retry_after: int | None = None
    result: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    client_ip: str = "unknown"

    def public(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "job_id": self.job_id,
            "symbol": self.symbol,
            "profile": self.profile,
            "state": self.state,
            "attempt": self.attempt,
        }
        if self.reason_code:
            out["reason_code"] = self.reason_code
        if self.retry_after is not None:
            out["retry_after"] = int(self.retry_after)
        if self.state in ("ok", "failed") and self.result is not None:
            out["result"] = self.result
        return out


class DebateJobManager:
    """Pool nền: tối đa ``max_workers`` job; idempotent theo (symbol, profile) đang chạy."""

    def __init__(
        self,
        debate_service: DebateService,
        *,
        max_workers: int = 2,
    ) -> None:
        self.svc = debate_service
        self._lock = threading.RLock()
        self._jobs: dict[str, DebateJob] = {}
        # ticker|profile → job_id đang queued/running
        self._active: dict[str, str] = {}
        self._executor = ThreadPoolExecutor(
            max_workers=max(1, int(max_workers)),
            thread_name_prefix="debate-job",
        )
        self._futures: dict[str, Future] = {}

    def _key(self, symbol: str, profile: str) -> str:
        return f"{symbol.strip().upper()}|{profile}"

    def submit(
        self,
        symbol: str,
        *,
        profile: str,
        client_ip: str = "unknown",
        run_fn: Callable[..., dict[str, Any]] | None = None,
    ) -> DebateJob:
        """Tạo job mới hoặc trả job đang chạy cùng mã (idempotent)."""
        sym = symbol.strip().upper()
        key = self._key(sym, profile)
        with self._lock:
            existing_id = self._active.get(key)
            if existing_id and existing_id in self._jobs:
                job = self._jobs[existing_id]
                if job.state in ("queued", "running"):
                    return job
            job_id = uuid.uuid4().hex[:16]
            job = DebateJob(
                job_id=job_id,
                symbol=sym,
                profile=profile,
                state="queued",
                client_ip=client_ip,
            )
            self._jobs[job_id] = job
            self._active[key] = job_id
            fn = run_fn or self._default_run
            fut = self._executor.submit(self._worker, job_id, fn)
            self._futures[job_id] = fut
            return job

    def get(self, job_id: str) -> DebateJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def get_for_symbol(self, symbol: str, profile: str, job_id: str) -> DebateJob | None:
        job = self.get(job_id)
        if job is None:
            return None
        if job.symbol != symbol.strip().upper() or job.profile != profile:
            return None
        return job

    def _default_run(self, job: DebateJob) -> dict[str, Any]:
        return self.svc.run(
            job.symbol,
            profile=job.profile,
            refresh=True,
            client_ip=job.client_ip,
        )

    def _worker(self, job_id: str, run_fn: Callable[[DebateJob], dict[str, Any]]) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.state = "running"
            job.attempt = max(1, job.attempt + 1)
            job.updated_at = time.time()
        try:
            result = run_fn(job)
            with self._lock:
                job = self._jobs[job_id]
                job.result = result
                job.updated_at = time.time()
                src = str((result or {}).get("source") or "").upper()
                ai = (result or {}).get("ai_attempt") or {}
                if src in ("LLM", "CACHE") or ai.get("state") == "ok":
                    job.state = "ok"
                    job.reason_code = None
                    job.retry_after = None
                else:
                    job.state = "failed"
                    job.reason_code = str(
                        ai.get("reason_code")
                        or (result or {}).get("reason")
                        or "llm_fallback_template"
                    )
                    ra = ai.get("retry_after")
                    job.retry_after = int(ra) if ra is not None else None
        except Exception as e:
            with self._lock:
                job = self._jobs[job_id]
                job.state = "failed"
                job.reason_code = f"llm_error:{type(e).__name__}"
                job.result = {
                    "source": "TEMPLATE",
                    "reason": job.reason_code,
                    "ai_attempt": {
                        "state": "failed",
                        "reason_code": job.reason_code,
                    },
                }
                job.updated_at = time.time()
        finally:
            with self._lock:
                job = self._jobs.get(job_id)
                if job is not None:
                    key = self._key(job.symbol, job.profile)
                    if self._active.get(key) == job_id:
                        self._active.pop(key, None)
                self._futures.pop(job_id, None)

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait)
