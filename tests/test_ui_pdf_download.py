from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_ui_waits_for_analysis_before_offering_pdf_download():
    app_file = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "stockai"
        / "UI"
        / "app.py"
    )
    app = AppTest.from_file(str(app_file)).run(timeout=30)

    assert not app.exception
    assert not list(app.get("download_button"))
    assert any(button.label == "Bắt đầu phân tích" for button in app.button)
