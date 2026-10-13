"""Đảm bảo helpers trong tests/ import được khi pythonpath chỉ có src."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_TESTS = Path(__file__).resolve().parent
if str(_TESTS) not in sys.path:
    sys.path.insert(0, str(_TESTS))


@pytest.fixture(autouse=True)
def _stockai_llm_offline(monkeypatch):
    """Pytest luôn offline: không nạp .env LLM, không gọi mạng debate.

    Test nào cần key giả thì tự ``monkeypatch.setenv`` trong test.
    """
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    monkeypatch.setattr(
        "stockai.llm.generate.load_dotenv_keys",
        lambda *a, **k: None,
    )
    # reset mock generate hook giữa các test
    try:
        from stockai.m7_scoring import debate as _debate

        monkeypatch.setattr(_debate, "load_dotenv_keys", lambda *a, **k: None)
        _debate.set_generate_fn(None)
        yield
        _debate.set_generate_fn(None)
    except Exception:
        yield
