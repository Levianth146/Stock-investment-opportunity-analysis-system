"""Walking skeleton: pipeline phải chạy hết M1->M9 trên fixture, kể cả khi 1 module crash."""
import json
from pathlib import Path

from stockai.pipeline import analyze

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot_DEMO.json"


def test_e2e_with_fixture(tmp_path):
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    for profile in ("long_term", "swing"):
        up = analyze(snap, profile, str(tmp_path))
        assert up["m7"]["rating"] in ("Mua mạnh", "Mua", "Nắm giữ", "Giảm tỷ trọng", "Bán")
        assert isinstance(up["m7"]["score"], (int, float))
        assert up["m7"]["quality_gate"]["scored"] is True
        assert Path(up["m9"]["pdf_path"]).exists()


def test_e2e_insufficient_not_ranked(tmp_path):
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    flags = [f for f in snap["meta"].get("flags", []) if not str(f).startswith("quality_")]
    snap["meta"]["flags"] = flags + ["quality_tier_insufficient", "quality_illiquid"]
    up = analyze(snap, "long_term", str(tmp_path))
    assert up["m7"]["score"] is None
    assert up["m7"]["rating"] == "Không xếp hạng"
    assert up["m7"]["target"] is None
    assert up["m7"]["quality_gate"]["scored"] is False
    assert Path(up["m9"]["pdf_path"]).exists()
    assert b"NOT RANKED" in Path(up["m9"]["pdf_path"]).read_bytes()


def test_one_module_crash_does_not_kill_pipeline(tmp_path, monkeypatch):
    import stockai.pipeline as p
    monkeypatch.setattr(p, "run_m3", lambda *a, **k: 1 / 0)
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    up = analyze(snap, "long_term", str(tmp_path))
    assert up["m3"]["status"] == "error"
    assert "T_missing_used_neutral" in up["m7"]["flags"]
    assert Path(up["m9"]["pdf_path"]).exists()
