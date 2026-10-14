import streamlit as st


def render_score_dashboard(
    scores: dict[str, float | None],
    recommendation: str | None,
    target_price: float | None,
    final_score: float | None,
) -> None:
    recommendation_text = recommendation.upper() if recommendation else "CHƯA CÓ"
    target_text = f"{target_price:,.0f} VNĐ" if target_price is not None else "Chưa có"
    st.markdown(
        f"### Khuyến nghị: **{recommendation_text}** | Giá mục tiêu: **{target_text}**"
    )
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("Điểm F (Cơ bản)", _format_score(scores.get("F")))
    col2.metric("Điểm T (Kỹ thuật)", _format_score(scores.get("T")))
    col3.metric("Điểm V (Định giá)", _format_score(scores.get("V")))
    col4.metric("Điểm S (Tâm lý)", _format_score(scores.get("S")))
    risk_score = scores.get("R")
    col5.metric("Phạt R (Rủi ro)", f"-{risk_score:.1f}" if risk_score is not None else "Chưa có")
    col6.metric(
        "ĐIỂM TỔNG",
        f"{final_score:.1f}/100" if final_score is not None else "Chưa có",
        delta=recommendation,
    )


def _format_score(score: float | None) -> str:
    return f"{score:.1f}/100" if score is not None else "Chưa có"