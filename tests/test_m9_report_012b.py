"""Feature 012b: ngân hàng P/B, phân vị ngành, tin cluster, PDF sạch mã kỹ thuật."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf
import pytest

from stockai.llm.generate import load_llm_cfg
from stockai.llm.payload import build_debate_payload
from stockai.m4_valuation.sector_stats import (
    load_sector_stats,
    lookup_sector_medians,
    percentile_rank,
)
from stockai.m7_scoring.debate_template import build_template_debate
from stockai.m7_scoring.scoring import compute_score, to_rating
from stockai.m9_report.news_cluster import cluster_news_for_report
from stockai.m9_report.sector_band import resolve_sector_band
from stockai.m9_report.theme import ROOT
from stockai.pipeline import _safe, load_cfg

SNAP_DIR = ROOT / "data" / "snapshots_ext"
AS_OF = "2026-10-08"
PREVIEW = ROOT / "data" / "reports_preview"

_FORBIDDEN = re.compile(
    r"(?:\bM[2-9]\b|[a-z]+_[a-z_]+|\bas_of\b|\bpeers?\b|quote\.history|\bsnapshot\b|"
    r"income/balance|\bLLM\b|\btemplate\b)",
    re.I,
)


def _has_snaps(*tickers: str) -> bool:
    return all((SNAP_DIR / f"{t}_{AS_OF}.json").is_file() for t in tickers)


def _upstream(ticker: str):
    from stockai.m2_fundamental.run import run as run_m2
    from stockai.m3_technical.run import run as run_m3
    from stockai.m4_valuation.run import run as run_m4
    from stockai.m5_sentiment.run import run as run_m5
    from stockai.m6_risk.run import run as run_m6

    snap = json.loads((SNAP_DIR / f"{ticker}_{AS_OF}.json").read_text(encoding="utf-8"))
    cfg = load_cfg("long_term")
    llm = load_llm_cfg()
    cfg["llm"] = llm
    if isinstance(llm.get("debate"), dict):
        cfg["debate"] = llm["debate"]
    up: dict = {}
    for name, fn in (
        ("m2", run_m2),
        ("m3", run_m3),
        ("m4", run_m4),
        ("m5", run_m5),
        ("m6", run_m6),
    ):
        up[name] = _safe(name, fn, snap, up, cfg, "module_out")
    return snap, up, cfg


@pytest.mark.skipif(not _has_snaps("VCB"), reason="thiếu snapshot VCB")
def test_vcb_bank_valuation_uses_pb_not_pe_as_reason():
    snap, up, cfg = _upstream("VCB")
    assert snap["company"].get("is_bank") is True

    def sc(m: str):
        o = up.get(m)
        return None if (o is None or o.get("status") == "error") else o.get("score")

    comp = compute_score(
        {"F": sc("m2"), "T": sc("m3"), "V": sc("m4"), "S": sc("m5"), "R": sc("m6")},
        "long_term",
        cfg,
    )
    rating, _ = to_rating(comp["score"], comp["scores"]["R"], cfg)
    payload = build_debate_payload(
        snap, up, cfg, score=comp["score"], rating=rating, scores=comp["scores"]
    )
    assert payload.get("is_bank") is True
    bull, bear, _ = build_template_debate(payload, cfg=cfg)
    texts = "\n".join(x["text"] for x in bull + bear)
    # Không lấy P/E làm lý do định giá (V)
    for item in bear + bull:
        t = item["text"]
        if "Định giá" in t or "định giá" in t:
            assert "P/E" not in t and "p/e" not in t.lower(), t
            assert "P/B" in t or "p/b" in t.lower() or "ROE" in t
    assert "P/B" in texts


@pytest.mark.skipif(not _has_snaps("HPG"), reason="thiếu snapshot HPG")
def test_hpg_news_cluster_no_duplicate_event_lines():
    snap, up, _ = _upstream("HPG")
    m5 = up["m5"]
    news_by_id = {
        str(n.get("id")): n for n in snap.get("news") or [] if isinstance(n, dict) and n.get("id")
    }
    clustered = cluster_news_for_report(m5.get("evidence") or [], news_by_id)
    titles = [c["title"] for c in clustered]
    # Không còn 2 dòng cùng cụm «con trai … mua … HPG»
    buy_like = [
        t for t in titles
        if "con trai" in t.lower() and ("mua" in t.lower() or "bắt đáy" in t.lower())
    ]
    assert len(buy_like) <= 1, buy_like


@pytest.mark.skipif(not _has_snaps("HPG"), reason="thiếu snapshot HPG")
def test_percentile_matches_m4_within_half_point():
    snap, up, _ = _upstream("HPG")
    m4 = up["m4"]
    pe = (m4.get("metrics") or {}).get("pe", {}).get("value")
    pb = (m4.get("metrics") or {}).get("pb", {}).get("value")
    sector = (snap.get("company") or {}).get("sector")
    band = resolve_sector_band(sector, pe=pe, pb=pb)
    stats = load_sector_stats(ROOT / "data" / "valuation_sector_stats.json")
    med = lookup_sector_medians(stats, sector)
    if pe is not None and med.pe_sorted:
        expected = 100.0 * float(percentile_rank(float(pe), med.pe_sorted))
        got = band["pe"]["percentile"]
        assert got is not None
        assert abs(got - expected) < 0.5
    if pb is not None and med.pb_sorted:
        expected = 100.0 * float(percentile_rank(float(pb), med.pb_sorted))
        got = band["pb"]["percentile"]
        assert got is not None
        assert abs(got - expected) < 0.5


@pytest.mark.skipif(
    not list(PREVIEW.glob("HPG_long_term.pdf")),
    reason="chưa có preview PDF — chạy scripts/dev_/_m9_preview.py trước",
)
def test_preview_pdfs_reject_code_dumped_strings():
    """Quét mọi PDF preview; bỏ qua nếu file cũ hơn 12h sau khi chưa regenerate (CI)."""
    pdfs = sorted(PREVIEW.glob("*_long_term.pdf")) + sorted(PREVIEW.glob("*_swing.pdf"))
    # Chỉ quét các mã feature 012b
    want = {"HPG", "VCB", "KOS", "FPT", "VVS", "AAM"}
    pdfs = [p for p in pdfs if p.name.split("_", 1)[0] in want]
    if not pdfs:
        pytest.skip("chưa có preview PDF mục tiêu")
    bad: list[str] = []
    for p in pdfs:
        with pymupdf.open(str(p)) as doc:
            text = "\n".join(page.get_text() for page in doc)
        for m in _FORBIDDEN.finditer(text):
            bad.append(f"{p.name}: {m.group(0)!r} @ …{text[max(0, m.start()-20):m.end()+20]!r}")
            if len(bad) > 40:
                break
        if len(bad) > 40:
            break
    assert not bad, "PDF còn chuỗi kỹ thuật bị cấm:\n" + "\n".join(bad[:40])
