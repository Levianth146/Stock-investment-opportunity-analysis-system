"""Điểm đánh giá ứng dụng (chỉ số K-Q3) từ App Store (iTunes Search/Lookup API chính thức) và Google Play (google-play-scraper).
  python 05_app_ratings.py --discover   # liệt kê ứng viên theo app_search để bạn CHỌN id đúng, điền vào config/banks.yaml
  python 05_app_ratings.py --collect    # lấy rating + số lượt đánh giá, ghi out/app_ratings.csv (có ngày thu thập)
Số liệu chỉ có tại thời điểm chạy: ghi rõ ngày thu thập trong đề tài."""
import csv, sys, time, requests
from common import *

banks = load_yaml("banks.yaml")["banks"]
S = requests.Session(); S.headers["User-Agent"] = "academic-research"
DELAY = 3.0

def apple_search(term):
    r = S.get("https://itunes.apple.com/search", params={"term": term, "country": "vn", "entity": "software", "limit": 5}, timeout=30)
    r.raise_for_status(); return r.json().get("results", [])
def apple_lookup(app_id):
    r = S.get("https://itunes.apple.com/lookup", params={"id": app_id, "country": "vn"}, timeout=30)
    r.raise_for_status(); res = r.json().get("results", []); return res[0] if res else None
def play_search(term):
    from google_play_scraper import search
    return search(term, lang="vi", country="vn", n_hits=5)
def play_app(app_id):
    from google_play_scraper import app
    return app(app_id, lang="vi", country="vn")

if "--discover" in sys.argv:
    for key, b in banks.items():
        for term in b["app_search"]:
            print(f"\n== {b['name']} | tìm: {term}")
            try:
                for a in apple_search(term):
                    print(f"  [Apple] id={a['trackId']}  {a['trackName']} | {a.get('sellerName')} | rating={a.get('averageUserRating')} n={a.get('userRatingCount')}")
            except Exception as e: print("  Apple lỗi:", e)
            time.sleep(DELAY)
            try:
                for a in play_search(term):
                    print(f"  [Play ] id={a['appId']}  {a['title']} | {a.get('developer')} | score={a.get('score')}")
            except Exception as e: print("  Play lỗi:", e)
            time.sleep(DELAY)
    print("\nChọn app CHÍNH CHỦ của ngân hàng (kiểm tra tên nhà phát hành) rồi điền apple_id / play_id vào config/banks.yaml")

if "--collect" in sys.argv:
    p = OUT / "app_ratings.csv"; new = not p.exists()
    with open(p, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new: w.writerow(["date", "bank", "store", "app_id", "title", "rating", "rating_count", "version", "note"])
        for key, b in banks.items():
            res = {}
            if b.get("apple_id"):
                try:
                    a = apple_lookup(b["apple_id"])
                    if a:
                        w.writerow([today(), key, "apple", b["apple_id"], a.get("trackName"), a.get("averageUserRating"), a.get("userRatingCount"), a.get("version"), "averageUserRating = trung bình mọi phiên bản"])
                        res["apple"] = (a.get("averageUserRating"), a.get("userRatingCount"))
                except Exception as e: print(key, "Apple lỗi:", e)
                time.sleep(DELAY)
            if b.get("play_id"):
                try:
                    a = play_app(b["play_id"])
                    w.writerow([today(), key, "play", b["play_id"], a.get("title"), a.get("score"), a.get("ratings"), a.get("version"), f"installs={a.get('installs')}"])
                    res["play"] = (a.get("score"), a.get("ratings"))
                except Exception as e: print(key, "Play lỗi:", e)
                time.sleep(DELAY)
            vals = [(r, n) for r, n in res.values() if r and n]
            if vals:
                r = sum(r * n for r, n in vals) / sum(n for _, n in vals)
                print(f"{b['name']:12s} rating gộp có trọng số = {r:.3f}  -> K-Q3 z = {(r - 1) / 4 * 100:.1f}")
if not ({"--discover", "--collect"} & set(sys.argv)): print(__doc__)
