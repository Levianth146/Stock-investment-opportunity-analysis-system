import streamlit as st


def _claims_text(claims) -> list[str]:
    if isinstance(claims, str):
        return [claims]
    if not isinstance(claims, list):
        return []
    return [
        claim.get("text", "") if isinstance(claim, dict) else str(claim)
        for claim in claims
    ]


def render_valuation_and_debate(
    debate: dict, target_price: float | None = None
) -> None:
    col_bull, col_bear = st.columns(2)
    with col_bull:
        st.success("##### 📈 Luận điểm tăng giá (Bullish Case)")
        claims = _claims_text(debate.get("bull"))
        if claims:
            for point in claims:
                st.markdown(f"- {point}")
        else:
            st.info("Chưa có luận điểm tăng giá.")
    with col_bear:
        st.error("##### 📉 Rủi ro giảm giá (Bearish Case)")
        claims = _claims_text(debate.get("bear"))
        if claims:
            for point in claims:
                st.markdown(f"- {point}")
        else:
            st.info("Chưa có luận điểm rủi ro.")