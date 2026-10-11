import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stockai.UI.data_view import (
    annual_financial_table,
    close_history,
    market_summary,
    technical_summary,
)


def test_market_and_technical_values_follow_selected_ticker_data():
    first_stock_prices = [
        {"date": f"2026-01-{day:02}", "close": 100 + day, "volume": 1000}
        for day in range(1, 17)
    ]
    second_stock_prices = [
        {"date": row["date"], "close": row["close"] * 2, "volume": 2000}
        for row in first_stock_prices
    ]
    first_snapshot = {"prices": {"rows": first_stock_prices}}
    second_snapshot = {"prices": {"rows": second_stock_prices}}

    assert market_summary(first_snapshot)["close"] == 116
    assert market_summary(second_snapshot)["close"] == 232
    assert technical_summary(first_stock_prices)["rsi14"] == 100
    assert technical_summary(second_stock_prices)["rsi14"] == 100
    assert close_history(first_stock_prices)[-1]["close"] != close_history(second_stock_prices)[-1]["close"]


def test_annual_financial_table_uses_snapshot_values_and_omits_missing_items():
    snapshot = {
        "financials": {
            "annual": [
                {
                    "period": "2025",
                    "items": {"revenue": 2_000_000_000, "net_income": 250_000_000},
                },
                {
                    "period": "2024",
                    "items": {"revenue": 1_000_000_000, "eps": 1200},
                },
            ]
        }
    }

    assert annual_financial_table(snapshot) == [
        {"Chỉ tiêu": "Doanh thu (tỷ VNĐ)", "2025": 2.0, "2024": 1.0},
        {"Chỉ tiêu": "Lợi nhuận sau thuế (tỷ VNĐ)", "2025": 0.25},
        {"Chỉ tiêu": "EPS (VNĐ)", "2024": 1200.0},
    ]
