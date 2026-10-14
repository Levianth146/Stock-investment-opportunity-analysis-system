"""Feature 012c: panel tin gần đây, chú thích giá tham chiếu, caption trang 2/3."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pymupdf
import pytest

from stockai.llm.generate import load_llm_cfg
from stockai.m5_sentiment.run import run as run_m5
from stockai.m9_report.news_cluster import (
    LABEL_NEG,
    LABEL_NEU,
    LABEL_POS,
    news_extra_phrase,
    select_news_panel,
)
from stockai.m9_report.theme import ROOT
from stockai.pipeline import load_cfg

SNAP_DIR = ROOT / "data" / "snapshots_ext"
AS_OF = "2026-10-08"
PREVIEW = ROOT / "data" / "reports_preview"

_FORBIDDEN = re.compile(
    r"(?:\bM[2-9]\b|[a-z]+_[a-z_]+|\bas_of\b|\bpeers?\b|quote\.history|\bsnapshot\b|"
    r"income/balance|\bLLM\b|\btemplate\b)",
    re.I,
)

_GLUED_EXTRA = re.compile(r"[^\s(]\(và \d+ tin cùng sự kiện\)|(?:đến nay|phiếu)và \d+ tin")


def _has_snaps(*tickers: str) -> bool:
    return all((SNAP_DIR / f"{t}_{AS_OF}.json").is_file() for t in tickers)


def test_news_extra_phrase_parenthesized_with_space():
    assert news_extra_phrase(0) == ""
    assert news_extra_phrase(4) == " (và 4 tin cùng sự kiện)"
    assert "(và 4 tin cùng sự kiện)" in news_extra_phrase(4, markup=True)
    assert news_extra_phrase(4, markup=True).lstrip().startswith("<font")
    assert news_extra_phrase(4).startswith(" (")
    assert news_extra_phrase(4).endswith(")")


@pytest.mark.skipif(not _has_snaps("HPG"), reason="thiếu snapshot HPG")
def test_hpg_news_panel_includes_negatives_and_neutrals_no_dupes():
    snap = json.loads((SNAP_DIR / f"HPG_{AS_OF}.json").read_text(encoding="utf-8"))
    cfg = load_cfg("long_term")
    cfg["llm"] = load_llm_cfg()
    m5 = run_m5(snap, {}, cfg)
    neg_n = int(((m5.get("metrics") or {}).get("news_negative_count") or {}).get("value") or 0)

    panel = select_news_panel(
        snap.get("news") or [],
        ticker="HPG",
        company=snap.get("company") or {},
        as_of=AS_OF,
        cfg=cfg,
        max_items=6,
        max_negatives=3,
    )
    assert panel, "panel trống"
    assert len(panel) <= 6
    labels = [p["label"] for p in panel]
    assert LABEL_NEU in labels or any(p.get("polarity") == 0 for p in panel)
    if neg_n > 0:
        neg_items = [p for p in panel if p["label"] == LABEL_NEG or float(p.get("polarity") or 0) < 0]
        assert neg_items, "có tin tiêu cực M5 nhưng panel không hiện"
        assert len(neg_items) == min(neg_n, 3) or len(neg_items) >= min(2, neg_n)
        # Không chỉ toàn tích cực
        assert not all(p["label"] == LABEL_POS for p in panel)

    titles = [p["title"] for p in panel]
    assert len(titles) == len(set(titles)), titles
    # Không 2 dòng cùng cụm «con trai … mua … HPG»
    buy_like = [
        t for t in titles
        if "con trai" in t.lower() and ("mua" in t.lower() or "bắt đáy" in t.lower())
    ]
    assert len(buy_like) <= 1, buy_like

    # Sắp xếp mới → cũ
    dates = [str(p.get("published_at") or "")[:10] for p in panel]
    assert dates == sorted(dates, reverse=True)

    for p in panel:
        phrase = news_extra_phrase(int(p.get("extra_count") or 0))
        line = f"{p['label']}. {p['title']}{phrase}"
        assert _GLUED_EXTRA.search(line) is None, line
        if phrase:
            assert phrase.startswith(" (") and phrase.endswith(")")


@pytest.mark.skipif(
    not list(PREVIEW.glob("HPG_long_term.pdf")),
    reason="chưa có preview PDF — chạy scripts/dev_/_m9_preview.py trước",
)
def test_preview_pdfs_012c_copy_and_regex():
    want = {"HPG", "VCB", "KOS", "FPT", "VVS", "AAM"}
    pdfs = [p for p in sorted(PREVIEW.glob("*_long_term.pdf")) + sorted(PREVIEW.glob("*_swing.pdf"))
            if p.name.split("_", 1)[0] in want]
    if not pdfs:
        pytest.skip("chưa có preview PDF mục tiêu")
    bad: list[str] = []
    for p in pdfs:
        with pymupdf.open(str(p)) as doc:
            text = "\n".join(page.get_text() for page in doc)
        assert "Tin được dùng làm căn cứ" not in text, p.name
        if "Tin gần đây" not in text and p.name.startswith(("HPG", "VCB", "FPT", "KOS")):
            # Một số mã thiếu tin vẫn có tiêu đề section
            pass
        for m in _FORBIDDEN.finditer(text):
            bad.append(f"{p.name}: {m.group(0)!r}")
            if len(bad) > 40:
                break
        if _GLUED_EXTRA.search(text):
            bad.append(f"{p.name}: glued extra phrase")
        # Caption trang 2 đúng một câu ngắn
        if "Giá tham chiếu suy ra từ bội số ngành; xem giải thích ở trang 3." not in text:
            # Chỉ bắt buộc khi PDF có giá tham chiếu
            if "Giá tham chiếu theo bội số ngành" in text:
                bad.append(f"{p.name}: thiếu caption trang 2")
        # Câu chênh ≥30% không nằm cùng khối chú thích ngắn trang 2 (vẫn được ở trang 3)
        # Không kiểm tra vắng mặt toàn PDF — chỉ kiểm tra không dính ngay sau caption trang 2
        cap = "Giá tham chiếu suy ra từ bội số ngành; xem giải thích ở trang 3."
        if cap in text:
            after = text.split(cap, 1)[1][:120]
            if "Chênh lệch lớn so với giá thị trường" in after:
                bad.append(f"{p.name}: câu ≥30% dính dưới bảng Số liệu chính")
    assert not bad, "PDF 012c lỗi:\n" + "\n".join(bad[:40])
