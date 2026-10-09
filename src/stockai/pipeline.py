"""Điều phối M1->M9. CHỈ N1 SỬA. Mỗi module bị bọc try/except: lỗi 1 module -> status=error, pipeline chạy tiếp."""
from __future__ import annotations

import json
import traceback
from pathlib import Path

import yaml

from stockai.contracts.schemas import validate
from stockai.m2_fundamental.run import run as run_m2
from stockai.m3_technical.run import run as run_m3
from stockai.m4_valuation.run import run as run_m4
from stockai.m5_sentiment.run import run as run_m5
from stockai.m6_risk.run import run as run_m6
from stockai.m7_scoring.run import run as run_m7
from stockai.m8_validate.run import run as run_m8
from stockai.m9_report.run import run as run_m9

ROOT = Path(__file__).resolve().parents[2]


def load_cfg(profile: str) -> dict:
    cfg = {}
    for f in ("scoring", "data_sources", "llm"):
        cfg.update(yaml.safe_load((ROOT / "config" / f"{f}.yaml").read_text(encoding="utf-8")))
    cfg["profile"] = profile
    return cfg


def _safe(name: str, fn, snapshot, upstream, cfg, schema: str | None):
    try:
        out = fn(snapshot, upstream, cfg)
        if schema:
            errs = validate(out, schema)
            if errs:
                return {"module": name, "status": "error", "score": None, "metrics": {}, "evidence": [],
                        "flags": [f"{name}_invalid_output"], "error": "; ".join(errs[:3])}
        return out
    except Exception as e:  # noqa: BLE001
        return {"module": name, "status": "error", "score": None, "metrics": {}, "evidence": [],
                "flags": [f"{name}_crashed"], "error": f"{e}\n{traceback.format_exc(limit=2)}"}


def analyze(snapshot: dict, profile: str = "long_term", out_dir: str = "reports") -> dict:
    cfg = load_cfg(profile); cfg["out_dir"] = out_dir
    up: dict = {}
    for name, fn in (("m2", run_m2), ("m3", run_m3), ("m4", run_m4), ("m5", run_m5), ("m6", run_m6)):
        up[name] = _safe(name, fn, snapshot, up, cfg, "module_out")   # M4 có thể đọc up["m2"]
    up["m7"] = _safe("m7", run_m7, snapshot, up, cfg, "result")
    up["m8"] = _safe("m8", run_m8, snapshot, up, cfg, "validation")
    up["m9"] = _safe("m9", run_m9, snapshot, up, cfg, None)
    d = Path(out_dir); d.mkdir(parents=True, exist_ok=True)
    stem = f"{snapshot['meta']['ticker']}_{snapshot['meta']['as_of']}_{profile}"
    (d / f"{stem}_result.json").write_text(json.dumps(up, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return up


def status_table(up: dict) -> str:
    return "\n".join(f"  {k:>3}  {o.get('status', 'ok'):<8} {o.get('error', '')[:60]}" for k, o in up.items())
