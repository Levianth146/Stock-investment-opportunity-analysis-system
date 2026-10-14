"""M9 báo cáo PDF: định dạng vi-VN, câu tiêu đề, dịch cờ, hạng trên thước điểm, kiểm tra chữ trong PDF, API."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf
import pytest

from stockai.m7_scoring import debate as debate_mod
from stockai.m9_report.data import load_universe_from_cache, rank_of
from stockai.m9_report.fmt import fmt_multiple, fmt_num, fmt_pct_ratio, fmt_signed
from stockai.m9_report.text import conclusion_title, translate_flags
from stockai.m9_report.theme import load_flag_dict
from tests.test_api_011 import api_env, client  # noqa: F401  (fixture dùng lại)

BULL = {"text": "Cơ bản hỗ trợ điểm (+12,4): ROE 49,2%", "refs": ["m2.roe"]}
BEAR = {"text": "Rủi ro gây áp lực lên điểm (rủi ro cao hơn mức trung bình, −4,3): beta 1,20", "refs": ["m6.beta"]}
NEUTRAL_BULL = {"text": "Không có yếu tố tích cực nổi bật so với mức trung tính", "refs": ["m7.scores"]}


# --------------------------------------------------------------------------- định dạng số

def test_fmt_vi_vn():
    assert fmt_num(20150) == "20.150"
    assert fmt_num(1234567.891, 2) == "1.234.567,89"
    assert fmt_pct_ratio(0.285) == "28,5%"
    assert fmt_signed(-2.2) == "\u22122,2"
    assert fmt_signed(4.41) == "+4,4"
    assert fmt_signed(-0.01) == "0,0"
    assert fmt_multiple(7.3275) == "7,33 lần"
    for bad in (None, float("nan"), "abc"):
        assert fmt_num(bad) == "n/a"


# --------------------------------------------------------------------------- câu tiêu đề trang 2

def test_title_from_contributions_no_score_numbers():
    t = conclusion_title(
        "AAA",
        [BULL],
        [BEAR],
        score=62.2,
        rating="Mua",
        contributions={"F": 5.0, "T": -2.0, "V": 0.0, "S": 0.0, "R": -1.0},
        m2={"metrics": {"net_income_growth": {"value": 0.285}, "roe": {"value": 0.118}}},
        m3={"metrics": {"close": {"value": 20}, "ma20": {"value": 21}, "ma50": {"value": 22}}},
        m4={"metrics": {"pb": {"value": 2.0}, "sector_median_pb": {"value": 1.5}}},
        m5={},
        m6={},
        is_bank=False,
    )
    assert t.startswith("AAA: ")
    assert not re.search(r"[+\-\u2212]?\d+,\d+\s*điểm", t)
    assert "ROE" in t or "lợi nhuận" in t or "giá" in t


def test_title_missing_side_is_neutral():
    t = conclusion_title("AAA", [], [BEAR], score=17.9, rating="Bán")
    assert t.startswith("AAA: ") and "None" not in t
    assert "17,9 điểm" not in t
    t2 = conclusion_title("AAA", [NEUTRAL_BULL], [BEAR], score=17.9, rating="Bán")
    assert "Không có yếu tố" not in t2
    t3 = conclusion_title("AAA", [], [], score=None, rating=None)
    assert t3.startswith("AAA: ") and "None" not in t3


def test_title_respects_fit():
    t = conclusion_title("AAA", [BULL], [BEAR], score=62.2, rating="Mua", fits=lambda s: len(s) <= 70)
    assert len(t) <= 80


# --------------------------------------------------------------------------- dịch cờ

def test_translate_flags_known_and_unknown():
    fd = load_flag_dict()
    known, unknown = translate_flags(["quality_illiquid", "flag_khong_co_trong_tu_dien", "quality_illiquid"], fd)
    assert any("Thanh khoản" in s for s in known)
    assert unknown == ["flag_khong_co_trong_tu_dien"]


# --------------------------------------------------------------------------- hạng trên thước điểm

def _write_bundle(d: Path, ticker: str, score, *, scored: bool = True, h: str = "aaaa") -> None:
    m7 = {"score": score, "quality_gate": {"tier": "full" if scored else "insufficient", "scored": scored}}
    (d / f"{ticker}_2026-10-08_long_term_{h}.json").write_text(json.dumps({"m7": m7}), encoding="utf-8")


def test_rank_from_cache_fixture(tmp_path):
    _write_bundle(tmp_path, "AAA", 70.0)
    _write_bundle(tmp_path, "BBB", 55.0)
    _write_bundle(tmp_path, "CCC", 55.0)
    _write_bundle(tmp_path, "ZZZ", None, scored=False)
    (tmp_path / "DDD_2026-10-08_swing_aaaa.json").write_text(json.dumps({"m7": {"score": 99}}), encoding="utf-8")
    rows = load_universe_from_cache(tmp_path, "2026-10-08", "long_term")
    assert sorted(rows) == [("AAA", 70.0), ("BBB", 55.0), ("CCC", 55.0)]
    assert rank_of("BBB", 55.0, rows) == (2, 3)
    assert rank_of("CCC", 55.0, rows) == (3, 3)
    assert rank_of("NEW", 60.0, rows) == (2, 4)
    assert rank_of("ZZZ", None, rows) == (None, 3)


# --------------------------------------------------------------------------- PDF qua API

def _raise_llm(*a, **k):
    raise AssertionError("M9 không được gọi LLM")


def _pdf_checks(raw: bytes, *, min_pages: int) -> list[str]:
    with pymupdf.open(stream=raw, filetype="pdf") as doc:
        texts = [p.get_text() for p in doc]
        n = len(texts)
        assert n >= min_pages
        fonts = {f[3] for p in doc for f in p.get_fonts()}
        exts = {f[1] for p in doc for f in p.get_fonts()}
    for i, t in enumerate(texts, start=1):
        assert f"Trang {i}/{n}" in t
        assert "Báo cáo tự động, không phải khuyến nghị đầu tư" in t
        assert not re.search(r"\bNone\b|\bnan\b|\bNaN\b", t)
        for ch in ("\u00b7", "\u2192", "\u2014"):
            assert ch not in t
    assert any("Noto" in f or "DejaVu" in f for f in fonts)
    assert "n/a" not in exts
    return texts


def test_api_report_pdf_scored_no_llm(client):  # noqa: F811
    debate_mod.set_generate_fn(_raise_llm)
    try:
        for prof in ("long_term", "swing"):
            r = client.get("/api/report/AAA.pdf", params={"profile": prof})
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("application/pdf")
            texts = _pdf_checks(r.content, min_pages=4)
            full = "\n".join(texts)
            assert "điểm trên thang 0 đến 100" in full
            assert "Kiểm tra dữ liệu" in full
            assert "Nguồn luận điểm: mẫu tự động" not in full
            assert "(M8)" not in full
    finally:
        debate_mod.set_generate_fn(None)


def test_api_report_pdf_unranked_one_page(client):  # noqa: F811
    debate_mod.set_generate_fn(_raise_llm)
    try:
        r = client.get("/api/report/ZZZ.pdf", params={"profile": "long_term", "cover": "false"})
        assert r.status_code == 200
        texts = _pdf_checks(r.content, min_pages=1)
        assert len(texts) == 1
        assert "chưa đủ dữ liệu để xếp hạng" in texts[0]
        assert "điểm trên thang" not in texts[0]
    finally:
        debate_mod.set_generate_fn(None)


def test_api_report_uses_cached_debate(client, monkeypatch):  # noqa: F811
    cached = {"bull": [{"text": "AAA: biên lợi nhuận cải thiện rõ", "refs": ["m2.roe"]}],
              "bear": [{"text": "AAA: nợ vay tăng nhanh", "refs": ["m6.beta"]}], "model": "mock"}
    monkeypatch.setattr("stockai.api.debate_service.DebateService.read_cached", lambda self, s, p: cached)
    debate_mod.set_generate_fn(_raise_llm)
    try:
        r = client.get("/api/report/AAA.pdf", params={"profile": "long_term"})
        assert r.status_code == 200
        full = "\n".join(_pdf_checks(r.content, min_pages=4))
        assert "biên lợi nhuận cải thiện rõ" in full
        assert "Luận điểm do mô hình ngôn ngữ soạn, đã đối chiếu số liệu." in full
        assert "LLM" not in full
    finally:
        debate_mod.set_generate_fn(None)


def test_api_report_bad_profile(client):  # noqa: F811
    r = client.get("/api/report/AAA.pdf", params={"profile": "khong_hop_le"})
    assert r.status_code == 400
