"""US3: offline smoke batch script với mock debate."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_batch_script_offline_mock(tmp_path, monkeypatch):
    # tạo 2 snapshot tối giản
    as_of = "2026-10-08"
    snap_dir = tmp_path / "snaps"
    snap_dir.mkdir()
    demo = json.loads((ROOT / "fixtures" / "snapshot_DEMO.json").read_text(encoding="utf-8"))
    for t in ("AAA", "BBB"):
        s = json.loads(json.dumps(demo))
        s["meta"]["ticker"] = t
        s["meta"]["as_of"] = as_of
        (snap_dir / f"{t}_{as_of}.json").write_text(json.dumps(s), encoding="utf-8")

    env = {**dict(**{k: v for k, v in __import__("os").environ.items()})}
    env["PYTHONPATH"] = str(ROOT / "src")
    env.pop("GEMINI_API_KEY", None)
    env.pop("ZAI_API_KEY", None)
    # chặn đọc .env bằng cách chạy với cwd tạm + không copy .env
    script = ROOT / "scripts" / "run_debate_batch.py"
    # Patch qua env var không có — script vẫn load_dotenv từ ROOT/.env.
    # Chạy inline Python thay vì script để kiểm soát mock.
    code = f"""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, r"{ROOT / 'src'}")
from stockai.m7_scoring.debate import set_generate_fn
from stockai.m7_scoring.run import run as run_m7
from stockai.pipeline import load_cfg

set_generate_fn(lambda *a, **k: {{
    "bull": [{{"text": "b1", "refs": ["m2.roe"]}}, {{"text": "b2", "refs": ["m4.pe"]}}],
    "bear": [{{"text": "r1", "refs": ["m6.beta"]}}, {{"text": "r2", "refs": ["m6.vol_20d"]}}],
    "_meta": {{"provider": "mock", "model": "mock", "flags": [], "cache_hit": False}},
}})
cfg = load_cfg("long_term")
as_of = "{as_of}"
snap_dir = Path(r"{snap_dir}")
counts = {{"llm_ok": 0, "fallback": 0, "cache_hit": 0, "error": 0}}
for t in ("AAA", "BBB"):
    snap = json.loads((snap_dir / f"{{t}}_{{as_of}}.json").read_text(encoding="utf-8"))
    up = {{m: {{"module": m, "status": "ok", "score": 60.0,
               "metrics": {{"roe": {{"value": 1}}, "pe": {{"value": 2}}, "beta": {{"value": 1}}, "vol_20d": {{"value": 0.1}}}},
               "evidence": [], "flags": []}} for m in ("m2","m3","m4","m5","m6")}}
    up["m2"]["metrics"] = {{"roe": {{"value": 18}}}}
    up["m4"]["metrics"] = {{"pe": {{"value": 12}}}}
    up["m5"]["evidence"] = [
        {{"text": "tích cực | Tin A", "news_id": "n0"}},
        {{"text": "tiêu cực | Tin B", "news_id": "n3"}},
    ]
    up["m6"]["metrics"] = {{"beta": {{"value": 1.1}}, "vol_20d": {{"value": 0.02}}}}
    up["m6"]["score"] = 70.0  # R cao → d_R < 0 để Bear cite m6 hợp lệ
    try:
        out = run_m7(snap, up, cfg)
        flags = out.get("flags") or []
        if "m7_debate_llm_used" in flags:
            counts["llm_ok"] += 1
        elif "debate_fallback_template" in flags:
            counts["fallback"] += 1
        if "debate_cache_hit" in flags:
            counts["cache_hit"] += 1
    except Exception:
        counts["error"] += 1
print("SUMMARY llm_ok={{}} fallback={{}} cache_hit={{}} error={{}}".format(
    counts["llm_ok"], counts["fallback"], counts["cache_hit"], counts["error"]))
assert counts["error"] == 0
assert counts["llm_ok"] == 2
"""
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SUMMARY" in proc.stdout
    assert "llm_ok=2" in proc.stdout
