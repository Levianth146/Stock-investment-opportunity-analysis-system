import sys
from pathlib import Path

from pypdf import PdfReader

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stockai.m8_validate.validator import validate_quantitative_data
from stockai.m9_report.report_generator import generate_pdf_report

def test_m8_and_m9_flow():
    mock_snap = {"ticker": "HPG"}
    mock_result = {
        "ticker": "HPG",
        "as_of": "2026-10-09",
        "scores": {"F": 85, "T": 72, "V": 90, "S": 65, "R": 15, "final": 78},
        "target_price": 34500,
        "recommendation": "Hấp dẫn",
        "debate": {
            "bull": "Tăng trưởng công suất, biên lợi nhuận cải thiện tích cực.",
            "bear": "Biến động chi phí nguyên vật liệu quặng sắt toàn cầu."
        }
    }

    # Test M8 Validation
    val_report = validate_quantitative_data(mock_snap, mock_result)
    assert val_report["is_passed"] is True

    # Test M9 PDF Generator
    output_pdf = "tests/test_output.pdf"
    success = generate_pdf_report(mock_result, output_pdf, val_report)
    assert success is True
    reader = PdfReader(output_pdf)
    extracted_text = " ".join(page.extract_text() or "" for page in reader.pages)
    font_names = {
        font.get_object().get("/BaseFont")
        for page in reader.pages
        for font in page.get("/Resources").get("/Font").values()
    }
    assert "Tăng trưởng" in extracted_text
    assert any("DejaVuSans" in str(font_name) for font_name in font_names)
    print("\nM8 validation passed and tests/test_output.pdf was generated.")

if __name__ == "__main__":
    test_m8_and_m9_flow()