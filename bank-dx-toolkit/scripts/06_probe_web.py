"""Kiểm tra trang web công khai làm bằng chứng cho T3 (cổng developer), D4 (chính sách bảo mật), K2... theo mục `probe` trong banks.yaml.
Mỗi trang: lưu HTML (snapshot có ngày), kiểm tra từ khóa kỳ vọng, tùy chọn chụp ảnh toàn trang.
  python 06_probe_web.py [--screenshot] [--js]
  --js          dùng Playwright (trang tải nội dung bằng JavaScript)
  --screenshot  chụp PNG toàn trang (cần Playwright)
Đầu ra: out/web_probe.csv + data/web/<bank>/<criterion>_<ngày>.html(.png). Không đăng nhập, không vượt rào chặn bot."""
import csv, re, sys, time, requests
from bs4 import BeautifulSoup
from common import *
from public_web import PublicFetcher

banks = load_yaml("banks.yaml")["banks"]
use_js = "--js" in sys.argv or "--screenshot" in sys.argv
shot = "--screenshot" in sys.argv
UA = "Mozilla/5.0 (academic research)"
fetcher = PublicFetcher(UA)
rows = []
pw = browser = None
if use_js:
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start(); browser = pw.chromium.launch()
    context = browser.new_context(user_agent=UA, service_workers="block")
    def guarded_route(route):
        """Áp robots và khoảng nghỉ cho cả tài nguyên phụ của trang JavaScript."""
        if route.request.url.startswith(("http://", "https://")):
            if not fetcher.allowed(route.request.url):
                route.abort()
                return
            fetcher.wait()
        # Không cho transport tự theo redirect: browser nhận 3xx để kiểm tra đích kế tiếp.
        response = route.fetch(max_redirects=0)
        route.fulfill(response=response)
    context.route("**/*", guarded_route)

def fetch(url, png_path=None):
    if use_js:
        pg = context.new_page()
        try:
            resp = pg.goto(url, wait_until="networkidle", timeout=60000)
            html = pg.content(); status = resp.status if resp else 0; final = pg.url
            if shot and png_path: pg.screenshot(path=str(png_path), full_page=True)
            return status, final, html
        finally:
            pg.close()
    r = fetcher.get(url, timeout=40); return r.status_code, r.url, r.text

for key, b in banks.items():
    for item in b.get("probe") or []:
        d = DATA / "web" / key; d.mkdir(parents=True, exist_ok=True)
        base = d / f"{item['criterion']}_{today()}"
        try:
            status, final, html = fetch(item["url"], base.with_suffix(".png"))
            base.with_suffix(".html").write_text(html, encoding="utf8")
            soup = BeautifulSoup(html, "html.parser")
            for t in soup(["script", "style", "noscript"]): t.decompose()
            text = nfc(re.sub(r"\s+", " ", soup.get_text(" ")))
            found = [k for k in item.get("expect", []) if re.search(re.escape(k), text, re.I)]
            miss = [k for k in item.get("expect", []) if k not in found]
            rows.append([key, item["criterion"], item["url"], status, final, (soup.title.string or "").strip() if soup.title else "", len(text), "; ".join(found), "; ".join(miss), str(base.with_suffix(".html").relative_to(ROOT)), today()])
            print(key, item["criterion"], status, "tìm thấy:", found, "thiếu:", miss)
        except Exception as e:
            rows.append([key, item["criterion"], item["url"], "error", "", "", 0, "", "", str(e), today()]); print(key, item["criterion"], "lỗi:", e)
        time.sleep(3)
if browser: browser.close(); pw.stop()
with open(OUT / "web_probe.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["bank", "criterion", "url", "status", "final_url", "title", "text_chars", "found", "missing", "snapshot", "date"]); w.writerows(rows)
print("->", OUT / "web_probe.csv")
