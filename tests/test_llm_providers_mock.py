"""US4: mock requests cho Gemini + GLM (success / parse error / 429)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from stockai.llm.providers import gemini_rest, glm_rest


def test_gemini_success_and_429(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}],
    }
    with patch("stockai.llm.providers.gemini_rest.requests.post", return_value=ok) as post:
        out = gemini_rest.generate_content_json("hi")
        assert out == {"ok": True}
        assert post.called
        # không đưa key vào URL query
        args, kwargs = post.call_args
        assert "key=" not in args[0]
        assert kwargs["headers"].get("x-goog-api-key") == "fake"
        gen_cfg = kwargs["json"]["generationConfig"]
        assert gen_cfg["maxOutputTokens"] >= 2048
        assert gen_cfg["responseMimeType"] == "application/json"
        assert "thinkingConfig" in gen_cfg
        assert gen_cfg["thinkingConfig"]["thinkingLevel"] in ("LOW", "MINIMAL")

    bad = MagicMock()
    bad.status_code = 429
    bad.text = "rate limit per minute"
    with patch("stockai.llm.providers.gemini_rest.requests.post", return_value=bad):
        with pytest.raises(gemini_rest.GeminiRestError) as ei:
            gemini_rest.generate_content_json("hi")
        assert ei.value.status_code == 429


def test_glm_success_and_parse_error(monkeypatch):
    monkeypatch.setenv("ZAI_API_KEY", "fake-zai")
    ok = MagicMock()
    ok.status_code = 200
    ok.json.return_value = {
        "choices": [{"message": {"content": '{"a": 1}'}}],
    }
    with patch("stockai.llm.providers.glm_rest.requests.post", return_value=ok):
        assert glm_rest.chat_completions_json("x") == {"a": 1}

    bad = MagicMock()
    bad.status_code = 200
    bad.json.return_value = {"choices": [{"message": {"content": "not-json"}}]}
    with patch("stockai.llm.providers.glm_rest.requests.post", return_value=bad):
        with pytest.raises(glm_rest.GlmRestError) as ei:
            glm_rest.chat_completions_json("x")
        assert "parse_json" in str(ei.value)
