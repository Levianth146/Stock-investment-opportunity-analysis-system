#!/usr/bin/env python3
"""Batch debate M7 trên nhiều ticker — báo cáo llm_ok / fallback / cache_hit / error.

Upstream thật: chạy M2–M6 qua pipeline._safe (giống analyze). Không stub.
Không crash cả batch khi một mã lỗi. Không in API key / prompt chứa khóa.
"""
from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# Windows console: in UTF-8 để in tiếng Việt (rating / luận điểm)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

from stockai.llm.generate import (  # noqa: E402
    format_error_reason_table,
    load_dotenv_keys,
    load_llm_cfg,
    reset_circuit_state,
)
from stockai.m2_fundamental.run import run as run_m2  # noqa: E402
from stockai.m3_technical.run import run as run_m3  # noqa: E402
from stockai.m4_valuation.run import run as run_m4  # noqa: E402
from stockai.m5_sentiment.run import run as run_m5  # noqa: E402
from stockai.m6_risk.run import run as run_m6  # noqa: E402
from stockai.m7_scoring.debate import set_generate_fn  # noqa: E402
from stockai.m7_scoring.run import run as run_m7  # noqa: E402
from stockai.pipeline import _safe, load_cfg  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Batch M7 debate (Bull/Bear)")
    p.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    p.add_argument(
        "--snapshots-dir",
        default=str(ROOT / "data" / "snapshots_ext"),
        help="Thư mục snapshot JSON (mặc định có news)",
    )
    p.add_argument("--tickers", default="", help="CSV ticker, vd VCB,FPT,HPG")
    p.add_argument("--limit", type=int, default=10, help="Giới hạn số mã nếu không --tickers")
    p.add_argument("--config", default=str(ROOT / "config" / "llm.yaml"))
    p.add_argument("--profile", default="long_term")
    p.add_argument("--print-debate", action="store_true", help="In đầy đủ bull/bear")
    p.add_argument(
        "--template-only",
        action="store_true",
        help="Bỏ qua LLM (không đọc lại .env key) — chỉ template fallback",
    )
    return p.parse_args()


def build_upstream_m2_m6(snapshot: dict, cfg: dict) -> dict:
    """Chạy M2–M6 thật qua ``_safe`` (cùng kiểu ``pipeline.analyze``)."""
    up: dict = {}
    for name, fn in (
        ("m2", run_m2),
        ("m3", run_m3),
        ("m4", run_m4),
        ("m5", run_m5),
        ("m6", run_m6),
    ):
        up[name] = _safe(name, fn, snapshot, up, cfg, "module_out")
    return up


def _load_snapshot(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _source_label(flags: list[str]) -> str:
    """Nhãn rõ: LLM vs fallback (không trình bày fallback như LLM)."""
    if "debate_fallback_template" in flags or "m7_debate_fallback_used" in flags:
        return "FALLBACK_TEMPLATE"
    if "m7_debate_llm_used" in flags:
        return "LLM"
    if "debate_cache_hit" in flags:
        return "LLM_CACHE"
    return "UNKNOWN"


def main() -> int:
    args = _parse_args()
    if args.template_only:
        # Không nạp key từ .env; chặn load lại trong debate/generate
        import os

        os.environ.pop("GEMINI_API_KEY", None)
        os.environ.pop("ZAI_API_KEY", None)
        import stockai.llm.generate as _gen
        import stockai.m7_scoring.debate as _deb

        _gen.load_dotenv_keys = lambda *a, **k: None  # type: ignore[assignment]
        _deb.load_dotenv_keys = lambda *a, **k: None  # type: ignore[assignment]
    else:
        load_dotenv_keys()
    llm_cfg = load_llm_cfg(args.config)
    snap_dir = Path(args.snapshots_dir)
    if args.tickers.strip():
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    else:
        files = sorted(snap_dir.glob(f"*_{args.as_of}.json"))
        tickers = []
        for f in files:
            if f.name.startswith("_"):
                continue
            tickers.append(f.name.split("_")[0])
            if len(tickers) >= args.limit:
                break

    scoring_cfg = load_cfg(args.profile)
    # gắn llm config (pricing / display_metrics / debate)
    scoring_cfg = {**scoring_cfg, "llm": llm_cfg}
    if isinstance(llm_cfg.get("debate"), dict) and "debate" not in scoring_cfg:
        scoring_cfg["debate"] = llm_cfg["debate"]

    reset_circuit_state()
    counts = {"llm_ok": 0, "fallback": 0, "cache_hit": 0, "error": 0}
    total_cost = 0.0
    print(f"as_of={args.as_of} tickers={len(tickers)} dir={snap_dir}")

    for ticker in tickers:
        path = snap_dir / f"{ticker}_{args.as_of}.json"
        try:
            snap = _load_snapshot(path)
            if snap is None:
                print(f"{ticker}: error missing_or_bad_json")
                counts["error"] += 1
                continue
            up = build_upstream_m2_m6(snap, scoring_cfg)
            # Dùng run_m7 để có score/rating + flags; debate nằm trong đó
            result = run_m7(snap, up, scoring_cfg)
            flags = result.get("flags") or []
            bull, bear = result.get("bull") or [], result.get("bear") or []
            cost = float(scoring_cfg.get("_debate_cost_usd") or 0.0)
            # flags có thể chứa debate_cost_usd:...
            for f in flags:
                if isinstance(f, str) and f.startswith("debate_cost_usd:"):
                    try:
                        cost = float(f.split(":", 1)[1])
                    except ValueError:
                        pass
            total_cost += cost
            src = _source_label(flags)
            if "debate_cache_hit" in flags:
                counts["cache_hit"] += 1
            if src.startswith("FALLBACK"):
                counts["fallback"] += 1
                status = "fallback"
            elif src.startswith("LLM"):
                counts["llm_ok"] += 1
                status = "llm_ok"
            else:
                if result.get("quality_gate", {}).get("scored") is False:
                    status = "quality_gate"
                else:
                    status = "ok_unknown"
                    counts["llm_ok"] += 1
            print(
                f"{ticker}: {status} source={src} bull={len(bull)} bear={len(bear)} "
                f"score={result.get('score')} rating={result.get('rating')} "
                f"cost_usd≈{cost:.6f}"
            )
            if args.print_debate:
                print(f"  --- {src} BULL ---")
                for i, it in enumerate(bull):
                    print(f"    [{i}] {it.get('text')} refs={it.get('refs')}")
                print(f"  --- {src} BEAR ---")
                for i, it in enumerate(bear):
                    print(f"    [{i}] {it.get('text')} refs={it.get('refs')}")
        except Exception as e:
            counts["error"] += 1
            print(f"{ticker}: error {type(e).__name__}: {e}")
            traceback.print_exc(limit=1)

    print(
        "SUMMARY "
        f"llm_ok={counts['llm_ok']} fallback={counts['fallback']} "
        f"cache_hit={counts['cache_hit']} error={counts['error']} "
        f"est_cost_usd={total_cost:.6f}"
    )
    print(format_error_reason_table())
    # Ghi chú giá Gemini Flash tăng 01/01/2027
    print("NOTE pricing: Gemini Flash rates rise 2027-01-01 — see config/llm.yaml debate.pricing")
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    # cho phép import không chạy
    set_generate_fn(None)
    raise SystemExit(main())
