"""Snapshot tin dựng tay cho test M5 — offline, không mạng."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def _base(ticker: str = "HPG", as_of: str = "2026-10-08", company_name: str = "Hoa Phat") -> dict:
    return {
        "meta": {
            "ticker": ticker,
            "as_of": as_of,
            "flags": ["quality_tier_full"],
            "synthetic": False,
        },
        "company": {"name": company_name, "is_bank": False},
        "news": [],
        "prices": {"currency": "VND", "adjusted": True, "rows": []},
        "index": {"symbol": "VNINDEX", "rows": []},
        "financials": {"annual": [], "quarterly": []},
        "shares": {},
        "peers": [],
        "sources": [],
    }


def _item(
    nid: str,
    title: str,
    published_at: str,
    source: str = "CafeF (qua Google News)",
) -> dict:
    return {
        "id": nid,
        "title": title,
        "url": f"https://example.local/{nid}",
        "source": source,
        "published_at": published_at,
        "summary": None,
    }


def snap_enough_directional() -> dict:
    """Đủ ≥8 relevant + ≥4 directional trong lookback 30 (as_of=2026-10-08)."""
    s = _base("HPG", company_name="Hoa Phat Group")
    titles = [
        ("n1", "HPG lợi nhuận tăng mạnh quý III", "2026-10-07"),
        ("n2", "HPG Hòa Phát vượt kế hoạch doanh thu", "2026-10-06"),
        ("n3", "HPG mua ròng khối ngoại tuần qua", "2026-10-05"),
        ("n4", "HPG thua lỗ mảng thép xây dựng", "2026-10-04"),
        ("n5", "HPG doanh thu giảm so với cùng kỳ", "2026-10-03"),
        ("n6", "HPG khởi sắc nhờ xuất khẩu", "2026-10-02"),
        ("n7", "HPG ký hợp đồng mới với đối tác Nhật", "2026-10-01"),
        ("n8", "HPG phục hồi biên lợi nhuận", "2026-09-30"),
        ("n9", "HPG công bố thông tin cổ đông lớn", "2026-09-28"),
        ("n10", "HPG giao dịch sôi động trên HOSE", "2026-09-25"),
    ]
    s["news"] = [_item(i, t, d) for i, t, d in titles]
    return s


def snap_insufficient() -> dict:
    s = _base("HPG", company_name="Hoa Phat Group")
    s["news"] = [
        _item("a1", "HPG lợi nhuận tăng mạnh", "2026-10-07"),
        _item("a2", "HPG họp hội đồng quản trị", "2026-10-06"),
    ]
    return s


def snap_with_future_news() -> dict:
    s = snap_enough_directional()
    s["news"].append(_item("fut", "HPG lợi nhuận tăng mạnh năm 2027", "2026-10-15"))
    return s


def snap_dieu_tra() -> dict:
    """Tiêu đề có chữ đ — phải khớp lexicon 'điều tra'."""
    s = _base("HPG", company_name="Hoa Phat Group")
    base_titles = [
        ("d1", "HPG bị điều tra về cáo buộc thao túng", "2026-10-07"),
        ("d2", "HPG lợi nhuận tăng mạnh quý III", "2026-10-06"),
        ("d3", "HPG vượt kế hoạch doanh thu", "2026-10-05"),
        ("d4", "HPG mua ròng khối ngoại", "2026-10-04"),
        ("d5", "HPG thua lỗ mảng phụ trợ", "2026-10-03"),
        ("d6", "HPG khởi sắc xuất khẩu", "2026-10-02"),
        ("d7", "HPG ký hợp đồng mới", "2026-10-01"),
        ("d8", "HPG phục hồi biên lợi nhuận", "2026-09-30"),
        ("d9", "HPG công bố thông tin cổ đông", "2026-09-28"),
        ("d10", "HPG giao dịch trên HOSE", "2026-09-25"),
    ]
    s["news"] = [_item(i, t, d) for i, t, d in base_titles]
    return s


def snap_duplicates() -> dict:
    s = snap_enough_directional()
    # Trùng tiêu đề từ nguồn khác
    s["news"].append(
        _item(
            "dup",
            "HPG lợi nhuận tăng mạnh quý III",
            "2026-10-06",
            source="Vietstock (qua Google News)",
        )
    )
    return s


def snap_cw_and_multi() -> dict:
    s = _base("HPG", company_name="Hoa Phat Group")
    s["news"] = [
        _item("cw1", "Chứng quyền HPG giảm sàn phiên chiều", "2026-10-07"),
        _item("m1", "HPG FPT VNM MWG cùng tăng trần", "2026-10-06"),
        _item("ok1", "HPG lợi nhuận tăng mạnh quý III", "2026-10-05"),
        _item("ok2", "HPG vượt kế hoạch doanh thu", "2026-10-04"),
        _item("ok3", "HPG mua ròng khối ngoại", "2026-10-03"),
        _item("ok4", "HPG thua lỗ mảng phụ", "2026-10-02"),
        _item("ok5", "HPG khởi sắc xuất khẩu", "2026-10-01"),
        _item("ok6", "HPG ký hợp đồng mới", "2026-09-30"),
        _item("ok7", "HPG phục hồi biên lợi nhuận", "2026-09-28"),
        _item("ok8", "HPG công bố thông tin cổ đông", "2026-09-25"),
        _item("ok9", "HPG giao dịch trên HOSE", "2026-09-22"),
    ]
    return s


def snap_ambiguous_ceo_offtopic() -> dict:
    """CEO ambiguous STRICT: person/finance kw không đủ; cần dạng chặt / alias."""
    s = _base("CEO", company_name="CEO Group")
    s["news"] = [
        _item("c1", "CEO mới của startup fintech được bổ nhiệm", "2026-10-07"),
        _item("c2", "CEO nhận giải lãnh đạo trẻ châu Á", "2026-10-06"),
        _item(
            "c2b",
            "CEO Pharbaco bị phạt hơn nửa tỷ đồng vì mua cổ phiếu không báo cáo trước",
            "2026-10-06",
        ),
        _item("c3", "CEO Group lợi nhuận tăng mạnh quý III", "2026-10-05"),
        _item("c4", "CEO Group vượt kế hoạch doanh thu", "2026-10-04"),
        _item("c5", "CEO Group mua ròng khối ngoại", "2026-10-03"),
        _item("c6", "CEO Group thua lỗ mảng BĐS", "2026-10-02"),
        _item("c7", "CEO Group khởi sắc nhờ dự án mới", "2026-10-01"),
        _item("c8", "CEO Group ký hợp đồng mới", "2026-09-30"),
        _item("c9", "CEO Group phục hồi biên lợi nhuận", "2026-09-28"),
        _item("c10", "CEO Group công bố thông tin cổ đông", "2026-09-25"),
        _item("c11", "Cổ phiếu CEO của CEO Group tăng trần", "2026-09-22"),
        _item("c12", "Tập đoàn CEO trúng thầu dự án hạ tầng", "2026-09-20"),
    ]
    return s


def snap_synthetic() -> dict:
    s = snap_enough_directional()
    s["meta"]["synthetic"] = True
    return s


def clone(snap: dict) -> dict[str, Any]:
    return deepcopy(snap)
