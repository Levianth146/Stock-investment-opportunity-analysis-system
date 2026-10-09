"""Hợp đồng dữ liệu giữa các module. CHỈ N1 ĐƯỢC SỬA FILE NÀY.

Cần thêm/đổi trường -> nhắn N1, N1 sửa schema + fixture + commit trước, mọi người rebase.
Quy ước chung:
  - Ngày: chuỗi ISO "YYYY-MM-DD". Thời điểm: "YYYY-MM-DDTHH:MM:SS".
  - Điểm F/T/V/S và penalty R: số 0-100 (R là PENALTY: càng cao càng xấu).
  - Thiếu dữ liệu: để null + ghi vào "flags", KHÔNG tự bịa số.
  - Mọi con số lấy từ nguồn phải truy được về "sources" (qua source_id).
"""
from __future__ import annotations

from jsonschema import Draft202012Validator

_NUM = {"type": ["number", "null"]}
_STR = {"type": "string"}

# --------------------------------------------------------------------------
# M1 -> M2..M6: data_snapshot.json
# --------------------------------------------------------------------------
SNAPSHOT_SCHEMA = {
    "type": "object",
    "required": ["meta", "company", "prices", "index", "financials", "peers", "news", "sources"],
    "properties": {
        "meta": {
            "type": "object",
            "required": ["schema_version", "ticker", "as_of", "window_start", "fetched_at", "data_status"],
            "properties": {
                "schema_version": {"const": "1.0"},
                "ticker": _STR,
                "as_of": _STR,          # ngày phân tích; mọi dữ liệu phải có published_at <= as_of
                "window_start": _STR,   # as_of lùi 5 năm
                "fetched_at": _STR,
                "synthetic": {"type": "boolean"},  # true = dữ liệu GIẢ để test, cấm đưa vào báo cáo thật
                "data_status": {
                    "type": "object",   # mỗi khối: ok | partial | missing
                    "required": ["prices", "index", "financials", "company", "peers", "news"],
                    "additionalProperties": {"enum": ["ok", "partial", "missing"]},
                },
                "flags": {"type": "array", "items": _STR},
            },
        },
        "company": {
            "type": "object",
            "required": ["name", "exchange", "sector", "is_bank"],
            "properties": {
                "name": _STR, "exchange": _STR, "sector": _STR, "industry": {"type": ["string", "null"]},
                "is_bank": {"type": "boolean"},   # ngân hàng/CTCK dùng bộ chỉ tiêu khác (P/B, ROE, NIM...)
                "shares_outstanding": _NUM,
                "source_id": _STR,
            },
        },
        "prices": {
            "type": "object",
            "required": ["adjusted", "source_id", "rows"],
            "properties": {
                "adjusted": {"type": "boolean"},   # BẮT BUỘC dùng giá đã điều chỉnh (cổ tức, chia tách)
                "source_id": _STR,
                "rows": {"type": "array", "items": {
                    "type": "object",
                    "required": ["date", "open", "high", "low", "close", "volume"],
                    "properties": {"date": _STR, "open": _NUM, "high": _NUM, "low": _NUM, "close": _NUM, "volume": _NUM},
                }},
            },
        },
        "index": {   # VN-Index làm benchmark tính beta
            "type": "object",
            "required": ["symbol", "source_id", "rows"],
            "properties": {
                "symbol": _STR, "source_id": _STR,
                "rows": {"type": "array", "items": {
                    "type": "object", "required": ["date", "close"],
                    "properties": {"date": _STR, "close": _NUM},
                }},
            },
        },
        "financials": {
            "type": "object",
            "required": ["unit", "annual", "quarterly"],
            "properties": {
                "unit": _STR,   # ví dụ "VND" hoặc "ty_VND" - ghi rõ, M2/M4 không đoán
                "annual": {"type": "array", "items": {"$ref": "#/$defs/fin_period"}},
                "quarterly": {"type": "array", "items": {"$ref": "#/$defs/fin_period"}},
            },
        },
        "peers": {"type": "array", "items": {
            "type": "object", "required": ["ticker"],
            "properties": {"ticker": _STR, "pe": _NUM, "pb": _NUM, "roe": _NUM, "market_cap": _NUM, "source_id": _STR},
        }},
        "news": {"type": "array", "items": {
            "type": "object", "required": ["id", "title", "url", "source", "published_at"],
            "properties": {
                "id": _STR, "title": _STR, "url": _STR, "source": _STR,
                "published_at": _STR, "summary": {"type": ["string", "null"]},
            },
        }},
        "sources": {"type": "array", "items": {
            "type": "object", "required": ["id", "name", "url", "fetched_at"],
            "properties": {"id": _STR, "name": _STR, "url": _STR, "fetched_at": _STR, "note": {"type": "string"}},
        }},
    },
    "$defs": {
        "fin_period": {
            "type": "object",
            "required": ["period", "published_at", "source_id", "items"],
            "properties": {
                "period": _STR,            # "2024" hoặc "2025Q2"
                "published_at": _STR,      # ngày CÔNG BỐ báo cáo, không phải ngày kết thúc kỳ
                "source_id": _STR,
                # Tên chỉ tiêu cố định (xem docs/CONTRACTS.md). Thiếu thì null.
                "items": {"type": "object", "additionalProperties": _NUM},
            },
        }
    },
}

# --------------------------------------------------------------------------
# M2..M6 output. M2->F, M3->T, M4->V (+target), M5->S, M6->R
# --------------------------------------------------------------------------
MODULE_OUT_SCHEMA = {
    "type": "object",
    "required": ["module", "status", "score", "metrics", "evidence", "flags"],
    "properties": {
        "module": {"enum": ["m2", "m3", "m4", "m5", "m6"]},
        "status": {"enum": ["ok", "partial", "error", "stub"]},   # stub = chưa làm thật
        "score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},  # F/T/V/S, hoặc R với m6
        "metrics": {"type": "object", "additionalProperties": {
            "type": "object", "required": ["value", "unit"],
            "properties": {"value": _NUM, "unit": _STR, "note": {"type": "string"}},
        }},
        "evidence": {"type": "array", "items": {   # câu giải thích + trỏ về nguồn (cho M7, M8, M9)
            "type": "object", "required": ["text"],
            "properties": {"text": _STR, "source_id": _STR, "news_id": _STR},
        }},
        "flags": {"type": "array", "items": _STR},
        # chỉ M4:
        "target": {"type": ["object", "null"], "properties": {
            "base": _NUM, "bull": _NUM, "bear": _NUM, "method": _STR, "assumptions": {"type": "array", "items": _STR},
        }},
        "error": {"type": "string"},
    },
}

# --------------------------------------------------------------------------
# M7 output: analysis_result.json
# --------------------------------------------------------------------------
RESULT_SCHEMA = {
    "type": "object",
    "required": ["ticker", "as_of", "profile", "scores", "weights", "contributions", "score", "rating", "target", "bull", "bear", "flags"],
    "properties": {
        "ticker": _STR, "as_of": _STR, "profile": {"enum": ["long_term", "swing"]},
        "scores": {"type": "object", "required": ["F", "T", "V", "S", "R"]},
        "weights": {"type": "object"},
        "contributions": {"type": "object"},     # đóng góp từng điểm vào Score (để giải thích)
        "score": {"type": "number", "minimum": 0, "maximum": 100},
        "rating": {"enum": ["Mua mạnh", "Mua", "Nắm giữ", "Giảm tỷ trọng", "Bán"]},
        "target": {"type": ["object", "null"]},  # copy NGUYÊN từ M4, M7 không tự đặt
        "bull": {"type": "array", "items": {"type": "object", "required": ["text"]}},
        "bear": {"type": "array", "items": {"type": "object", "required": ["text"]}},
        "flags": {"type": "array", "items": _STR},
    },
}

# --------------------------------------------------------------------------
# M8 output: validation_report.json
# --------------------------------------------------------------------------
VALIDATION_SCHEMA = {
    "type": "object",
    "required": ["status", "checked", "issues"],
    "properties": {
        "status": {"enum": ["pass", "warn", "fail"]},
        "checked": {"type": "integer"},
        "issues": {"type": "array", "items": {
            "type": "object", "required": ["severity", "message"],
            "properties": {"severity": {"enum": ["info", "warn", "fatal"]}, "message": _STR, "where": _STR},
        }},
    },
}

SCHEMAS = {
    "snapshot": SNAPSHOT_SCHEMA,
    "module_out": MODULE_OUT_SCHEMA,
    "result": RESULT_SCHEMA,
    "validation": VALIDATION_SCHEMA,
}


def validate(obj: dict, name: str) -> list[str]:
    """Trả về danh sách lỗi (rỗng = hợp lệ)."""
    v = Draft202012Validator(SCHEMAS[name])
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in v.iter_errors(obj)]


def assert_valid(obj: dict, name: str) -> None:
    errs = validate(obj, name)
    if errs:
        raise ValueError(f"{name} không hợp lệ:\n  " + "\n  ".join(errs[:10]))
