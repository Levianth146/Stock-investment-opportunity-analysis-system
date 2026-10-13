"""Chạy FastAPI (uvicorn) — bind 127.0.0.1 theo config/api.yaml."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def main() -> int:
    import uvicorn

    from stockai.api.store import load_api_cfg

    cfg = load_api_cfg(_ROOT / "config" / "api.yaml")
    host = str(cfg.get("host") or "127.0.0.1")
    port = int(cfg.get("port") or 8000)
    # Chỉ lắng nghe localhost — không mở ra mạng
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"Cảnh báo: ép host về 127.0.0.1 (config có {host!r})")
        host = "127.0.0.1"
    uvicorn.run(
        "stockai.api.app:app",
        host=host,
        port=port,
        reload=False,
        factory=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
