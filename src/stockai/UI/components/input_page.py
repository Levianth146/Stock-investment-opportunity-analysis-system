from datetime import date
import streamlit as st

VN30_DEFAULT = [
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"
]

def render_sidebar():
    st.sidebar.title("HỆ THỐNG PHÂN TÍCH")
    st.sidebar.caption("VN30 Investment Opportunity Engine")
    
    ticker = st.sidebar.selectbox("1. Mã cổ phiếu (VN30):", VN30_DEFAULT, index=9) # Mặc định HPG
    profile = st.sidebar.radio(
        "2. Hồ sơ nhà đầu tư:",
        options=["long_term", "swing"],
        format_func=lambda x: "Dài hạn (Ưu tiên Cơ bản/Định giá)" if x == "long_term" else "Lướt sóng (Ưu tiên Kỹ thuật/Dòng tiền)"
    )
    as_of = st.sidebar.date_input("3. Ngày phân tích (as_of):", value=date(2026, 10, 9))
    report_type = st.sidebar.selectbox("4. Loại báo cáo PDF:", ["Tóm tắt nhanh (2-3 trang)", "Báo cáo chi tiết (10-15 trang)"])
    
    btn_run = st.sidebar.button("Bắt đầu phân tích", type="primary", use_container_width=True)
    return ticker, profile, as_of, report_type, btn_run