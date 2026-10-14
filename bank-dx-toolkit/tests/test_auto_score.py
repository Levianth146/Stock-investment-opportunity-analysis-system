"""Kiểm chứng pipeline DBI thuật toán bằng báo cáo giả, không sửa dữ liệu thật."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.replace(".", "_"), ROOT / "scripts" / name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


A = load_script("09c_auto_score.py")
S = load_script("10_score.py")


class TestAutoFeatures(unittest.TestCase):
    def test_future_and_negation_do_not_count_as_implementation(self):
        for text in ("sẽ triển khai", "dự kiến triển khai", "chưa triển khai", "không triển khai", "will deploy", "will be deployed", "not implemented"):
            with self.subTest(text=text):
                self.assertFalse(A.has_action(text))
        self.assertTrue(A.has_action("Ngân hàng đã triển khai hệ thống."))

    def test_numeric_implementation_and_plain_mention(self):
        self.assertEqual(A.level_of(A.features("Ngân hàng định hướng ngân hàng số.")), 1)
        self.assertEqual(A.level_of(A.features("Ngân hàng đã triển khai hệ thống.")), 2)
        self.assertEqual(A.level_of(A.features("Ngân hàng đã triển khai cho 50 khách hàng.")), 3)

    def test_prefilter_keeps_regex_matches(self):
        from common import compile_kw
        for keyword, text in [("RPA", "RPA"), ("chuyển đổi số", "ch uyển đổi số"),
                              ("digital", "DIGITAL"), ("digital", "dıgıtal"), ("digital", "DİGİTAL")]:
            with self.subTest(keyword=keyword, text=text):
                self.assertTrue(compile_kw(keyword).search(text))
                self.assertIn(A.search_key(keyword), A.search_key(text))

    def test_long_evidence_uses_complete_csv_reference(self):
        row = dict(criterion="K1", bank="mb", year=2025, supporting_evidence="x" * 40000)
        reference = json.loads(A.workbook_evidence(row))
        self.assertEqual(reference, dict(source_file="out/auto_scores.csv", criterion="K1", bank="mb", year=2025))

    def test_excel_display_strips_illegal_controls(self):
        self.assertEqual(A.excel_value("Bằng chứng\x07 gốc\n\t"), "Bằng chứng gốc\n\t")
        self.assertEqual(A.excel_value(3), 3)


class TestAutoPipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="bankdx_auto_")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        shutil.copytree(ROOT / "scripts", self.root / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(ROOT / "config", self.root / "config")
        self.text = self.root / "data/text"
        self.text.mkdir(parents=True)
        self.out = self.root / "out"
        self.out.mkdir()
        banks = dict(banks={"mb": {"name": "MB"}, "vcb": {"name": "VCB"}}, years=[2024, 2025], coding_years=[2024, 2025])
        (self.root / "config/banks.yaml").write_text(yaml.safe_dump(banks), encoding="utf-8")
        codes = [f"{pillar}{n}" for pillar in "KSTOCD" for n in range(1, 5)]
        keywords = {code: dict(name=code, keywords=["topic" + code]) for code in codes}
        (self.root / "config/keywords.yaml").write_text(yaml.safe_dump(keywords), encoding="utf-8")

    def add_page(self, bank, year, text, junk=0, lang="vi"):
        path = self.text / f"{bank}_{year}_bctn.jsonl"
        path.write_text(json.dumps(dict(bank=bank, year=year, doc_type="bctn", page=1,
                                       lang=lang, junk=junk, text=text), ensure_ascii=False) + "\n", encoding="utf-8")

    def run_script(self, name, *args, success=True):
        result = subprocess.run([sys.executable, "-B", name, *args], cwd=self.root / "scripts",
                                env=dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8"), capture_output=True)
        if success:
            self.assertEqual(result.returncode, 0, (result.stdout + result.stderr).decode("utf-8", "replace"))
        else:
            self.assertNotEqual(result.returncode, 0)
        return result

    def scores(self):
        return pd.read_csv(self.out / "auto_scores.csv", encoding="utf-8-sig")

    def test_missing_documents_blank_and_no_mention_zero(self):
        self.add_page("mb", 2025, "Một báo cáo có nội dung đọc được về hoạt động khác.")
        self.run_script("09c_auto_score.py")
        scores = self.scores()
        self.assertEqual(len(scores), 96)
        observed = scores[(scores.bank == "mb") & (scores.year == 2025)]
        self.assertTrue(observed.auto_score.eq(0).all())
        self.assertTrue(observed.status.eq("no_mention").all())
        self.assertTrue(observed.not_disclosed.isna().all())
        missing = scores[scores.status == "no_document"]
        self.assertEqual(len(missing), 72)
        self.assertTrue(missing.auto_score.isna().all())

    def test_unreadable_pages_are_not_scored_zero(self):
        self.add_page("mb", 2025, "topicK1 triển khai 50 khách hàng", junk=0.5)
        self.run_script("09c_auto_score.py", "--bank", "mb", "--year", "2025")
        self.assertTrue(self.scores().auto_score.isna().all())

    def test_levels_one_two_three(self):
        for phrase, level in [("topicK1 là định hướng", 1), ("topicK1 đã triển khai", 2), ("topicK1 đã triển khai cho 50 khách hàng", 3)]:
            with self.subTest(level=level):
                self.add_page("mb", 2025, phrase)
                self.run_script("09c_auto_score.py", "--bank", "mb", "--year", "2025")
                self.assertEqual(self.scores().loc[lambda df: df.criterion == "K1", "auto_score"].iloc[0], level)

    def test_year_filter_preserves_multiyear_evidence(self):
        self.add_page("mb", 2024, "topicK1 đã triển khai cho 20 khách hàng")
        self.add_page("mb", 2025, "topicK1 đã triển khai cho 50 khách hàng, được Deloitte kiểm chứng độc lập")
        self.run_script("09c_auto_score.py", "--bank", "mb")
        before = self.scores().query("year == 2025 and criterion == 'K1'").iloc[0]
        self.run_script("09c_auto_score.py", "--bank", "mb", "--year", "2025")
        scores = self.scores()
        after = scores.query("criterion == 'K1'").iloc[0]
        self.assertEqual(set(scores.bank), {"mb"})
        self.assertEqual(set(scores.year), {2025})
        self.assertEqual(after.auto_score, 4)
        self.assertEqual(before.auto_score, after.auto_score)
        support = json.loads(after.supporting_evidence)
        self.assertEqual({item["year"] for item in support}, {2024, 2025})
        self.assertTrue(all(item["page"] == 1 and item["file"].startswith("data/raw/") for item in support))

    def test_language_filter_and_reproducibility(self):
        self.add_page("mb", 2025, "topicK1 implemented for 50 customers", lang="en")
        self.run_script("09c_auto_score.py", "--only-lang", "en")
        before = (self.out / "auto_scores.csv").read_bytes()
        manifest = (self.out / "auto_scoring_manifest.json").read_bytes()
        self.run_script("09c_auto_score.py", "--only-lang", "en")
        self.assertEqual(before, (self.out / "auto_scores.csv").read_bytes())
        self.assertEqual(manifest, (self.out / "auto_scoring_manifest.json").read_bytes())
        self.run_script("09c_auto_score.py", "--only-lang", "vi")
        self.assertTrue(self.scores().auto_score.isna().all())

    def test_missing_as_zero_is_rejected(self):
        self.run_script("09c_auto_score.py", "--missing-as-zero", success=False)

    def test_draft_does_not_fall_back_to_human_scores(self):
        path = self.out / "legacy.xlsx"
        pd.DataFrame([dict(bank="mb", year=2025, criterion="K1", final=None, coder1=4, coder2=4)]).to_excel(path, index=False)
        self.assertTrue(S.load_coding(path, draft=True)["score"].isna().all())

    def test_score_uses_auto_workbook_by_default(self):
        self.add_page("mb", 2025, "topicK1 đã triển khai cho 50 khách hàng\x07 theo báo cáo")
        self.run_script("09c_auto_score.py")
        inputs = self.out / "dataset_clean"
        inputs.mkdir()
        pd.DataFrame(columns=["bank", "year", "variable", "value", "definition"]).to_csv(inputs / "dti_inputs_confirmed.csv", index=False, encoding="utf-8-sig")
        self.run_script("10_score.py", "--draft")
        summary = pd.read_csv(self.out / "score_summary_draft.csv", encoding="utf-8-sig")
        mb = summary[summary.bank == "mb"].iloc[0]
        self.assertAlmostEqual(mb.score, 3 / 24 / 4 * 100)
        self.assertEqual(mb.scoring_method, "rule_based")
        self.assertEqual(mb.rules_version, A.RULES_VERSION)
        self.assertEqual(len(mb.rules_hash), 64)
        workbook = pd.read_excel(self.out / "coding_auto.xlsx")
        self.assertNotIn("coder1", workbook)
        self.assertFalse(workbook.evidence_quote.fillna("").str.contains("\x07").any())
        self.assertTrue(self.scores().evidence_quote.fillna("").str.contains("\x07").any())


if __name__ == "__main__":
    unittest.main()
