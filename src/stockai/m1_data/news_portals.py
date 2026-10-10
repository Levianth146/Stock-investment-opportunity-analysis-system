"""Cổng tin tài chính Việt Nam cho M1 (N2).

Mặc định chỉ chạy CafeF (`news_portals_active`); parser VnEconomy/TNCK giữ nhưng tắt.

Chỉ chạy khi news_portals_enabled và universe_name ∈ {VN30, VN100}.
Mỗi bài MUST nhắc mã (\\bTICKER\\b, phân biệt hoa thường) trong tiêu đề hoặc đầu nội dung.
Fixture/HTML parse offline qua tham số fetch; không bịa ngày; URL n/a không làm khóa trùng.
"""
from __future__ import annotations

import gzip
import hashlib
import html as html_lib
import re
import time
import zlib
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from stockai.m1_data.news_extra import http_get

FetchFn = Callable[[str], bytes]

_UA = "Mozilla/5.0 (compatible; stockai-m1/1.0)"


class PortalDecompressError(OSError):
    """Giải nén gzip/deflate thất bại — không im lặng parse body rác."""

# Cổng trong phạm vi (xem specs/003-news-portals/research.md).
PORTAL_META: dict[str, dict[str, str]] = {
    "cafef": {
        "source": "CafeF",
        "home": "https://cafef.vn",
        "source_id": "src_news_cafef",
    },
    "vneconomy": {
        "source": "VnEconomy",
        "home": "https://vneconomy.vn",
        "source_id": "src_news_vneconomy",
    },
    "tinnhanhchungkhoan": {
        "source": "TinNhanhChungKhoan",
        "home": "https://www.tinnhanhchungkhoan.vn",
        "source_id": "src_news_tinnhanhchungkhoan",
    },
}

# Độ dài đầu nội dung dùng để khớp mã (sau khi bỏ HTML).
_RELEVANCE_BODY_CHARS = 2500

_SUMMARY_LIMIT = 500
_UA_SLEEP_ONLY_DEFAULT = http_get


def portals_enabled(cfg: dict) -> bool:
    """True khi bật cổng và universe được phép."""
    if not cfg.get("news_portals_enabled"):
        return False
    return str(cfg.get("universe_name") or "") in {"VN30", "VN100"}


def active_portal_slugs(cfg: dict) -> list[str]:
    """Danh sách slug được chạy (cfg news_portals_active); mặc định chỉ cafef."""
    raw = cfg.get("news_portals_active")
    if raw is None:
        raw = ["cafef"]
    if isinstance(raw, str):
        raw = [raw]
    out: list[str] = []
    for item in raw:
        slug = str(item).strip().lower()
        if slug in PORTAL_META and slug not in out:
            out.append(slug)
    return out


def _prioritize_links_by_title(links: list[dict], ticker: str) -> list[dict]:
    """Ưu tiên link đã nhắc mã trong title/anchor; vẫn giữ đủ danh sách (trần cắt sau)."""
    hit: list[dict] = []
    miss: list[dict] = []
    for link in links:
        if ticker_relevant(ticker, link.get("title"), ""):
            hit.append(link)
        else:
            miss.append(link)
    return hit + miss


def usable_url(url: str | None) -> bool:
    if url is None:
        return False
    u = str(url).strip()
    return bool(u) and u.lower() != "n/a"


def normalize_url(url: str | None) -> str | None:
    """Chuẩn hóa URL; None nếu rỗng hoặc n/a (không dùng làm khóa trùng)."""
    if not usable_url(url):
        return None
    u = str(url).strip()
    if u.startswith("//"):
        u = "https:" + u
    p = urlparse(u)
    scheme = (p.scheme or "https").lower()
    netloc = p.netloc.lower()
    path = p.path or "/"
    # bỏ fragment + query tracking đơn giản
    return urlunparse((scheme, netloc, path, "", "", ""))


def normalize_title(title: str | None) -> str:
    t = (title or "").lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t.strip(" \t.,;:!?'\"“”‘’")


def parse_published_at(raw: str | None) -> str | None:
    """Trả ISO đầy đủ hoặc YYYY-MM-DD; None nếu thiếu / chỉ năm / không parse được."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    # chỉ năm
    if re.fullmatch(r"\d{4}", s):
        return None
    # YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s
    # ISO / offset
    m = re.match(
        r"^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}(?::\d{2})?)",
        s,
    )
    if m:
        day, hm = m.group(1), m.group(2)
        if len(hm) == 5:
            hm += ":00"
        return f"{day}T{hm}"
    # dd/mm/yyyy[ hh:mm[:ss]]
    m = re.match(
        r"^(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
        s,
    )
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        day = f"{y:04d}-{mo:02d}-{d:02d}"
        if m.group(4) is None:
            return day
        hh, mm = int(m.group(4)), int(m.group(5))
        ss = int(m.group(6) or 0)
        return f"{day}T{hh:02d}:{mm:02d}:{ss:02d}"
    return None


def in_date_window(published_at: str, nstart: str, as_of: str) -> bool:
    day = published_at[:10]
    return nstart <= day <= as_of


def make_summary(teaser: str | None, body: str | None, limit: int = _SUMMARY_LIMIT) -> str | None:
    text = (teaser or "").strip() or (body or "").strip()
    if not text:
        return None
    text = re.sub(r"\s+", " ", html_lib.unescape(text)).strip()
    return text[:limit] if text else None


def ticker_relevant(ticker: str, title: str | None, body_or_html: str | None) -> bool:
    """True khi mã (viết hoa) khớp nguyên từ \\bTICKER\\b trong tiêu đề hoặc đầu nội dung.

    Phân biệt hoa thường: chỉ khớp đúng ticker.upper() (vd VCB, không khớp vcb).
    """
    t = (ticker or "").strip().upper()
    if not t:
        return False
    title_s = title or ""
    body_s = body_or_html or ""
    # nếu còn HTML → bỏ thẻ rồi lấy phần đầu
    if "<" in body_s:
        body_s = re.sub(r"<script[^>]*>.*?</script>", " ", body_s, flags=re.I | re.S)
        body_s = re.sub(r"<style[^>]*>.*?</style>", " ", body_s, flags=re.I | re.S)
        body_s = re.sub(r"<[^>]+>", " ", body_s)
    body_s = html_lib.unescape(body_s)
    head = f"{title_s} {body_s}"[: _RELEVANCE_BODY_CHARS + len(title_s) + 1]
    return re.search(rf"\b{re.escape(t)}\b", head) is not None


def news_id(url: str, title: str) -> str:
    return "n" + hashlib.sha1(f"{url}|{title}".encode("utf-8")).hexdigest()[:10]


def to_news_item(article: dict) -> dict:
    """Đưa PortalArticle về shape contract news."""
    url = article.get("url") or "n/a"
    title = article["title"]
    return {
        "id": article.get("id") or news_id(url, title),
        "title": title,
        "url": url,
        "source": article["source"],
        "published_at": article["published_at"],
        "summary": article.get("summary"),
        "_portal_slug": article.get("portal_slug"),
        "_source_id": article.get("source_id") or PORTAL_META.get(article.get("portal_slug", ""), {}).get("source_id"),
    }


def merge_news(existing: list[dict], portal_articles: list[dict], max_news: int) -> list[dict]:
    """Gộp tin; trùng URL hợp lệ hoặc tiêu đề → giữ bản cổng; sắp mới → cắt max_news."""
    portal_items = [to_news_item(a) if "portal_slug" in a or "_portal_slug" in a else a for a in portal_articles]
    # đánh dấu cổng
    for p in portal_items:
        p.setdefault("_from_portal", True)

    out: list[dict] = []
    url_keys: dict[str, int] = {}
    title_keys: dict[str, int] = {}

    def _upsert(item: dict, prefer: bool) -> None:
        nu = normalize_url(item.get("url"))
        nt = normalize_title(item.get("title"))
        idx = None
        if nu is not None and nu in url_keys:
            idx = url_keys[nu]
        elif nt and nt in title_keys:
            idx = title_keys[nt]
        if idx is None:
            out.append(item)
            i = len(out) - 1
            if nu is not None:
                url_keys[nu] = i
            if nt:
                title_keys[nt] = i
            return
        if prefer or out[idx].get("_from_portal"):
            # giữ portal nếu đang prefer portal hoặc slot đã là portal
            if prefer:
                out[idx] = item
                if nu is not None:
                    url_keys[nu] = idx
                if nt:
                    title_keys[nt] = idx

    for it in existing:
        row = {**it, "_from_portal": False}
        _upsert(row, prefer=False)
    for it in portal_items:
        row = {**it, "_from_portal": True}
        _upsert(row, prefer=True)

    out.sort(key=lambda x: x.get("published_at") or "", reverse=True)
    trimmed = out[: int(max_news)]
    for it in trimmed:
        it.pop("_from_portal", None)
        it.pop("_portal_slug", None)
        # giữ _source_id tạm cho caller gắn sources; fetch_news sẽ pop
    return trimmed


# ------------------------------------------------------------------ cache / gzip
def _cache_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def _is_gzip_magic(data: bytes) -> bool:
    return len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B


def decompress_http_body(data: bytes, content_encoding: str | None = None) -> bytes:
    """Giải nén body còn nén (magic 1f 8b hoặc deflate thật).

    Nếu header bảo gzip nhưng không còn magic → urllib đã giải nén sẵn, trả nguyên.
    Body vẫn nén mà giải thất bại → PortalDecompressError (không im lặng).
    """
    enc = (content_encoding or "").lower().strip()
    # gzip: chỉ giải khi còn magic (tránh double-decompress khi header còn gzip)
    if _is_gzip_magic(data):
        try:
            return gzip.decompress(data)
        except Exception as e:  # noqa: BLE001
            raise PortalDecompressError(f"giải nén gzip thất bại: {e}") from e
    if enc in ("gzip", "x-gzip"):
        return data  # đã plain
    if enc == "deflate":
        try:
            try:
                return zlib.decompress(data)
            except zlib.error:
                return zlib.decompress(data, -zlib.MAX_WBITS)
        except Exception as e:  # noqa: BLE001
            # một số stack đã inflate sẵn
            if data.lstrip()[:1] in (b"<", b"{", b"[") or data[:1] in (b"\n", b"\r", b" "):
                return data
            raise PortalDecompressError(f"giải nén deflate thất bại: {e}") from e
    return data


def _http_get_raw(url: str, timeout: float = 20.0) -> tuple[bytes, str | None]:
    """GET mạng thật kèm Content-Encoding (không giải nén ở đây)."""
    req = Request(url, headers={"User-Agent": _UA})
    with urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.read(), r.headers.get("Content-Encoding")


def cache_get(cfg: dict, url: str) -> bytes | None:
    """Đọc cache; nếu bản cũ còn magic gzip thì giải nén, lỗi thì xóa và trả None (tải lại)."""
    nu = normalize_url(url)
    if nu is None:
        return None
    root = cfg.get("news_portal_cache_dir")
    if not root:
        return None
    path = Path(root) / f"{_cache_key(nu)}.html"
    if not path.is_file():
        return None
    data = path.read_bytes()
    if not _is_gzip_magic(data):
        return data
    try:
        plain = decompress_http_body(data, "gzip")
        path.write_bytes(plain)  # chuẩn hóa cache sang HTML đã giải nén
        return plain
    except PortalDecompressError:
        path.unlink(missing_ok=True)
        return None


def cache_put(cfg: dict, url: str, data: bytes) -> None:
    """Ghi cache — chỉ lưu body đã giải nén."""
    nu = normalize_url(url)
    if nu is None:
        return
    root = cfg.get("news_portal_cache_dir")
    if not root:
        return
    if _is_gzip_magic(data):
        data = decompress_http_body(data, "gzip")
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    (path / f"{_cache_key(nu)}.html").write_bytes(data)


def fetch_url(url: str, cfg: dict, fetch: FetchFn = http_get) -> bytes:
    """Tải URL; giải nén gzip/deflate trước cache/parse; sleep/retry khi fetch mặc định."""
    cached = cache_get(cfg, url)
    if cached is not None:
        return cached
    retries = int(cfg.get("news_portal_retries", 2))
    delay = float(cfg.get("news_portal_interval_sec", 1.0))
    last_err: Exception | None = None
    use_default = fetch is _UA_SLEEP_ONLY_DEFAULT or fetch is http_get
    for attempt in range(max(1, retries + 1)):
        try:
            if use_default and attempt > 0:
                time.sleep(delay)
            if use_default:
                raw, enc = _http_get_raw(url)
                data = decompress_http_body(raw, enc)
            else:
                data = decompress_http_body(fetch(url), None)
            if use_default:
                time.sleep(delay)
            cache_put(cfg, url, data)
            return data
        except PortalDecompressError:
            raise
        except Exception as e:  # noqa: BLE001
            last_err = e
    assert last_err is not None
    raise last_err


# ------------------------------------------------------------------ HTML helpers
def _meta_content(html: str, *names: str) -> str | None:
    for name in names:
        m = re.search(
            rf'<meta[^>]+(?:property|name)=["\']{re.escape(name)}["\'][^>]*content=["\']([^"\']+)["\']',
            html,
            re.I,
        )
        if m:
            return html_lib.unescape(m.group(1)).strip()
        m = re.search(
            rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']{re.escape(name)}["\']',
            html,
            re.I,
        )
        if m:
            return html_lib.unescape(m.group(1)).strip()
    return None


def _first_time_datetime(html: str) -> str | None:
    m = re.search(r'<time[^>]+datetime=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1).strip()
    m = re.search(r'itemprop=["\']datePublished["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
    if m:
        return m.group(1).strip()
    return None


def extract_published_at(html: str) -> str | None:
    raw = _meta_content(html, "article:published_time", "pubdate", "publishdate", "date")
    if not raw:
        raw = _first_time_datetime(html)
    return parse_published_at(raw)


def extract_title(html: str) -> str | None:
    t = _meta_content(html, "og:title", "twitter:title")
    if t:
        return t
    m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
    return html_lib.unescape(m.group(1)).strip() if m else None


def extract_teaser(html: str) -> str | None:
    return _meta_content(html, "og:description", "description", "twitter:description")


def extract_body_prefix(html: str, limit: int = 2000) -> str | None:
    # bỏ script/style
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    # ưu tiên khối bài phổ biến
    for pat in (
        r'<div[^>]+(?:class|id)=["\'][^"\']*(?:detail-content|content-detail|article-content|entry-content)[^"\']*["\'][^>]*>(.*?)</div>',
        r"<article[^>]*>(.*?)</article>",
    ):
        m = re.search(pat, text, re.I | re.S)
        if m:
            chunk = re.sub(r"<[^>]+>", " ", m.group(1))
            chunk = re.sub(r"\s+", " ", html_lib.unescape(chunk)).strip()
            if len(chunk) > 40:
                return chunk[:limit]
    return None


def parse_article_html(html: str, url: str, portal_slug: str) -> dict | None:
    """Parse trang bài → PortalArticle hoặc None nếu thiếu ngày/tiêu đề."""
    meta = PORTAL_META[portal_slug]
    title = extract_title(html)
    published = extract_published_at(html)
    if not title or not published:
        return None
    teaser = extract_teaser(html)
    body = extract_body_prefix(html)
    summary = make_summary(teaser, body)
    return {
        "title": title,
        "url": normalize_url(url) or url,
        "published_at": published,
        "source": meta["source"],
        "summary": summary,
        "portal_slug": portal_slug,
        "source_id": meta["source_id"],
    }


# ------------------------------------------------------------------ portal-specific listing
def _abs_href(href: str, home: str) -> str:
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return home.rstrip("/") + href
    return home.rstrip("/") + "/" + href


def parse_cafef_search(html: str) -> list[dict]:
    """Lấy link bài CafeF (`…-188….chn`) từ tim-kiem hoặc trang mã."""
    out: list[dict] = []
    for m in re.finditer(r'href=["\']([^"\']*188\d+\.chn)["\']', html, re.I):
        url = _abs_href(m.group(1), "https://cafef.vn")
        ctx = html[max(0, m.start() - 200) : m.end() + 200]
        tm = re.search(r'title=["\']([^"\']+)["\']', ctx, re.I)
        title = html_lib.unescape(tm.group(1)).strip() if tm else ""
        out.append({"title": title or url.rsplit("/", 1)[-1], "url": url})
    seen, uniq = set(), []
    for it in out:
        nu = normalize_url(it["url"])
        if nu and nu not in seen:
            seen.add(nu)
            uniq.append(it)
    return uniq


def parse_vneconomy_search(html: str) -> list[dict]:
    """Lấy link bài VnEconomy từ tim-kiem.htm — slug dài, bỏ premium và trang mục."""
    out: list[dict] = []
    for m in re.finditer(r'href=["\']([^"\']+\.htm)["\']', html, re.I):
        href = m.group(1)
        if "premium.vneconomy" in href.lower():
            continue
        url = _abs_href(href, "https://vneconomy.vn")
        if "vneconomy.vn" not in url:
            continue
        path = urlparse(url).path or ""
        # bài thật: slug dài (≥40); bỏ trang mục ngắn
        slug = path.rsplit("/", 1)[-1]
        if len(slug) < 40:
            continue
        if any(x in path for x in ("tim-kiem", "/tag/")):
            continue
        ctx = html[max(0, m.start() - 240) : m.end() + 240]
        tm = re.search(r'title=["\']([^"\']+)["\']', ctx, re.I)
        title = html_lib.unescape(tm.group(1)).strip() if tm else ""
        out.append({"title": title or slug, "url": url})
    seen, uniq = set(), []
    for it in out:
        nu = normalize_url(it["url"])
        if nu and nu not in seen:
            seen.add(nu)
            uniq.append(it)
    return uniq


def parse_tnck_search(html: str) -> list[dict]:
    """Lấy link bài TinNhanhChungKhoan (…-postNNNN.html)."""
    out: list[dict] = []
    for m in re.finditer(
        r'href=["\']((?:https://www\.tinnhanhchungkhoan\.vn)?/[a-z0-9\-]+-post\d+\.html)["\']',
        html,
        re.I,
    ):
        url = _abs_href(m.group(1), "https://www.tinnhanhchungkhoan.vn")
        ctx = html[max(0, m.start() - 240) : m.end() + 240]
        tm = re.search(r'title=["\']([^"\']+)["\']', ctx, re.I)
        title = html_lib.unescape(tm.group(1)).strip() if tm else ""
        out.append({"title": title or url.rsplit("/", 1)[-1], "url": url})
    seen, uniq = set(), []
    for it in out:
        nu = normalize_url(it["url"])
        if nu and nu not in seen:
            seen.add(nu)
            uniq.append(it)
    return uniq


def cafef_search_url(ticker: str) -> str:
    # tim-kiem.chn có link bài trong HTML tĩnh (slug chứa chứa mã); tin-tuc trang mã hay lẫn tin chung
    return f"https://cafef.vn/tim-kiem.chn?keywords={ticker.strip().upper()}"


def vneconomy_search_url(ticker: str) -> str:
    return f"https://vneconomy.vn/tim-kiem.htm?keyword={ticker.strip().upper()}"


def tnck_search_url(ticker: str) -> str:
    # không có search ổn định → chuyên mục; lọc liên quan theo mã ở bước sau
    _ = ticker
    return "https://www.tinnhanhchungkhoan.vn/ngan-hang/"


_PARSERS = {
    "cafef": (cafef_search_url, parse_cafef_search),
    "vneconomy": (vneconomy_search_url, parse_vneconomy_search),
    "tinnhanhchungkhoan": (tnck_search_url, parse_tnck_search),
}


def diagnose_no_date(html: str, url: str) -> dict:
    """Chẩn đoán vì sao parse_article_html trả None (không đổi logic lọc).

    Ưu tiên nguyên nhân ngày (missing_meta / unparsed / premium), rồi mới missing_title.
    """
    raw_meta = _meta_content(html, "article:published_time", "pubdate", "publishdate", "date")
    raw_time = _first_time_datetime(html)
    raw = raw_meta or raw_time
    parsed = parse_published_at(raw) if raw else None
    title = extract_title(html)
    ul = (url or "").lower()
    if "premium.vneconomy" in ul or ("premium" in ul and "vneconomy" in ul):
        reason = "premium_page"
    elif not parsed:
        reason = "missing_meta" if not raw else "unparsed_date_format"
    elif not title:
        reason = "missing_title"  # có ngày nhưng thiếu tiêu đề → art vẫn None
    else:
        reason = "other_parse_none"
    return {
        "reason": reason,
        "url": url,
        "raw_meta": (raw_meta or "")[:120] or None,
        "raw_time": (raw_time or "")[:120] or None,
        "parsed_ok": parsed is not None,
        "title_ok": bool(title),
    }


def _empty_portal_stats(slug: str, search_url: str = "") -> dict:
    return {
        "slug": slug,
        "search_url": search_url,
        "links_found": 0,
        "fetched_ok": 0,
        "fetch_error": 0,
        "drop_no_date": 0,  # art is None (giữ đúng đếm cờ hiện tại)
        "drop_irrelevant": 0,
        "drop_window": 0,
        "kept": 0,
        "no_date_reasons": {},  # reason -> count
        "no_date_samples": [],  # tối đa vài mẫu chẩn đoán
    }


def _fetch_one_portal(
    slug: str,
    ticker: str,
    nstart: str,
    as_of: str,
    cfg: dict,
    fetch: FetchFn,
) -> tuple[list[dict], list[str], dict]:
    """Trả (articles sau lọc ngày, flags riêng, stats chẩn đoán)."""
    flags: list[str] = []
    search_url_fn, parse_search = _PARSERS[slug]
    search_url = search_url_fn(ticker)
    stats = _empty_portal_stats(slug, search_url)
    html = fetch_url(search_url, cfg, fetch=fetch).decode("utf-8", errors="replace")
    links = parse_search(html)
    stats["links_found"] = len(links)
    # CafeF: tải trước các link đã nhắc mã trên title/anchor; trần 30 giữ nguyên
    if slug == "cafef":
        links = _prioritize_links_by_title(links, ticker)
    kept: list[dict] = []
    for link in links[:30]:  # trần an toàn mỗi cổng mỗi mã
        try:
            raw = fetch_url(link["url"], cfg, fetch=fetch)
            page = raw.decode("utf-8", errors="replace")
            art = parse_article_html(page, link["url"], slug)
            stats["fetched_ok"] += 1
        except PortalDecompressError:
            raise  # không im lặng — fetch_portals gắn news_portal_failed
        except Exception:  # noqa: BLE001
            stats["fetch_error"] += 1
            continue
        if art is None:
            stats["drop_no_date"] += 1
            diag = diagnose_no_date(page, link["url"])
            reason = diag["reason"]
            stats["no_date_reasons"][reason] = stats["no_date_reasons"].get(reason, 0) + 1
            if len(stats["no_date_samples"]) < 12:
                stats["no_date_samples"].append(diag)
            continue
        if not art.get("title") and link.get("title"):
            art["title"] = link["title"]
        # lọc liên quan: mã phải xuất hiện trong tiêu đề hoặc đầu nội dung
        if not ticker_relevant(ticker, art.get("title"), page):
            stats["drop_irrelevant"] += 1
            continue
        if not in_date_window(art["published_at"], nstart, as_of):
            stats["drop_window"] += 1
            continue
        kept.append(art)
        stats["kept"] += 1
    return kept, flags, stats


def _emit_portal_diag(ticker: str, stats: dict, cfg: dict) -> None:
    """Ghi stats vào cfg và in khi verbose."""
    cfg.setdefault("_news_portal_diag", {}).setdefault(ticker, {})[stats["slug"]] = stats
    if not (cfg.get("news_portal_verbose") or cfg.get("verbose")):
        return
    print(
        f"[portal-diag] {ticker}/{stats['slug']}: "
        f"links={stats['links_found']} fetched={stats['fetched_ok']} "
        f"fetch_err={stats['fetch_error']} no_date={stats['drop_no_date']} "
        f"irrelevant={stats['drop_irrelevant']} window={stats['drop_window']} "
        f"kept={stats['kept']} reasons={stats['no_date_reasons']}"
    )


def fetch_portals(
    ticker: str,
    company_name: str | None,
    nstart: str,
    as_of: str,
    cfg: dict,
    fetch: FetchFn = http_get,
) -> tuple[list[dict], list[str]]:
    """Lấy tin các cổng trong phạm vi. Cờ ok/empty gắn theo bài sau lọc ngày (trước merge/cap).

    Dedupe với Google và cắt max_news do caller (`merge_news`) đảm nhiệm; ok/empty ở đây
    dựa trên số bài sau lọc ngày từng cổng (FR-007: trước cắt trần — caller truyền
    thêm bước dedupe trước khi quyết định ok nếu cần). Để khớp FR-007 đầy đủ,
    `fetch_news` sẽ gọi `classify_portal_flags` sau dedupe pre-cap.

    Chẩn đoán: cfg["_news_portal_diag"][ticker][slug] (luôn ghi); in khi
    cfg["news_portal_verbose"] hoặc cfg["verbose"].
    """
    _ = company_name
    if not portals_enabled(cfg):
        return [], []

    all_articles: list[dict] = []
    flags: list[str] = []
    no_date_total = 0
    per_slug_raw: dict[str, list[dict]] = {}
    active = active_portal_slugs(cfg)
    cfg["_news_portals_active_run"] = list(active)

    for slug in active:
        try:
            arts, fl, stats = _fetch_one_portal(slug, ticker, nstart, as_of, cfg, fetch)
            flags.extend(fl)
            no_date_total += int(stats["drop_no_date"])
            per_slug_raw[slug] = arts
            all_articles.extend(arts)
            _emit_portal_diag(ticker, stats, cfg)
        except Exception:  # noqa: BLE001
            flags.append(f"news_portal_failed:{slug}")
            per_slug_raw[slug] = []
            failed_stats = _empty_portal_stats(slug)
            failed_stats["fetch_error"] = -1  # cả cổng lỗi ở tầng ngoài
            _emit_portal_diag(ticker, failed_stats, cfg)

    if no_date_total:
        flags.append(f"news_portal_no_date_dropped:{no_date_total}")

    # provisional ok/empty by date filter only; fetch_news may refine after dedupe
    for slug, arts in per_slug_raw.items():
        if any(f == f"news_portal_failed:{slug}" for f in flags):
            continue
        if arts:
            flags.append(f"news_portal_ok:{slug}")
        else:
            flags.append(f"news_portal_empty:{slug}")

    return all_articles, flags


def refine_portal_flags_after_dedupe(
    flags: list[str],
    portal_articles: list[dict],
    surviving_pre_cap: list[dict],
    active_slugs: list[str] | None = None,
) -> list[str]:
    """Gắn lại ok/empty theo bài còn sau dedupe (trước cắt max_news).

    Chỉ gắn cờ cho slug trong active_slugs (mặc định: mọi khóa PORTAL_META — caller nên truyền danh sách active).
    """
    slugs = list(active_slugs) if active_slugs is not None else list(PORTAL_META)
    by_slug: dict[str, int] = {s: 0 for s in slugs}
    for it in surviving_pre_cap:
        slug = it.get("_portal_slug") or it.get("portal_slug")
        if slug in by_slug:
            by_slug[slug] += 1
    # nếu surviving chưa mang slug, map theo URL từ portal_articles
    if sum(by_slug.values()) == 0 and portal_articles:
        urls = {normalize_url(a.get("url")) for a in surviving_pre_cap}
        titles = {normalize_title(a.get("title")) for a in surviving_pre_cap}
        for a in portal_articles:
            slug = a.get("portal_slug")
            if slug not in by_slug:
                continue
            nu = normalize_url(a.get("url"))
            nt = normalize_title(a.get("title"))
            if (nu and nu in urls) or (nt and nt in titles):
                by_slug[slug] += 1

    out = [f for f in flags if not f.startswith("news_portal_ok:") and not f.startswith("news_portal_empty:")]
    failed = {f.split(":", 1)[1] for f in out if f.startswith("news_portal_failed:")}
    for slug in slugs:
        if slug in failed:
            continue
        if by_slug.get(slug, 0) > 0:
            out.append(f"news_portal_ok:{slug}")
        else:
            out.append(f"news_portal_empty:{slug}")
    return out


def merge_pre_cap_for_flags(
    existing: list[dict],
    portal_articles: list[dict],
) -> list[dict]:
    """Giống merge_news nhưng không cắt max_news — dùng để tính ok/empty (FR-007)."""
    return merge_news(existing, portal_articles, max_news=10**9)
