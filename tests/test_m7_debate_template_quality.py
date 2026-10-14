"""Round-2: template quality — tiếng Việt, số VN, tin không lặp, M8 pass."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from stockai.llm.generate import load_llm_cfg
from stockai.llm.payload import build_debate_payload, metric_display_name
from stockai.m2_fundamental.run import run as run_m2
from stockai.m3_technical.run import run as run_m3
from stockai.m4_valuation.run import run as run_m4
from stockai.m5_sentiment.run import run as run_m5
from stockai.m6_risk.run import run as run_m6
from stockai.m7_scoring.debate_template import build_template_debate
from stockai.m7_scoring.run import run as run_m7
from stockai.m8_validate.run import run as run_m8
from stockai.pipeline import _safe, load_cfg

ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = ROOT / "data" / "snapshots_ext"
AS_OF = "2026-10-08"

_RAW_KEY_RE = re.compile(r"m\d\.\w+")
_LONG_DECIMAL_RE = re.compile(r"\d+\.\d{5,}")
# Thập phân kiểu Anh 1–2 số; cho phép nhóm nghìn N.NNN
_EN_DECIMAL_RE = re.compile(r"(?<![\d.])\d+\.\d{1,2}(?!\d)")
_THOUSAND_RE = re.compile(r"^\d{1,3}(\.\d{3})+$")
# Tên metric tiếng Anh / snake thường lộ
_EN_METRIC_FRAGMENTS = (
    "annualized",
    "volatility",
    "drawdown",
    "sentiment",
    "net_income",
    "revenue_growth",
    "volume_ratio",
    "max_drawdown",
    "var_95",
    "price_close",
)


def _has_real_snaps() -> bool:
    return all((SNAP_DIR / f"{t}_{AS_OF}.json").is_file() for t in ("HPG", "VCB", "KOS", "PAN", "VIC"))


pytestmark = pytest.mark.skipif(not _has_real_snaps(), reason="thiếu snapshots_ext HPG/VCB/KOS/PAN/VIC")


def _upstream(ticker: str) -> tuple[dict, dict, dict]:
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


def _template_for(ticker: str):
    snap, up, cfg = _upstream(ticker)
    from stockai.m7_scoring.scoring import compute_score, to_rating

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
    bull, bear, flags = build_template_debate(payload, cfg=cfg)
    return snap, up, cfg, payload, bull, bear, flags


def _assert_vi_numbers(text: str) -> None:
    assert not _LONG_DECIMAL_RE.search(text), f"long decimal in text: {text}"
    for m in re.finditer(r"\d+\.\d+", text):
        tok = m.group(0)
        if _THOUSAND_RE.fullmatch(tok):
            continue
        # năm không có dấu chấm — mọi \d+\.\d+ còn lại là lỗi (trừ nghìn)
        pytest.fail(f"số kiểu Anh còn lại '{tok}' trong: {text}")
    assert not _EN_DECIMAL_RE.search(text), f"English decimal in text: {text}"


def _assert_no_en_metric_names(text: str) -> None:
    low = text.lower()
    for frag in _EN_METRIC_FRAGMENTS:
        # "Biến động năm hóa" không chứa "annualized"; "volatility" Anh thì fail
        if frag == "volatility" and "biến động" in low:
            # chỉ fail nếu còn chữ volatility tiếng Anh
            if "volatility" in low:
                pytest.fail(f"English metric fragment '{frag}' in: {text}")
            continue
        if frag == "drawdown" and "sụt giảm" in low:
            if "drawdown" in low:
                pytest.fail(f"English metric fragment '{frag}' in: {text}")
            continue
        if frag == "sentiment" and ("điểm tin" in low or "độ phân cực" in low or "tin tích cực" in low or "tin tiêu cực" in low):
            if "sentiment" in low:
                pytest.fail(f"English metric fragment '{frag}' in: {text}")
            continue
        if frag in low:
            pytest.fail(f"English metric fragment '{frag}' in: {text}")


def _assert_news_once(text: str) -> None:
    quotes = re.findall(r"«([^»]+)»", text)
    assert len(quotes) == len(set(quotes)), f"repeated «…» in: {text}"
    # Không lặp title: «title» xuất hiện sau khi title đã in ngoài cặp «»
    for q in quotes:
        # đếm lần title xuất hiện; cho phép 1 (trong «»)
        assert text.count(q) == 1, f"title repeated outside «»: {text}"


@pytest.mark.parametrize("ticker", ["HPG", "VCB", "KOS", "PAN", "VIC"])
def test_template_round2_quality(ticker):
    _, _, _, _, bull, bear, flags = _template_for(ticker)
    assert "debate_fallback_template" in flags
    for item in bull + bear:
        text = item["text"]
        assert not _RAW_KEY_RE.search(text), f"raw key in text: {text}"
        _assert_vi_numbers(text)
        _assert_no_en_metric_names(text)
        _assert_news_once(text)
        assert "độ lệch" not in text.lower(), f"còn 'độ lệch': {text}"
        if "trụ rủi ro" in text.lower():
            assert "rủi ro thấp hơn mức trung bình" in text or "rủi ro cao hơn mức trung bình" in text


def test_kos_bull_excludes_net_income_growth():
    _, _, _, payload, bull, bear, _ = _template_for("KOS")
    nig = (payload.get("metrics") or {}).get("m2.net_income_growth") or {}
    assert isinstance(nig.get("value"), (int, float)) and nig["value"] < 0
    for item in bull:
        refs = item.get("refs") or []
        text = item.get("text") or ""
        assert "m2.net_income_growth" not in refs
        assert "net_income_growth" not in text
        assert "Tăng trưởng lợi nhuận" not in text
    assert any("Không có yếu tố tích cực" in (it.get("text") or "") for it in bull)


@pytest.mark.parametrize("ticker", ["HPG", "VCB", "KOS"])
def test_template_refs_justified_and_m8_pass(ticker):
    snap, up, cfg, payload, bull, bear, _ = _template_for(ticker)
    metrics = payload.get("metrics") or {}
    news_by_ref = {
        n["ref"]: n for n in (payload.get("news") or []) if isinstance(n, dict) and n.get("ref")
    }
    for item in bull + bear:
        text = item.get("text") or ""
        refs = item.get("refs") or []
        assert refs, "refs rỗng"
        for ref in refs:
            if ref.startswith("n"):
                n = news_by_ref.get(ref)
                assert n, f"news ref {ref} không trong payload"
                title = (n.get("title") or "")[:20]
                assert title and title in text, f"news ref {ref} không được nhắc trong text"
            else:
                entry = metrics.get(ref) or {}
                dname = entry.get("display_name") or metric_display_name(ref, cfg)
                disp = entry.get("display") or ""
                ok = (
                    (dname and dname.lower() in text.lower())
                    or (disp and disp in text)
                    or ("Không có yếu tố" in text and ref.split(".")[0] in {"m2", "m3", "m4", "m5", "m6"})
                    or any(c in text for c in ("F=", "T=", "V=", "S=", "R="))
                )
                assert ok, f"metric ref {ref} không được nhắc trong text: {text}"

    up["m7"] = run_m7(snap, up, cfg)
    up["m7"] = {**up["m7"], "bull": bull, "bear": bear}
    out = run_m8(snap, up, cfg)
    assert not any("debate_ungrounded" in (i.get("message") or "") for i in out["issues"])
    assert out["status"] in ("pass", "warn")
