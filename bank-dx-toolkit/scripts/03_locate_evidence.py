"""Định vị đoạn bằng chứng cho 24 tiêu chí + chỉ số mật độ đề cập.
Đầu ra:
  out/evidence_candidates.csv  -> mỗi dòng: tiêu chí, ngân hàng, năm, tài liệu, trang, từ khóa, đoạn trích, gợi ý ưu tiên đọc
  out/keyword_density.csv      -> số lần khớp / 10.000 từ theo (ngân hàng, năm, tiêu chí) - chỉ dùng kiểm tra độ nhạy
Cách dùng: python 03_locate_evidence.py [--bank tcb] [--year 2024] [--only-lang vi|en] [--context 220] [--exact]"""
import csv, json, re, sys, collections
from common import *

ctx = int(sys.argv[sys.argv.index("--context") + 1]) if "--context" in sys.argv else 220
KW = load_yaml("keywords.yaml")
ACTION = re.compile(r"triển khai|ra mắt|vận hành|ký kết|hoàn thành|đưa vào|áp dụng|thử nghiệm|xây dựng|nâng cấp|chứng nhận|đạt chuẩn"
                    r"|launched|deployed|implemented|went live|rolled out|introduced|completed|certified|piloted|upgraded|signed|partnered|established", re.I)
NUM = re.compile(r"\d[\d.,]*\s*(%|triệu|tỷ|nghìn|ngàn|lượt|khách hàng|giờ|người|quy trình|API|đối tác|million|billion|trillion|customers|users|hours|employees|staff|partners|transactions|processes|VND)", re.I)
MULTI = re.compile(r"20\d\d.{0,40}20\d\d")  # nhiều năm gần nhau -> có số liệu đa kỳ (gợi ý)

EXACT = "--exact" in sys.argv   # tắt chế độ chịu lỗi khoảng trắng thừa (mặc định bật)
PAT = {c: [(k, compile_kw(k, EXACT)) for k in v["keywords"]] for c, v in KW.items()}

cand = []; hits = collections.Counter(); words = collections.Counter()
for jf in sorted((DATA / "text").glob("*.jsonl")):
    for line in open(jf, encoding="utf8"):
        d = json.loads(line); t = d["text"]; key = (d["bank"], d["year"])
        if d["doc_type"] not in ("bctn", "bcptbv", "web", "other"): continue
        if not keep(d["bank"], d["year"], d["doc_type"]) or not keep_lang(d.get("lang")): continue
        words[key] += len(t.split())
        flat = re.sub(r"\s+", " ", t)
        for c, pats in PAT.items():
            last_end = -10**9
            spans = []
            for k, rx in pats:
                for m in rx.finditer(flat): spans.append((m.start(), m.end(), k))
            spans.sort()
            for s, e, k in spans:
                hits[(d["bank"], d["year"], c)] += 1
                if s < last_end + ctx: continue           # gộp các hit gần nhau thành một đoạn
                last_end = e
                snip = flat[max(0, s - ctx): e + ctx]
                prio = 1 + bool(ACTION.search(snip)) + 2 * bool(NUM.search(snip)) + bool(MULTI.search(snip))
                cand.append([c, d["bank"], d["year"], d["doc_type"], d["page"], k, snip, prio,
                             str((DATA / "raw" / d["bank"] / f"{d['year']}_{d['doc_type']}.pdf").relative_to(ROOT)), d.get("lang") or "vi"])
cand.sort(key=lambda r: (r[0], r[1], r[2], -r[7]))
with open(OUT / "evidence_candidates.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["criterion", "bank", "year", "doc_type", "page", "keyword", "snippet", "read_priority(1-5)", "source_file", "lang"]); w.writerows(cand)
with open(OUT / "keyword_density.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["bank", "year", "criterion", "hits", "words", "hits_per_10k_words"])
    for (b, y, c), n in sorted(hits.items()):
        wd = words[(b, y)]; w.writerow([b, y, c, n, wd, round(n / wd * 1e4, 2) if wd else ""])
print(len(cand), "đoạn ứng viên ->", OUT / "evidence_candidates.csv")
print("Lưu ý: 'read_priority' chỉ là gợi ý thứ tự đọc, KHÔNG phải điểm. Điểm do người chấm quyết định theo codebook.")
