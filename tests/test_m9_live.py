"""M9: khối dữ liệu thời gian thực tại thời điểm xuất PDF (giá trực tiếp/chốt phiên, VN-Index, độ rộng)."""
from __future__ import annotations

import pymupdf

from stockai.api import app as api_app
from stockai.m7_scoring import debate as debate_mod
from stockai.m9_report.data import sanitize_live
from tests.test_api_011 import api_env, client  # noqa: F401
from tests.test_m9_report import _raise_llm

LIVE = {
    "captured_at": "2026-10-15T16:35:12+07:00",
    "session_phase": "closed",
    "quote": {"price": 23450.0, "change": 250.0, "change_pct": 1.08, "volume": 1234567,
              "state": "closed", "basis": "close", "label": None, "ts": None},
    "index": {"name": "VN-Index", "price": 1712.34, "change_pct": -0.21, "basis": "close", "label": None},
    "breadth": {"up": 210, "down": 95, "flat": 40},
}


def test_sanitize_drops_bad_values():
    assert sanitize_live(None) == {}
    assert sanitize_live({"quote": {"price": "abc"}}) == {}
    assert sanitize_live({"quote": {"price": float("nan")}}) == {}
    assert sanitize_live({"quote": {"price": -5}}) == {}
    clean = sanitize_live(LIVE)
    assert clean["quote"]["price"] == 23450.0 and clean["breadth"]["up"] == 210
    assert clean["captured_at"].startswith("2026-10-15")


def _pdf_text(content: bytes) -> str:
    doc = pymupdf.open(stream=content, filetype="pdf")
    return " ".join(" ".join(p.get_text().split()) for p in doc)


def test_pdf_has_live_block_with_export_time(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(api_app, "_report_live", lambda request, store, sym: LIVE)
    debate_mod.set_generate_fn(_raise_llm)
    try:
        r = client.get("/api/report/AAA.pdf", params={"profile": "long_term"})
        assert r.status_code == 200
        full = _pdf_text(r.content)
        assert "Dữ liệu thời gian thực tại thời điểm xuất" in full
        assert "15/10/2026 16:35" in full
        assert "23.450" in full and "chốt phiên" in full.lower()
        assert "VN-Index" in full and "1.712,34" in full
        assert "không đổi theo giá trong phiên" in full
    finally:
        debate_mod.set_generate_fn(None)


def test_pdf_without_live_says_eod_only(client, monkeypatch):  # noqa: F811
    monkeypatch.setattr(api_app, "_report_live", lambda request, store, sym: {})
    debate_mod.set_generate_fn(_raise_llm)
    try:
        r = client.get("/api/report/AAA.pdf", params={"profile": "long_term"})
        assert r.status_code == 200
        full = _pdf_text(r.content)
        assert "Dữ liệu thời gian thực tại thời điểm xuất" not in full
        assert "không có dữ liệu trực tiếp tại thời điểm xuất" in full
    finally:
        debate_mod.set_generate_fn(None)
