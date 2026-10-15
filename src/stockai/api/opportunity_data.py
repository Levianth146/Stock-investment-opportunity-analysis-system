"""Small price series for the opportunity list, sourced from the same snapshot."""
from math import isfinite
from datetime import date


def recent_closes(snapshot: dict, asof: str) -> list[dict]:
    by_date = {}
    for row in (snapshot.get("prices") or {}).get("rows") or []:
        if not isinstance(row, dict):
            continue
        day, close = str(row.get("date") or "")[:10], row.get("close")
        try:
            date.fromisoformat(day)
        except ValueError:
            continue
        if len(day) == 10 and day <= asof and isinstance(close, (int, float)) and not isinstance(close, bool) and isfinite(close) and close > 0:
            by_date[day] = close
    return [{"date": day, "close": by_date[day]} for day in sorted(by_date)[-20:]]
