import streamlit as st


def render_download_ui(m8_passed: bool, ticker: str, pdf_data: bytes | None = None) -> None:
    st.markdown("#### Tùy chọn & Xuất Báo Cáo")

    # 1. Các tùy chọn cấu hình báo cáo
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        report_len = st.radio(
            "Độ dài báo cáo:",
            ["Bản tóm tắt (2-3 trang)", "Bản chi tiết đầy đủ (10-15 trang)"],
            horizontal=True
        )
    with col_opt2:
        include_sections = st.multiselect(
            "Các phần muốn đính kèm:",
            ["Định giá & Bull/Bear", "BCTC 5 năm", "Chỉ báo kỹ thuật", "Tin tức & Sentiment", "Phụ lục Provenance"],
            default=["Định giá & Bull/Bear", "BCTC 5 năm", "Phụ lục Provenance"]
        )

    # 2. Xử lý nút tải theo kết quả M8
    if m8_passed and pdf_data is not None:
        st.success("✓ Kiểm định M8 ĐẠT: Số liệu đối chiếu khớp với snapshot gốc.")
        st.download_button(
            label=f"⬇️ TẢI BÁO CÁO PDF ({ticker})",
            data=pdf_data,
            file_name=f"Bao_cao_phan_tich_{ticker}.pdf",
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    elif m8_passed:
        st.error("Không thể tạo file PDF. Vui lòng thử lại hoặc kiểm tra lỗi tạo báo cáo.")
        st.button("TẢI BÁO CÁO (PDF CHƯA SẴN SÀNG)", disabled=True, use_container_width=True)
    else:
        st.info(
            "Chưa thể tải báo cáo: cần dữ liệu đầy đủ, các module phân tích hoàn tất "
            "và kiểm chứng M8 đạt."
        )
        st.button("TẢI BÁO CÁO (CHƯA SẴN SÀNG)", disabled=True, use_container_width=True)