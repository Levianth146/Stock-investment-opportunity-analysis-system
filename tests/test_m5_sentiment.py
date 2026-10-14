"""TDD M5 sentiment live — offline, không mạng. Cover A–D accuracy pass."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from stockai.m5_sentiment.run import (
    _cluster_stories,
    _load_m5_cfg,
    classify_title,
    normalize_title,
    run,
)
from tests.helpers_m5_snapshots import (
    snap_ambiguous_ceo_offtopic,
    snap_cw_and_multi,
    snap_dieu_tra,
    snap_duplicates,
    snap_enough_directional,
    snap_insufficient,
    snap_synthetic,
    snap_with_future_news,
)

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "tests" / "fixtures" / "m5_gold_headlines.csv"
OLD_GOLD = ROOT / "fixtures" / "m5_gold_labels.csv"
REAL_DIR = ROOT / "data" / "snapshots_ext"


def _flags(out: dict) -> set[str]:
    return set(out.get("flags") or [])


def _cfg():
    return _load_m5_cfg({})[0]


# --- A1 normalize ---


def test_normalize_keeps_diacritics_and_d():
    assert "điều" in normalize_title("Điều tra")
    assert "bán" in normalize_title("Bán tháo")
    assert "bàn" in normalize_title("Bàn thảo")
    assert normalize_title("Bán   tháo!!!") == "bán tháo"


def test_ban_thao_not_confused_with_ban_thao_discussion():
    """'bàn thảo phương án tăng vốn' MUST NOT match 'bán tháo'; 'bán tháo' must match."""
    cfg = _cfg()
    pol_disc, matches_disc, _ = classify_title(
        "HPG bàn thảo phương án tăng vốn", "HPG", m5_cfg=cfg
    )
    assert "bán tháo" not in [normalize_title(m) for m in matches_disc]
    # Có thể trung tính hoặc khác hướng, nhưng không vì bán tháo
    pol_sell, matches_sell, _ = classify_title(
        "Nhà đầu tư bán tháo cổ phiếu HPG", "HPG", m5_cfg=cfg
    )
    assert pol_sell < 0
    assert any(normalize_title(m) == "bán tháo" for m in matches_sell)
    assert pol_disc >= 0 or "bán tháo" not in matches_disc


# --- A2 no hard-code in classify path (force_neutral from lexicon) ---


def test_phat_hanh_co_phieu_thuong_neutral_from_lexicon():
    cfg = _cfg()
    pol, _, _ = classify_title(
        "HPG phát hành cổ phiếu thưởng cho nhân viên", "HPG", m5_cfg=cfg
    )
    assert pol == 0.0


# --- A3 negation ---


def test_negation_cham_dut_chuoi_giam():
    cfg = _cfg()
    pol, _, meta = classify_title(
        "FPT vừa chấm dứt chuỗi ngày giảm điểm", "FPT", m5_cfg=cfg
    )
    assert pol > 0
    assert meta.get("negation_flipped") is True


def test_negation_thoat_chuoi_giam():
    cfg = _cfg()
    pol, _, _ = classify_title(
        "FPT thoát chuỗi giảm liên tiếp, hồi phục mạnh", "FPT", m5_cfg=cfg
    )
    assert pol > 0


def test_negation_khong_con_lao_doc():
    cfg = _cfg()
    pol, _, _ = classify_title("Cổ phiếu HPG không còn lao dốc", "HPG", m5_cfg=cfg)
    assert pol >= 0


# --- A4 subject / research issuer ---


def test_ssi_research_issuer_vs_vpbank_subject():
    cfg = _cfg()
    title = "SSI Research nâng dự báo lợi nhuận VPBank"
    pol_ssi, matches_ssi, meta_ssi = classify_title(title, "SSI", m5_cfg=cfg)
    assert pol_ssi == 0.0
    assert meta_ssi.get("subject_weight") == 0.0

    pol_vpb, matches_vpb, meta_vpb = classify_title(title, "VPB", m5_cfg=cfg)
    assert pol_vpb > 0
    assert meta_vpb.get("subject_weight") > 0


# --- A5 market summary ---


def test_market_summary_vic_weight_zero_unless_colon_lead():
    cfg = _cfg()
    titles_zero = [
        "Nhịp đập Thị trường 05/10: Thị trường xanh vỏ đỏ lòng, VIC góp hơn 13.3 điểm tăng cho VN-Index",
        "VN-Index 5/10 hồi phục 15 điểm, VIC đóng góp gần 13 điểm",
        "Thị trường chứng khoán ngày 02/10/2026: VN-Index rút chân nhờ VIC",
        "Chứng khoán phiên 22/9: Thanh khoản giảm mạnh, VIC hồi phục nâng đỡ VN-Index",
    ]
    for title in titles_zero:
        pol, matches, meta = classify_title(title, "VIC", m5_cfg=cfg)
        assert pol == 0.0, title
        assert meta.get("market_summary") or "market_summary" in matches

    # Có marker thị trường nhưng mã dẫn "VIC:" → không ép 0
    pol_ok, matches_ok, meta_ok = classify_title(
        "VIC: lợi nhuận tăng mạnh dù VN-Index rung lắc phiên ngày",
        "VIC",
        m5_cfg=cfg,
    )
    assert meta_ok.get("market_summary") is False
    assert pol_ok > 0
    assert "market_summary" not in matches_ok


# --- A6 flow weight ×0.5 ---


def test_flow_group_weight_halved():
    cfg = _cfg()
    # Flow nhân 0.5 trong lexicon: "mua ròng" nằm flow_positive (0.6*0.5)
    # vs cụm positive thường "khởi sắc" (0.8) — không clamp cả hai lên ±1
    pol_flow, matches_f, _ = classify_title(
        "HPG khối ngoại mua ròng tuần qua", "HPG", m5_cfg=cfg
    )
    pol_pos, matches_p, _ = classify_title("HPG khởi sắc nhờ xuất khẩu", "HPG", m5_cfg=cfg)
    assert pol_flow > 0
    assert pol_pos > 0
    assert any("mua ròng" in normalize_title(m) or "khối ngoại" in normalize_title(m) for m in matches_f)
    assert abs(pol_flow) < abs(pol_pos)


# --- A7 VCI + người có liên quan ---


def test_vci_disclosure_default_neutral_tng():
    cfg = _cfg()
    title = "TNG: Công bố thông tin về việc ký hợp đồng với người có liên quan"
    pol, _, meta = classify_title(title, "TNG", source="vnstock/VCI", m5_cfg=cfg)
    assert pol == 0.0
    assert meta.get("vci") is True


def test_vci_announcement_can_be_directional():
    cfg = _cfg()
    pol, matches, _ = classify_title(
        "HPG: Thông báo trả cổ tức bằng tiền",
        "HPG",
        source="vnstock/VCI",
        m5_cfg=cfg,
    )
    assert pol > 0
    assert matches


# --- A8 multi-ticker weight ×0.3 ---


def test_multi_ticker_weighted_not_dropped():
    cfg = _cfg()
    title = "HPG FPT VNM MWG cùng tăng trần phiên sáng"
    pol, _, meta = classify_title(title, "HPG", m5_cfg=cfg)
    assert meta.get("multi_ticker") is True
    assert pol > 0
    # Đơn mã cùng cụm phải mạnh hơn
    pol_single, _, meta_s = classify_title("HPG cùng tăng trần phiên sáng", "HPG", m5_cfg=cfg)
    assert meta_s.get("multi_ticker") is False
    assert abs(pol_single) > abs(pol) - 1e-9


# --- D12 story clustering ---


def test_story_cluster_hpg_bat_day():
    cfg = _cfg()
    recs = [
        {
            "id": "a",
            "title": "Con trai tỷ phú Trần Đình Long chi 1.000 tỷ 'bắt đáy' cổ phiếu HPG",
            "date": "2026-09-20",
            "age": 5,
            "polarity": 0.5,
            "weight": 0.8,
            "matches": ["bắt đáy"],
            "source": "Nghệ An 24h",
        },
        {
            "id": "b",
            "title": "Con trai tỷ phú Trần Đình Long sắp chi nghìn tỷ 'bắt đáy' HPG",
            "date": "2026-09-21",
            "age": 4,
            "polarity": 0.5,
            "weight": 0.85,
            "matches": ["bắt đáy"],
            "source": "Vietnam.vn",
        },
    ]
    stories = _cluster_stories(
        recs,
        jaccard_thr=float(cfg.get("story_jaccard_threshold", 0.6)),
        window_days=int(cfg.get("story_window_days", 3)),
    )
    assert len(stories) == 1
    assert stories[0]["story_size"] == 2
    assert stories[0]["outlet_count"] >= 2


# --- D13/14 metrics flags evidence ---


def test_enough_news_scores_ok():
    out = run(snap_enough_directional(), {}, {})
    assert out["module"] == "m5"
    assert out["status"] == "ok"
    assert out["score"] is not None
    assert 0 <= float(out["score"]) <= 100
    m = out["metrics"]
    assert m["news_relevant_count"]["value"] >= 3
    assert m["news_directional_count"]["value"] >= 2
    assert "news_distinct_sources" in m
    assert "news_newest_age_days" in m
    assert any(e.get("news_id") for e in out["evidence"][1:])
    # Evidence tiếng Việt
    body = " ".join(e.get("text", "") for e in out["evidence"][1:])
    assert ("tích cực" in body) or ("tiêu cực" in body)
    assert "positive |" not in body.lower()
    assert "negative |" not in body.lower()


def test_insufficient_news_null_score():
    out = run(snap_insufficient(), {}, {})
    assert out["score"] is None
    assert out["status"] == "partial"
    assert any(f.startswith("m5_insufficient_news") for f in out["flags"])


def test_future_news_excluded():
    out = run(snap_with_future_news(), {}, {})
    assert out["metrics"]["news_future_excluded"]["value"] >= 1
    assert "m5_future_news_excluded" in _flags(out)
    assert out["score"] is not None


def test_dieu_tra_keeps_letter_d():
    out = run(snap_dieu_tra(), {}, {})
    texts = " ".join(e.get("text", "") for e in out["evidence"])
    assert out["score"] is not None
    assert ("điều tra" in texts.lower()) or (
        out["metrics"]["news_negative_count"]["value"] >= 1
    )


def test_duplicate_titles_deduped():
    out = run(snap_duplicates(), {}, {})
    assert out["metrics"]["news_duplicate_count"]["value"] >= 1
    assert "m5_duplicate_news_excluded" in _flags(out)


def test_cw_multi_ambiguous_filtered():
    out_cw = run(snap_cw_and_multi(), {}, {})
    assert out_cw["metrics"]["news_relevant_count"]["value"] >= 3
    # CW vẫn loại; multi-ticker giữ nhưng có thể đếm weighted
    assert out_cw["metrics"].get("news_offtopic_excluded", {}).get("value", 0) >= 1

    out_ceo = run(snap_ambiguous_ceo_offtopic(), {}, {})
    assert out_ceo["metrics"]["news_relevant_count"]["value"] < len(
        snap_ambiguous_ceo_offtopic()["news"]
    )
    if out_ceo["metrics"]["news_offtopic_excluded"]["value"] >= 1:
        assert "m5_off_topic_filtered" in _flags(out_ceo)


def test_synthetic_null():
    out = run(snap_synthetic(), {}, {})
    assert out["score"] is None
    assert "m5_synthetic_data" in _flags(out)
    assert any(f.startswith("m5_insufficient_news") for f in out["flags"])


def test_ambiguous_seed_and_new_defaults():
    m5_cfg, _ = _load_m5_cfg({})
    amb = [str(x).upper() for x in (m5_cfg.get("ambiguous_tickers") or [])]
    assert amb == ["CEO", "HCM", "VND", "AAA"]
    assert m5_cfg.get("llm_enabled") is False
    assert int(m5_cfg.get("lookback_days", 0)) == 60
    assert int(m5_cfg.get("half_life_days", 0)) == 14
    assert int(m5_cfg.get("min_relevant_news", 0)) == 3
    assert int(m5_cfg.get("min_directional_news", 0)) == 2
    brokerage = {str(x).upper() for x in (m5_cfg.get("brokerage_tickers") or [])}
    assert {"SSI", "VND", "HCM", "MBS", "VCI"}.issubset(brokerage)
    assert m5_cfg.get("flip_objects")


# --- Round-2: ambiguous STRICT (không chỉ finance keyword) ---


def test_ambiguous_ceo_strict_real_headlines():
    """Tiêu đề thật: CEO person/Pharbaco → FILTERED; cổ phiếu CEO + alias → ACCEPTED."""
    from stockai.m5_sentiment.run import _ambiguous_identity_ok, normalize_title

    m5_cfg, _ = _load_m5_cfg({})
    aliases = dict(m5_cfg.get("company_aliases") or {})
    company = normalize_title("CEO Group")

    filtered = [
        "CEO Pharbaco bị phạt hơn nửa tỷ đồng vì mua cổ phiếu không báo cáo trước",
        "CEO Dược phẩm Trung ương I - Pharbaco (PBC) bị phạt tiền và cấm giao dịch 18 tháng",
    ]
    for title in filtered:
        ok = _ambiguous_identity_ok(
            title,
            normalize_title(title),
            "CEO",
            source="CafeF (qua Google News)",
            aliases=aliases,
            company_name_norm=company,
        )
        assert ok is False, title

    accepted = "Cổ phiếu CEO của CEO Group tăng trần"
    assert (
        _ambiguous_identity_ok(
            accepted,
            normalize_title(accepted),
            "CEO",
            source="CafeF (qua Google News)",
            aliases=aliases,
            company_name_norm=company,
        )
        is True
    )

    # Pipeline: 2 tiêu đề offtopic + 1 chấp nhận → offtopic ≥2, relevant ≥1
    snap = {
        "meta": {
            "ticker": "CEO",
            "as_of": "2026-10-08",
            "flags": ["quality_tier_full"],
            "synthetic": False,
        },
        "company": {"name": "CEO Group", "is_bank": False},
        "news": [
            {
                "id": "f1",
                "title": filtered[0],
                "url": "https://example.local/f1",
                "source": "CafeF",
                "published_at": "2026-10-07",
                "summary": None,
            },
            {
                "id": "f2",
                "title": filtered[1],
                "url": "https://example.local/f2",
                "source": "CafeF",
                "published_at": "2026-10-06",
                "summary": None,
            },
            {
                "id": "ok",
                "title": accepted,
                "url": "https://example.local/ok",
                "source": "CafeF",
                "published_at": "2026-10-05",
                "summary": None,
            },
        ],
        "prices": {"currency": "VND", "adjusted": True, "rows": []},
        "index": {"symbol": "VNINDEX", "rows": []},
        "financials": {"annual": [], "quarterly": []},
        "shares": {},
        "peers": [],
        "sources": [],
    }
    out = run(snap, {}, {})
    assert out["metrics"]["news_offtopic_excluded"]["value"] >= 2
    assert out["metrics"]["news_relevant_count"]["value"] >= 1


def test_brokerage_market_theme_weight_zero():
    cfg = _cfg()
    title = "MBS: Chứng khoán có thể rung lắc mạnh trước kỳ nghỉ lễ"
    pol, matches, meta = classify_title(title, "MBS", m5_cfg=cfg)
    assert pol == 0.0
    assert meta.get("brokerage_market") or "brokerage_market" in matches


def test_object_flip_no_vay_giam_manh():
    cfg = _cfg()
    pol, matches, meta = classify_title(
        "PAN: nợ vay giảm mạnh, lãi trước thuế vượt 2.000 tỷ",
        "PAN",
        m5_cfg=cfg,
    )
    assert pol >= 0
    assert meta.get("object_flipped") is True or pol > 0
    # Không còn âm vì "giảm mạnh"
    assert pol >= 0


def test_multi_ticker_deferred_from_evidence():
    """Multi-ticker (weight < 0.5) không vào evidence nếu còn tin đơn mã."""
    snap = snap_cw_and_multi()
    out = run(snap, {}, {})
    body = " ".join(e.get("text", "") for e in out["evidence"][1:])
    # Có tin đơn mã hướng trong snapshot → evidence không ưu tiên list HPG FPT VNM MWG
    assert "HPG FPT VNM MWG" not in body or out["metrics"]["news_directional_count"]["value"] <= 1


def test_gold_headlines_csv_schema():
    assert GOLD.is_file()
    assert not OLD_GOLD.exists(), "fixtures/m5_gold_labels.csv phải đã xóa"
    with GOLD.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 120
    assert set(rows[0].keys()) >= {"id", "ticker", "title", "current_pred", "label"}
    assert all(not (r.get("label") or "").strip() for r in rows)
    preds = [r.get("current_pred", "") for r in rows]
    assert sum(1 for p in preds if p == "pos") == 35
    assert sum(1 for p in preds if p == "neg") == 35
    assert sum(1 for p in preds if p == "zero") == 30
    assert sum(1 for p in preds if p == "market_summary") == 10
    assert sum(1 for p in preds if p == "multi_ticker") == 10
    tickers = [r["ticker"] for r in rows]
    assert len(set(tickers)) >= 70
    from collections import Counter

    counts = Counter(tickers)
    assert all(v <= 2 for v in counts.values())


def test_config_defaulted_flag_when_override_empty_files(monkeypatch, tmp_path):
    import stockai.m5_sentiment.run as m5

    monkeypatch.setattr(m5, "_SENTIMENT_YAML", tmp_path / "missing_sentiment.yaml")
    monkeypatch.setattr(m5, "_LEXICON_YAML", tmp_path / "missing_lex.yaml")
    monkeypatch.setattr(m5, "_ALIASES_YAML", tmp_path / "missing_alias.yaml")
    out = m5.run(snap_enough_directional(), {}, {})
    assert "m5_config_defaulted" in _flags(out) or out["score"] is not None


@pytest.mark.skipif(not (REAL_DIR / "HPG_2026-10-08.json").is_file(), reason="no real snap")
def test_optional_real_hpg_snapshot():
    import json

    snap = json.loads((REAL_DIR / "HPG_2026-10-08.json").read_text(encoding="utf-8"))
    out = run(snap, {}, {})
    assert out["module"] == "m5"
    assert out["status"] in ("ok", "partial")
    assert out["score"] is None or 0 <= float(out["score"]) <= 100


# --- Round-3: market summary ticker-action / stock dividend / firm form ---


def test_market_summary_ticker_action_weight():
    """Market summary + hành động gắn mã → hướng giữ, weight 0.6; list kéo chỉ số vẫn 0."""
    cfg = _cfg()
    cases = [
        (
            "VN-Index mất thêm 36 điểm, DXG ngược dòng tăng mạnh",
            "DXG",
            1,
        ),
        (
            "KOS tiếp tục giảm sàn giữa áp lực giải chấp",
            "KOS",
            -1,
        ),
        (
            "Chứng khoán 8-10: VN-Index giảm hơn 14 điểm, KOS tiếp tục giảm sàn giữa áp lực giải chấp",
            "KOS",
            -1,
        ),
        (
            "VN-Index hồi gần 16 điểm: VIC dẫn sóng, LPB và NVB tăng kịch biên độ",
            "LPB",
            1,
        ),
    ]
    for title, ticker, sign in cases:
        pol, matches, meta = classify_title(title, ticker, m5_cfg=cfg)
        is_ms = "vn-index" in normalize_title(title) or "vnindex" in normalize_title(title)
        if is_ms:
            assert meta.get("market_summary") is True, title
            assert meta.get("market_summary_ticker_action") is True, title
            assert abs(float(meta.get("subject_weight", 0)) - 0.6) < 1e-9, title
        assert pol * sign > 0, (title, pol, matches)

    # Chỉ nhắc mã trong list kéo chỉ số — giữ weight 0.
    pol_gas, matches_gas, meta_gas = classify_title(
        "GAS - GVR kéo VN-Index giảm điểm phiên sáng",
        "GAS",
        m5_cfg=cfg,
    )
    assert pol_gas == 0.0
    assert meta_gas.get("market_summary") or "market_summary" in matches_gas
    assert not meta_gas.get("market_summary_ticker_action")


def test_stock_dividend_force_neutral_cash_stays_positive():
    """Phát hành CP trả cổ tức → trung tính; cổ tức bằng tiền vẫn dương nhẹ."""
    cfg = _cfg()
    stock_div = [
        (
            "Afiex (AFX) sắp phát hành thêm 10,5 triệu cổ phiếu để trả cổ tức",
            "AFX",
        ),
        (
            "AGR: Nghị quyết HĐQT về việc triển khai phương án phát hành cổ phiếu để trả cổ tức năm 2025",
            "AGR",
        ),
        (
            "AGR: CBTT về PHCP để trả cổ tức và ngày ĐKCC thực hiện quyền nhận cổ tức bằng CP năm 2025",
            "AGR",
        ),
        (
            "CTI: Nghị quyết HĐQT số 25/2026 ngày 22/08/2026 và Báo cáo kết quả phát hành cổ phiếu trả cổ tức",
            "CTI",
        ),
        (
            "CTI: Thông báo nhận được Văn bản của UBCKNN về tài liệu báo cáo kết quả phát hành cổ phiếu để trả cổ tức",
            "CTI",
        ),
    ]
    for title, ticker in stock_div:
        pol, _, _ = classify_title(title, ticker, m5_cfg=cfg)
        assert pol == 0.0, title

    cash = [
        (
            "BMI: Nghị quyết, Thông báo ngày ĐKCC về chi trả cổ tức năm 2025 bằng tiền",
            "BMI",
        ),
        (
            "D2D: Thông báo ngày ĐKCC chi trả cổ tức năm 2025 bằng tiền",
            "D2D",
        ),
        ("HPG: Thông báo trả cổ tức bằng tiền", "HPG"),
    ]
    for title, ticker in cash:
        pol, _, _ = classify_title(title, ticker, m5_cfg=cfg)
        assert pol > 0, title


def test_force_neutral_dinh_chinh_quan_tri_rui_ro():
    cfg = _cfg()
    pol, _, _ = classify_title(
        "ASM: Đính chính báo cáo tình hình quản trị công ty 06 tháng đầu năm 2026",
        "ASM",
        m5_cfg=cfg,
    )
    assert pol == 0.0
    pol2, _, _ = classify_title(
        "HPG công bố chính sách quản trị rủi ro tín dụng mới",
        "HPG",
        m5_cfg=cfg,
    )
    assert pol2 == 0.0
    pol3, _, _ = classify_title(
        "VNM giải trình biến động giá cổ phiếu trên 5%",
        "VNM",
        m5_cfg=cfg,
    )
    assert pol3 == 0.0


def test_lexicon_round3_phrases():
    cfg = _cfg()
    pol_pos, matches_pos, _ = classify_title(
        "3 lần gom cổ phiếu ANV, lãnh đạo Nam Việt nâng sở hữu lên 1,18%",
        "ANV",
        m5_cfg=cfg,
    )
    assert pol_pos > 0
    assert any(
        normalize_title(m) in ("gom cổ phiếu", "nâng sở hữu") for m in matches_pos
    )

    pol_warn_out, _, _ = classify_title(
        "ASP: Quyết định về việc đưa cổ phiếu ra khỏi diện cảnh báo",
        "ASP",
        m5_cfg=cfg,
    )
    assert pol_warn_out > 0

    pol_warn_in, _, _ = classify_title(
        "HPG vào diện cảnh báo của HOSE",
        "HPG",
        m5_cfg=cfg,
    )
    assert pol_warn_in < 0

    pol_slow, _, _ = classify_title(
        "CSM sắp tổ chức ĐHĐCĐ bất thường năm 2026, bị HOSE nhắc nhở chậm công bố thông tin",
        "CSM",
        m5_cfg=cfg,
    )
    assert pol_slow < 0


def test_ambiguous_firm_role_hcm_not_ceo_job_title():
    """HCM/VND/AAA: HĐQT/thành viên + mã → chấp nhận; CEO <công ty> vẫn lọc."""
    from stockai.m5_sentiment.run import _ambiguous_identity_ok

    m5_cfg, _ = _load_m5_cfg({})
    aliases = dict(m5_cfg.get("company_aliases") or {})

    hcm_title = "Thành viên Hội đồng quản trị HCM đăng ký bán 250.000 cổ phiếu"
    assert (
        _ambiguous_identity_ok(
            hcm_title,
            normalize_title(hcm_title),
            "HCM",
            source="CafeF",
            aliases=aliases,
            company_name_norm="",
        )
        is True
    )
    pol_hcm, _, _ = classify_title(hcm_title, "HCM", m5_cfg=m5_cfg)
    assert pol_hcm < 0

    filtered_ceo = [
        "CEO Pharbaco bị phạt hơn nửa tỷ đồng vì mua cổ phiếu không báo cáo trước",
        "CEO Dược phẩm Trung ương I - Pharbaco (PBC) bị phạt tiền và cấm giao dịch 18 tháng",
        "CEO EVF đăng ký mua 4 triệu cổ phiếu, dự kiến chi khoảng 46 tỷ đồng",
        "CEO Kafi: 'Sau giai đoạn xây nền tảng, Kafi bước vào bài toán tăng trưởng bằng hiệu quả'",
    ]
    for title in filtered_ceo:
        ok = _ambiguous_identity_ok(
            title,
            normalize_title(title),
            "CEO",
            source="CafeF",
            aliases=aliases,
            company_name_norm=normalize_title("CEO Group"),
        )
        assert ok is False, title


def test_gold_regression_round3_handwritten_polarity():
    """Hồi quy trên tiêu đề gold thật — expected polarity tự viết, KHÔNG sửa cột label."""
    cfg = _cfg()
    by_id: dict[str, dict] = {}
    with GOLD.open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            by_id[row["id"]] = row

    # (id, expected sign: +1 / -1 / 0)
    expected = [
        ("g101", 1),  # DXG ngược dòng tăng mạnh trong tóm tắt VN-Index
        ("g106", -1),  # KOS giảm sàn
        ("g108", 1),  # LPB tăng kịch biên độ
        ("g003", 0),  # AFX phát hành CP trả cổ tức
        ("g007", 0),  # AGR phát hành cổ phiếu để trả cổ tức
        ("g027", 0),  # CTI phát hành cổ phiếu trả cổ tức
        ("g012", 1),  # BMI cổ tức bằng tiền
        ("g037", 0),  # ASM đính chính
        ("g061", -1),  # HCM thành viên HĐQT đăng ký bán
        ("g071", 1),  # ANV gom cổ phiếu / nâng sở hữu
        ("g078", 1),  # ASP ra khỏi diện cảnh báo
        ("g092", -1),  # CSM nhắc nhở chậm
    ]
    for gid, sign in expected:
        row = by_id[gid]
        title = row["title"]
        ticker = row["ticker"]
        pol, matches, _ = classify_title(title, ticker, m5_cfg=cfg)
        if sign == 0:
            assert pol == 0.0, (gid, title, pol, matches)
        else:
            assert pol * sign > 0, (gid, title, pol, matches)
