import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


def load_module():
    root = Path(__file__).resolve().parents[1]
    scripts_dir = root / 'scripts'
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    path = scripts_dir / '01_download.py'
    spec = importlib.util.spec_from_file_location('download_mod', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDownloadSources(unittest.TestCase):
    def test_iter_source_rows_skips_malformed_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / 'sources.csv'
            src.write_text(
                '\ufeffbank,year,doc_type,url,notes\n'
                'mb,2024,bctn,https://example.com,ok\n'
                '\n'
                '2025,bctn,https://example.org,missing bank\n',
                encoding='utf-8-sig',
            )

            mod = load_module()
            rows = list(mod.iter_source_rows(src))

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['bank'], 'mb')


if __name__ == '__main__':
    unittest.main()
