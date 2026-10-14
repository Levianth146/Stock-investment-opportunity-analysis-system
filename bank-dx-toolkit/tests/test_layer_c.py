"""Kiểm thử công thức, dữ liệu thiếu và đồng hạng lớp C trên số tính tay."""
import importlib.util
from pathlib import Path
import sys
import unittest
import tempfile

import pandas as pd

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("layer_c", SCRIPTS / "19_validate_layer_c.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def fixture():
    rows = []
    for year, variable, value in [(2023, "equity", 100), (2024, "equity", 200),
                                  (2023, "total_assets", 1000), (2024, "total_assets", 2000),
                                  (2024, "net_profit_parent", 30),
                                  (2024, "net_profit_consolidated", 45),
                                  (2024, "net_profit", 999), (2024, "opex", -40),
                                  (2024, "op_profit_before_provision", 60),
                                  (2024, "net_interest_income", 70),
                                  (2024, "net_fee_income", 5),
                                  (2024, "casa_deposits", 20), (2024, "customer_deposits", 80)]:
        rows.append(dict(bank="a", year=year, variable=variable, value=value,
                         unit="VND million", source_file="sample.pdf", page=2,
                         confirmed_by="nam", definition="consolidated" if variable in
                         ("total_assets", "net_profit_consolidated") else "parent", note=""))
    return pd.DataFrame(rows)


class LayerCTest(unittest.TestCase):
    def test_formulas_and_evidence(self):
        result = C.calculate(fixture(), [("a", 2024)]).set_index("indicator")
        for indicator, expected in dict(roe=20, roa=3, casa=25, non_interest_share=30).items():
            self.assertAlmostEqual(result.loc[indicator, "value"], expected)
            self.assertEqual(result.loc[indicator, "status"], "available")
        self.assertIn('"year": 2023', result.loc["roe", "evidence"])
        self.assertIn('"source_file": "sample.pdf"', result.loc["roe", "evidence"])

    def test_missing_previous_and_unconfirmed(self):
        data = fixture()
        data = data[data.year != 2023].copy()
        data.loc[data.variable == "casa_deposits", "confirmed_by"] = "range-checked"
        result = C.calculate(data, [("a", 2024)]).set_index("indicator")
        self.assertTrue(result.loc[["roe", "roa", "casa"], "value"].isna().all())
        self.assertTrue(result.loc[["roe", "roa", "casa"], "status"].eq("missing").all())

    def test_scope_and_notes_excluded_from_clean_sample(self):
        data = fixture()
        data.loc[data.variable == "net_profit_parent", "definition"] = ""
        data.loc[data.variable == "casa_deposits", "note"] = "CẦN KIỂM: BIEN_DONG"
        result = C.calculate(data, [("a", 2024)])
        scores = pd.DataFrame([dict(bank="a", year=2024, score=50, dbi_score=60)])
        _, corr = C.correlations(result, scores)
        clean = corr[(corr['sample'] == "without_review_flags") & corr.indicator.isin(["roe", "casa"])]
        self.assertTrue(clean.n_banks.eq(0).all())
        self.assertEqual(result[result.indicator == "roe"].status.iloc[0], "needs_review")
        self.assertTrue(result[result.indicator == "roe"].value.isna().all())

    def test_resolved_requires_evidence_and_retains_history(self):
        data = fixture()
        mask = data.variable == "casa_deposits"
        data.loc[mask, "note"] = "CHƯA đối chiếu PDF | Đã đối chiếu PDF. Giữ số."
        data.loc[mask, "review_status"] = "resolved"
        result = C.calculate(data, [("a", 2024)]).set_index("indicator")
        self.assertEqual(result.loc["casa", "status"], "needs_review")
        for col, value in dict(reviewed_by="nam", review_date="2026-10-13",
                               review_evidence="Đối chiếu sample.pdf trang 2: CASA=20, đúng cột năm").items():
            data.loc[mask, col] = value
        result = C.calculate(data, [("a", 2024)]).set_index("indicator")
        self.assertEqual(result.loc["casa", "status"], "available")
        self.assertIn("CHƯA đối chiếu PDF", result.loc["casa", "evidence"])
        data.loc[mask, "unit"] = "VND billion"
        result = C.calculate(data, [("a", 2024)]).set_index("indicator")
        self.assertEqual(result.loc["casa", "status"], "needs_review")
        data.loc[mask, "review_date"] = "13/10/2026"
        self.assertTrue(C.review_warnings(data[mask].iloc[0]))

    def test_pending_and_unknown_status(self):
        self.assertTrue(C.review_warnings(dict(review_status="pending", note="")))
        self.assertTrue(C.review_warnings(dict(review_status="done", note="")))
        self.assertEqual(C.review_warnings(dict(note="")), [])

    def test_wrong_roa_scope_and_no_legacy_fallback(self):
        data = fixture()
        data.loc[data.variable == "total_assets", "definition"] = "parent"
        result = C.calculate(data, [("a", 2024)]).set_index("indicator")
        self.assertTrue(pd.isna(result.loc["roa", "value"]))
        data = fixture()
        data = data[~data.variable.isin(["net_profit_parent", "net_profit_consolidated"])]
        result = C.calculate(data, [("a", 2024)]).set_index("indicator")
        self.assertTrue(result.loc[["roe", "roa"], "value"].isna().all())
        self.assertTrue(result.loc[["roe", "roa"], "status"].eq("missing").all())

    def test_resolved_cannot_bypass_confirmation(self):
        data = fixture()
        mask = data.variable == "net_profit_parent"
        for col, value in dict(review_status="resolved", reviewed_by="nam", review_date="2026-10-13",
                               review_evidence="Đã kiểm", confirmed_by="range-checked").items():
            data.loc[mask, col] = value
        result = C.calculate(data, [("a", 2024)]).set_index("indicator")
        self.assertTrue(pd.isna(result.loc["roe", "value"]))

    def test_queue_prioritizes_previous_year_for_latest_target(self):
        data = fixture()
        data.loc[data.variable == "equity", "note"] = "CẦN KIỂM"
        queue = C.review_queue(data, [("a", 2023), ("a", 2024)])
        self.assertEqual(queue[(queue.year == 2023) & (queue.variable == "equity")].priority.iloc[0], 1)
        self.assertEqual(queue[(queue.year == 2022) & (queue.variable == "equity")].priority.iloc[0], 2)

    def test_prepare_preserves_data_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "inputs.csv"
            data = fixture()
            data = data[~data.variable.isin(["net_profit_parent", "net_profit_consolidated"])]
            data.to_csv(path, index=False, encoding="utf-8-sig")
            original_bytes = path.read_bytes()
            prepared = C.prepare_inputs(path)
            new = prepared[prepared.variable.isin(["net_profit_parent", "net_profit_consolidated"])]
            self.assertTrue(new.value.fillna("").eq("").all())
            self.assertTrue(new.confirmed_by.fillna("").eq("").all())
            self.assertEqual(prepared[prepared.variable == "net_profit"].value.iloc[0], 999)
            backups = list(Path(temp).glob("inputs.before_layer_c_*.csv"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), original_bytes)
            first = path.read_bytes()
            C.prepare_inputs(path)
            self.assertEqual(path.read_bytes(), first)

    def test_ties_missing_and_constant(self):
        pairs = pd.DataFrame(dict(x=[1, 1, 2, None], y=[10, 20, 30, 99]))
        rho, _ = C.spearman_pairs(pairs)
        self.assertAlmostEqual(rho, 3 ** 0.5 / 2)
        self.assertEqual(C.spearman_pairs(pairs.iloc[:2])[1], "insufficient_pairs")
        pairs.x = 1
        self.assertEqual(C.spearman_pairs(pairs)[1], "constant_series")

    def test_zero_denominator(self):
        data = fixture()
        data.loc[data.variable == "customer_deposits", "value"] = 0
        result = C.calculate(data, [("a", 2024)]).set_index("indicator")
        self.assertTrue(pd.isna(result.loc["casa", "value"]))


if __name__ == "__main__":
    unittest.main()
