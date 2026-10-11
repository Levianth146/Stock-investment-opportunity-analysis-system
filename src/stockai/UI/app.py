import sys
import tempfile
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from components.download_ui import render_download_ui
from components.input_page import render_sidebar
from components.score_dashboard import render_score_dashboard
from components.valuation_view import render_valuation_and_debate
from stockai.UI.data_view import (
    annual_financial_table,
    close_history,
    market_summary,
    technical_summary,
)
from stockai.m1_data.fetch import build_snapshot
from stockai.m8_validate.validator import validate_quantitative_data
from stockai.m9_report.report_generator import generate_pdf_report
from stockai.pipeline import analyze, load_cfg

st.set_page_config(page_title="Hệ thống phân tích cổ phiếu VN30", layout="wide")

ticker, profile, as_of, report_type, btn_run = render_sidebar()
analysis_key = (ticker, profile, as_of.isoformat())

if btn_run:
    try:
        with st.status("Đang lấy dữ liệu và phân tích...", expanded=True) as status:
            cfg = load_cfg(profile)
            st.write(f"M1: Đang lấy dữ liệu {ticker} đến {as_of.isoformat()}...")
            snapshot = build_snapshot(ticker, as_of.isoformat(), cfg)

            if not snapshot["prices"]["rows"]:
                details = "; ".join(snapshot["meta"]["flags"][:5])
                raise RuntimeError(
                    f"Không lấy được dữ liệu giá cho {ticker}. "
                    f"Kiểm tra kết nối/nguồn dữ liệu. {details}"
                )

            st.write("M2-M8: Đang chạy các module phân tích...")
            with tempfile.TemporaryDirectory() as output_dir:
                upstream = analyze(snapshot, profile, output_dir)

            st.session_state["stock_analysis"] = {
                "key": analysis_key,
                "snapshot": snapshot,
                "upstream": upstream,
            }
            status.update(label="Đã phân tích dữ liệu mã đã chọn.", state="complete")
    except Exception as error:
        st.session_state["stock_analysis"] = {
            "key": analysis_key,
            "error": str(error),
        }

stored_analysis = st.session_state.get("stock_analysis")
if stored_analysis and stored_analysis.get("key") != analysis_key:
    stored_analysis = None

st.title(f"BÁO CÁO PHÂN TÍCH: :blue[{ticker}]")
st.caption(f"Hồ sơ: {profile.upper()} | Ngày chốt số liệu (as_of): {as_of}")

if stored_analysis is None:
    st.info("Chọn mã, hồ sơ và ngày phân tích, sau đó nhấn **Bắt đầu phân tích** để lấy dữ liệu riêng cho mã đó.")
elif "error" in stored_analysis:
    st.error(f"Không thể phân tích {ticker}: {stored_analysis['error']}")
else:
    snapshot = stored_analysis["snapshot"]
    upstream = stored_analysis["upstream"]
    result = upstream["m7"]

    data_status = snapshot["meta"]["data_status"]
    st.caption(
        "Tình trạng dữ liệu: "
        + " | ".join(f"{name}: {state}" for name, state in data_status.items())
    )
    if any(state != "ok" for state in data_status.values()):
        st.warning(
            "Một số nhóm dữ liệu thiếu hoặc chưa đầy đủ. "
            "Xem cờ dữ liệu và trạng thái module trước khi sử dụng kết quả."
        )
    if snapshot["meta"].get("flags"):
        with st.expander("Chi tiết chất lượng dữ liệu"):
            for flag in snapshot["meta"]["flags"]:
                st.write(f"- {flag}")

    prices = snapshot["prices"]["rows"]
    summary = market_summary(snapshot)
    if summary:
        price_col, change_col, volume_col = st.columns(3)
        price_col.metric(
            f"Giá đóng cửa ({summary['date']})",
            f"{summary['close']:,.0f} VNĐ",
        )
        change_col.metric(
            "Thay đổi phiên trước",
            f"{summary['change_pct']:+.2f}%" if summary["change_pct"] is not None else "Chưa có",
        )
        volume_col.metric(
            "Khối lượng",
            f"{summary['volume']:,.0f}" if summary["volume"] is not None else "Chưa có",
        )
        st.line_chart(close_history(prices), x="date", y="close")

    modules = {name: upstream.get(name, {}) for name in ("m2", "m3", "m4", "m5", "m6")}
    module_status = {
        name: module.get("status", "missing")
        for name, module in modules.items()
    }
    scores = {
        key: (
            modules[module_name].get("score")
            if module_status[module_name] in {"ok", "partial"}
            and isinstance(modules[module_name].get("score"), (int, float))
            else None
        )
        for key, module_name in (
            ("F", "m2"),
            ("T", "m3"),
            ("V", "m4"),
            ("S", "m5"),
            ("R", "m6"),
        )
    }
    all_scores_ready = all(value is not None for value in scores.values())
    target = modules["m4"].get("target") if module_status["m4"] in {"ok", "partial"} else None
    target_price = target.get("base") if isinstance(target, dict) else None
    recommendation = result.get("rating") if all_scores_ready else None
    final_score = result.get("score") if all_scores_ready else None

    st.subheader("Điểm phân tích")
    partial_modules = [
        name for name, module in modules.items()
        if module_status[name] == "partial"
    ]
    if not all_scores_ready or partial_modules:
        st.warning(
            "Một số chỉ tiêu phân tích còn thiếu hoặc chỉ có dữ liệu một phần. "
            "Điểm từng module được tính từ chỉ tiêu thực có; không dùng điểm mẫu."
            + (f" Module chưa đủ dữ liệu: {', '.join(name.upper() for name in partial_modules)}." if partial_modules else "")
        )
    render_score_dashboard(scores, recommendation, target_price, final_score)

    st.subheader("Trạng thái module")
    st.dataframe(
        [
            {
                "Module": name.upper(),
                "Trạng thái": module_status[name],
                "Điểm": modules[name].get("score")
                if module_status[name] in {"ok", "partial"}
                and isinstance(modules[name].get("score"), (int, float))
                else None,
                "Ghi chú": "; ".join(modules[name].get("flags", [])),
            }
            for name in modules
        ] + [
            {
                "Module": name.upper(),
                "Trạng thái": upstream.get(name, {}).get("status", "missing"),
                "Điểm": upstream.get(name, {}).get("score"),
                "Ghi chú": "; ".join(upstream.get(name, {}).get("flags", [])),
            }
            for name in ("m7", "m8")
        ],
        hide_index=True,
        use_container_width=True,
    )
    metric_rows = [
        {
            "Module": name.upper(),
            "Chỉ tiêu": metric_name,
            "Giá trị": metric.get("value") if metric.get("value") is not None else "Chưa có",
            "Đơn vị": metric.get("unit", ""),
            "Ghi chú": metric.get("note", ""),
        }
        for name, module in modules.items()
        for metric_name, metric in module.get("metrics", {}).items()
    ]
    if metric_rows:
        with st.expander("Chỉ tiêu đã tính trong các module"):
            st.dataframe(metric_rows, hide_index=True, use_container_width=True)

    st.divider()
    tab_analysis, tab_financials, tab_technical = st.tabs(
        ["Định giá & Bull/Bear", "Báo cáo tài chính", "Kỹ thuật"]
    )
    with tab_analysis:
        debate = {
            "bull": result.get("bull", []),
            "bear": result.get("bear", []),
        }
        render_valuation_and_debate(debate, target_price)
        if target_price is None:
            st.info("Module M4 chưa cung cấp giá mục tiêu cho mã này.")
    with tab_financials:
        financial_rows = annual_financial_table(snapshot)
        if financial_rows:
            st.dataframe(financial_rows, hide_index=True, use_container_width=True)
        else:
            st.info("Không có dữ liệu báo cáo tài chính năm cho mã/ngày đã chọn.")
    with tab_technical:
        indicators = technical_summary(prices)
        if indicators:
            cols = st.columns(4)
            cols[0].metric("MA20", f"{indicators['ma20']:,.0f} VNĐ" if indicators["ma20"] is not None else "Chưa đủ dữ liệu")
            cols[1].metric("MA50", f"{indicators['ma50']:,.0f} VNĐ" if indicators["ma50"] is not None else "Chưa đủ dữ liệu")
            cols[2].metric("RSI 14", f"{indicators['rsi14']:.1f}" if indicators["rsi14"] is not None else "Chưa đủ dữ liệu")
            cols[3].metric("Số phiên", f"{indicators['sessions']:,}")
        else:
            st.info("Không có đủ dữ liệu giá để tính chỉ báo kỹ thuật.")

    m8_result = upstream.get("m8", {})
    pdf_ready = (
        m8_result.get("status") == "pass"
        and all_scores_ready
        and target_price is not None
    )
    pdf_data = None
    if pdf_ready:
        report_payload = {
            "ticker": ticker,
            "as_of": as_of.isoformat(),
            "profile": profile,
            "scores": {**scores, "final": final_score},
            "recommendation": recommendation,
            "target_price": target_price,
            "debate": {
                "bull": "\n".join(
                    claim.get("text", "") for claim in result.get("bull", [])
                ),
                "bear": "\n".join(
                    claim.get("text", "") for claim in result.get("bear", [])
                ),
            },
            "provenance": [
                {
                    "metric": source["name"],
                    "value": snapshot["meta"]["ticker"],
                    "source": source["url"],
                    "published_at": source["fetched_at"],
                    "method": source.get("note", ""),
                }
                for source in snapshot["sources"]
            ],
        }
        validation = validate_quantitative_data(
            {"ticker": ticker},
            report_payload,
        )
        if validation["is_passed"]:
            with tempfile.TemporaryDirectory() as temp_dir:
                pdf_path = Path(temp_dir) / f"{ticker}_report.pdf"
                if generate_pdf_report(report_payload, str(pdf_path), validation):
                    pdf_data = pdf_path.read_bytes()

    render_download_ui(
        pdf_ready and pdf_data is not None,
        ticker,
        pdf_data,
    )
    if m8_result.get("issues"):
        with st.expander("Cảnh báo kiểm chứng M8"):
            for issue in m8_result["issues"]:
                st.write(f"- {issue.get('message', issue)}")

st.sidebar.caption("Nguồn dữ liệu được lấy khi nhấn nút phân tích; một số module có thể chưa hoàn tất.")
