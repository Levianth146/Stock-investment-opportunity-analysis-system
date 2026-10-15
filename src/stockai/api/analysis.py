"""Request contract and frontend adapter for the existing snapshot pipeline."""
from __future__ import annotations

from datetime import date
from math import isfinite
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from stockai.api.store import ResultStore, repo_root
from stockai.api.company_profile import company_profile
from stockai.api.dividends import dividends_for
from stockai.llm.payload import build_debate_payload


def financial_reports(snapshot: dict, asof: str) -> dict:
    """Statement items in their original unit, available at the snapshot date."""
    financials = snapshot.get("financials") or {}
    result = {
        "unit": financials.get("unit"),
        "is_bank": bool((snapshot.get("company") or {}).get("is_bank")),
        "published_at_note": financials.get("published_at_note"),
    }
    for frequency in ("annual", "quarterly"):
        periods = []
        for row in financials.get(frequency) or []:
            published = row.get("published_at")
            if not published or str(published)[:10] > asof:
                continue
            items = {
                key: value if isinstance(value, (int, float)) and not isinstance(value, bool)
                and isfinite(value) else None
                for key, value in (row.get("items") or {}).items()
            }
            periods.append({
                "period": row.get("period"),
                "published_at": published,
                "published_at_estimated": bool(row.get("published_at_estimated")),
                "source_id": row.get("source_id"),
                "items": items,
            })
        periods.sort(key=lambda row: (str(row["period"]), str(row["published_at"])))
        result[frequency] = periods
    return result


class AnalyzeRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=6, pattern=r"^[A-Z0-9]{1,6}$")
    profile: Literal["long_term", "swing"] = "long_term"
    as_of: date | None = None

    @field_validator("ticker", mode="before")
    @classmethod
    def normalize_ticker(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


def analyze_snapshot(store: ResultStore, ticker: str, profile: str) -> dict:
    bundle = store.get_bundle(ticker, profile, debate_mode="template")
    snapshot = store.load_snapshot(ticker)
    result = bundle.get("m7") or {}
    company = dict(snapshot.get("company") or {})
    company.update({key: value for key, value in (bundle.get("company") or {}).items() if value is not None})
    root = getattr(store, "root", None) or repo_root()
    profile_data = company_profile(snapshot, ticker, root)
    if profile_data.get("name") and company.get("name") in (None, "", ticker):
        company["name"] = profile_data["name"]
    target = result.get("target") or {}
    rows = sorted(
        (r for r in (snapshot.get("prices") or {}).get("rows", [])
         if r.get("date") and r["date"] <= store.asof
         and isinstance(r.get("close"), (int, float)) and not isinstance(r["close"], bool)
         and isfinite(r["close"])),
        key=lambda r: r["date"],
    )
    latest = rows[-1] if rows else {}
    price = latest.get("close")
    previous = rows[-2].get("close") if len(rows) > 1 else None
    change = price - previous if price is not None and previous is not None else None
    base = target.get("base")
    # Use the same n1/n2 mapping as the debate generator, not snapshot article order.
    payload = build_debate_payload(snapshot, bundle, {"profile": profile})
    news_by_id = {str(item.get("id")): item for item in snapshot.get("news", [])}
    news = []
    for item in payload["news"]:
        source = news_by_id.get(item["id"], {})
        published = source.get("published_at")
        if published and str(published)[:10] > store.asof:
            continue
        news.append({
            **item,
            "title": source.get("title") or item["title"],
            "summary": source.get("summary"),
            "source": source.get("source"),
            "url": source.get("url"),
            "published_at": published,
        })
    reports = financial_reports(snapshot, store.asof)
    source_flags = (snapshot.get("meta") or {}).get("flags") or []
    source_news = [item for item in snapshot.get("news", [])
                   if not item.get("published_at") or str(item["published_at"])[:10] <= store.asof]
    return {
        "ticker": ticker,
        "profile": profile,
        "as_of": store.asof,
        "company": company,
        "company_profile": profile_data,
        "dividends": dividends_for(root, ticker, asof=store.asof),
        "score": result.get("score"),
        "recommendation": result.get("rating"),
        "scores": result.get("scores"),
        "target_price": base,
        "target": result.get("target"),
        "current_price": price,
        "price_date": latest.get("date"),
        "price_change": change,
        "price_change_percent": round(change / previous * 100, 2) if change is not None and previous else None,
        "upside": round((base / price - 1) * 100, 2) if base is not None and price else None,
        "volume": latest.get("volume"),
        "price_history": [
            {key: row.get(key) for key in ("date", "open", "high", "low", "close", "volume")}
            for row in rows[-252:]
        ],
        "bull": result.get("bull") or [],
        "bear": result.get("bear") or [],
        "debate_source": "template",
        "news": news,
        "news_ref_map": payload["news_ref_map"],
        "quality_gate": result.get("quality_gate"),
        "flags": result.get("flags") or [],
        "modules": {key: bundle.get(key) for key in ("m2", "m3", "m4", "m5", "m6")},
        "validation": bundle.get("m8"),
        "financial_reports": reports,
        "data_availability": {
            "price_sessions": len(rows),
            "price_date": latest.get("date"),
            "annual_reports": len(reports["annual"]),
            "quarterly_reports": len(reports["quarterly"]),
            "news_articles": len(source_news),
            "collection_incomplete": "fetch_skipped_early" in source_flags,
            "data_status": (snapshot.get("meta") or {}).get("data_status") or {},
        },
        "data_source": "snapshot",
        "report_url": f"/api/report/{ticker}.pdf?profile={profile}",
    }
