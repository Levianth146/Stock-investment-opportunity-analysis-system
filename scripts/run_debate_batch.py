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
    get_network_call_count,
    load_dotenv_keys,
    load_llm_cfg,
    reset_circuit_state,
    reset_network_call_count,
    set_max_live_calls,
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
    p.add_argument(
        "--top",
        type=int,
        default=0,
        help="Prefetch top N theo điểm (profile) + VN30; bỏ qua cache LLM còn hạn",
    )
    p.add_argument(
        "--pause-sec",
        type=float,
        default=2.0,
        help="Nghỉ giữa các mã khi --top (tránh 429)",
    )
    p.add_argument("--config", default=str(ROOT / "config" / "llm.yaml"))
    p.add_argument("--profile", default="long_term")
    p.add_argument("--print-debate", action="store_true", help="In đầy đủ bull/bear")
    p.add_argument(
        "--template-only",
        action="store_true",
        help="Bỏ qua LLM (không đọc lại .env key) — chỉ template fallback",
    )
    p.add_argument(
        "--max-live-calls",
        type=int,
        default=6,
        help="Trần số HTTP LLM thật trong batch (mặc định 6; free Gemini ~20/ngày/model)",
    )
    p.add_argument(
        "--prefer-model",
        default="",
        help="Ưu tiên model Gemini đầu danh sách (vd gemini-3.6-flash)",
    )
    return p.parse_args()


def _load_vn30() -> set[str]:
    """Đọc danh sách VN30 từ config nếu có."""
    for name in ("universe_vn30.yaml", "universe.yaml"):
        fp = ROOT / "config" / name
        if not fp.is_file():
            continue
        try:
            import yaml

            data = yaml.safe_load(fp.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        if isinstance(data, dict):
            for key in ("vn30", "tickers", "symbols"):
                raw = data.get(key)
                if isinstance(raw, list):
                    return {str(x).strip().upper() for x in raw if str(x).strip()}
        if isinstance(data, list):
            return {str(x).strip().upper() for x in data if str(x).strip()}
    # Fallback cứng ngắn (có thể thiếu) — batch vẫn chạy bằng ranking
    return {
        "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
        "MBB", "MSN", "MWG", "PLX", "LPB", "SAB", "SHB", "SSB", "SSI", "STB",
        "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
    }


def _pick_top_tickers(as_of: str, profile: str, n: int, snap_dir: Path) -> list[str]:
    """Top N theo điểm ranking (API cache nếu có) + ưu tiên VN30; fallback snapshot."""
    vn30 = _load_vn30()
    ranked: list[tuple[float, str]] = []
    cache = ROOT / "data" / "api_cache" / f"rankings_{profile}_{as_of}.json"
    if cache.is_file():
        try:
            payload = json.loads(cache.read_text(encoding="utf-8"))
            rows = payload.get("items") or payload.get("rows") or payload
            if isinstance(rows, list):
                for r in rows:
                    if not isinstance(r, dict):
                        continue
                    t = str(r.get("ticker") or r.get("symbol") or "").upper()
                    sc = r.get("score")
                    if not t or not isinstance(sc, (int, float)):
                        continue
                    ranked.append((float(sc), t))
        except (OSError, ValueError):
            pass
    if not ranked:
        # Fallback: mọi snapshot có file
        for f in sorted(snap_dir.glob(f"*_{as_of}.json")):
            if f.name.startswith("_"):
                continue
            ranked.append((0.0, f.name.split("_")[0].upper()))
    # Ưu tiên VN30: điểm + bonus lớn
    scored = []
    for sc, t in ranked:
        bonus = 1000.0 if t in vn30 else 0.0
        scored.append((sc + bonus, t))
    scored.sort(key=lambda x: (-x[0], x[1]))
    out: list[str] = []
    seen: set[str] = set()
    for _, t in scored:
        if t in seen:
            continue
        if not (snap_dir / f"{t}_{as_of}.json").is_file():
            continue
        seen.add(t)
        out.append(t)
        if len(out) >= n:
            break
    return out


def _has_valid_llm_cache(ticker: str, as_of: str, cache_dir: str) -> bool:
    """True nếu đã có file cache debate LLM cho mã/as_of (bỏ qua prefetch)."""
    d = Path(cache_dir)
    if not d.is_dir():
        return False
    for p in d.glob(f"{ticker}_*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        if str(data.get("as_of") or data.get("asof") or "") != as_of:
            # tên file đôi khi chứa as_of
            if as_of not in p.name:
                continue
        if data.get("bull") and data.get("bear"):
            return True
    return False


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
    reset_network_call_count()
    if not args.template_only:
        set_max_live_calls(args.max_live_calls)
    llm_cfg = load_llm_cfg(args.config)
    if args.prefer_model.strip() and isinstance(llm_cfg.get("debate"), dict):
        g = dict(llm_cfg["debate"].get("gemini") or {})
        pref = args.prefer_model.strip()
        models = list(g.get("models") or [])
        if pref in models:
            models = [pref] + [m for m in models if m != pref]
        else:
            models = [pref] + models
        g["models"] = models
        g["model"] = pref
        llm_cfg["debate"]["gemini"] = g
    snap_dir = Path(args.snapshots_dir)
    debate_cache = str((llm_cfg.get("debate") or {}).get("cache_dir") or "data/llm_cache")
    prefetch = int(args.top or 0) > 0
    if args.tickers.strip():
        tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]
    elif prefetch:
        tickers = _pick_top_tickers(args.as_of, args.profile, int(args.top), snap_dir)
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
    counts = {
        "llm_ok": 0,
        "fallback": 0,
        "cache_hit": 0,
        "error": 0,
        "created": 0,
        "skipped": 0,
        "failed": 0,
    }
    total_cost = 0.0
    rows_report: list[dict] = []
    print(
        f"as_of={args.as_of} tickers={len(tickers)} dir={snap_dir} "
        f"profile={args.profile} top={args.top or '-'} "
        f"max_live_calls={args.max_live_calls if not args.template_only else 0}"
    )

    import time as _time

    for idx, ticker in enumerate(tickers):
        path = snap_dir / f"{ticker}_{args.as_of}.json"
        if prefetch and _has_valid_llm_cache(ticker, args.as_of, debate_cache):
            print(f"{ticker}: skipped valid_cache")
            counts["skipped"] += 1
            rows_report.append(
                {
                    "ticker": ticker,
                    "model": "-",
                    "latency_ms": 0,
                    "status": "skipped_cache",
                    "cost_usd": 0.0,
                }
            )
            continue
        try:
            snap = _load_snapshot(path)
            if snap is None:
                print(f"{ticker}: error missing_or_bad_json")
                counts["error"] += 1
                counts["failed"] += 1
                rows_report.append(
                    {
                        "ticker": ticker,
                        "model": "-",
                        "latency_ms": 0,
                        "status": "error",
                        "cost_usd": 0.0,
                    }
                )
                continue
            t0 = _time.monotonic()
            up = build_upstream_m2_m6(snap, scoring_cfg)
            # Dùng run_m7 để có score/rating + flags; debate nằm trong đó
            result = run_m7(snap, up, scoring_cfg)
            latency_ms = int((_time.monotonic() - t0) * 1000)
            flags = result.get("flags") or []
            bull, bear = result.get("bull") or [], result.get("bear") or []
            cost = float(scoring_cfg.get("_debate_cost_usd") or 0.0)
            model = str(scoring_cfg.get("_debate_model") or "-")
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
                counts["skipped"] += 1
            if src.startswith("FALLBACK"):
                counts["fallback"] += 1
                counts["failed"] += 1
                status = "fallback"
            elif src.startswith("LLM"):
                counts["llm_ok"] += 1
                if "debate_cache_hit" not in flags:
                    counts["created"] += 1
                status = "llm_ok"
            else:
                if result.get("quality_gate", {}).get("scored") is False:
                    status = "quality_gate"
                    counts["failed"] += 1
                else:
                    status = "ok_unknown"
                    counts["llm_ok"] += 1
                    counts["created"] += 1
            print(
                f"{ticker}: {status} source={src} model={model} "
                f"bull={len(bull)} bear={len(bear)} "
                f"score={result.get('score')} rating={result.get('rating')} "
                f"latency_ms={latency_ms} cost_usd≈{cost:.6f}"
            )
            rows_report.append(
                {
                    "ticker": ticker,
                    "model": model,
                    "latency_ms": latency_ms,
                    "status": status,
                    "cost_usd": cost,
                }
            )
            if args.print_debate:
                print(f"  --- {src} BULL ---")
                for i, it in enumerate(bull):
                    print(f"    [{i}] {it.get('text')} refs={it.get('refs')}")
                print(f"  --- {src} BEAR ---")
                for i, it in enumerate(bear):
                    print(f"    [{i}] {it.get('text')} refs={it.get('refs')}")
            # Dừng batch khi hết hạn mức
            if any(
                isinstance(f, str) and "quota_exhausted" in f
                for f in flags
            ):
                print(f"STOP quota_exhausted after {ticker}")
                break
        except Exception as e:
            counts["error"] += 1
            counts["failed"] += 1
            print(f"{ticker}: error {type(e).__name__}: {e}")
            traceback.print_exc(limit=1)
            rows_report.append(
                {
                    "ticker": ticker,
                    "model": "-",
                    "latency_ms": 0,
                    "status": f"error:{type(e).__name__}",
                    "cost_usd": 0.0,
                }
            )
            if "quota" in str(e).lower():
                print("STOP quota exception")
                break
        if prefetch and idx + 1 < len(tickers) and float(args.pause_sec) > 0:
            _time.sleep(float(args.pause_sec))

    print(
        "SUMMARY "
        f"created={counts['created']} skipped={counts['skipped']} "
        f"failed={counts['failed']} "
        f"llm_ok={counts['llm_ok']} fallback={counts['fallback']} "
        f"cache_hit={counts['cache_hit']} error={counts['error']} "
        f"est_cost_usd={total_cost:.6f}"
    )
    if rows_report:
        print("TABLE ticker\tmodel\tlatency_ms\tstatus\tcost_usd")
        for r in rows_report:
            print(
                f"{r['ticker']}\t{r['model']}\t{r['latency_ms']}\t"
                f"{r['status']}\t{r['cost_usd']:.6f}"
            )
    print(f"TOTAL_NETWORK_CALLS={get_network_call_count()}")
    print(format_error_reason_table())
    # Ghi chú giá Gemini Flash tăng 01/01/2027
    print("NOTE pricing: Gemini Flash rates rise 2027-01-01 — see config/llm.yaml debate.pricing")
    set_max_live_calls(None)
    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    # cho phép import không chạy
    set_generate_fn(None)
    raise SystemExit(main())
