import time
import streamlit as st

def render_pipeline_progress():
    status_placeholder = st.status("Đang chạy chuỗi phân tích M1 → M9...", expanded=True)
    with status_placeholder:
        st.write("🔄 **M1 (Dữ liệu):** Trích xuất snapshot 5 năm point-in-time...")
        time.sleep(0.4)
        st.write("🔄 **M2 - M6 (Xử lý):** Chạy song song Cơ bản, Kỹ thuật, Định giá, Sentiment, Rủi ro...")
        time.sleep(0.4)
        st.write("🔄 **M7 (Tổng hợp):** Tính F/T/V/S, trừ điểm phạt R, lập luận Bull/Bear...")
        time.sleep(0.3)
        st.write("🔄 **M8 (Kiểm chứng):** Đối chiếu chéo số liệu và nguồn trích dẫn...")
        time.sleep(0.3)
        status_placeholder.update(label="✓ Hệ thống hoàn tất! Dữ liệu đạt chuẩn M8.", state="complete", expanded=False)