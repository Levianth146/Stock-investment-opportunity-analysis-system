"""TEXT MINING trên báo cáo (BCTN + BCPTBV) cho 6 trụ cột / 24 tiêu chí.
Chạy sau bước 2 (đã có data/text/*.jsonl). Mỗi (ngân hàng, năm) = một "văn bản" gộp BCTN + BCPTBV.

Các phép đo (đều là CHỈ SỐ PHỤ, dùng đối chiếu/kiểm tra độ nhạy; điểm chính vẫn là rubric thuật toán 09c):
  1. BM25 theo từ điển: tần suất từ khóa có bão hòa (k1) và chuẩn hóa độ dài văn bản (b), nhân IDF
     -> giảm ảnh hưởng báo cáo dài/ lặp từ. Tổng hợp theo tiêu chí, trụ cột; chuẩn hóa 0-100 (min-max toàn bộ văn bản).
  2. Độ phủ từ vựng (coverage): tỷ lệ từ khóa khác nhau xuất hiện / tổng từ khóa của tiêu chí -> chống 'lặp một từ nhiều lần'.
  3. Tỷ lệ định lượng hóa: trong các câu chứa từ khóa, tỷ lệ câu có con số + đơn vị -> phân biệt 'nói' với 'có số liệu'.
  4. TF-IDF cụm 1-2 từ đặc trưng của từng ngân hàng-năm (khám phá, tìm chủ đề nổi bật).
  5. Mở rộng từ điển: cụm từ hay đi cùng từ khóa gốc (log-odds) -> ứng viên từ khóa mới, người dùng duyệt thủ công.
  6. So sánh với điểm thuật toán (out/coding_auto.xlsx): tương quan hạng Spearman theo trụ cột/năm.

Cách dùng: python 07_text_mining.py [--bank tcb,mb] [--year 2024] [--only-lang vi|en] [--k1 1.2] [--b 0.75] [--expand] [--compare] [--exact]
Đầu ra (thư mục out/): tm_criterion.csv, tm_pillar.csv, tm_tfidf_terms.csv, tm_dictionary_expansion.csv, tm_vs_dbi.csv"""
import collections, csv, json, math, re, sys
import pandas as pd
from common import *

arg = lambda name, default: float(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default
K1, B = arg("--k1", 1.2), arg("--b", 0.75)
EXACT = "--exact" in sys.argv
KW = load_yaml("keywords.yaml")
PILLAR = {"K": "Khách hàng", "S": "Chiến lược", "T": "Công nghệ", "O": "Vận hành", "C": "Văn hóa", "D": "Dữ liệu"}
NUM = re.compile(r"\d[\d.,]*\s*(%|triệu|tỷ|nghìn|ngàn|lượt|khách hàng|giờ|người|quy trình|API|đối tác|giao dịch|tài khoản|robot|million|billion|trillion|customers|users|hours|employees|staff|partners|transactions|processes|VND)", re.I)
SENT = re.compile(r"(?<=[.;!?])\s+|\n{2,}")
STOP = set("""và của các là có được cho với trong một những này đã không để từ tại theo về như khi năm người hơn đến ra vào trên cũng sẽ
tiếp tục đồng tỷ triệu ngân hàng bank thành phố việt nam công ty cổ phần tổng số hoạt động thực hiện đạt tăng so với cùng kỳ
the of and to in for with on by is are we our nhằm đồng thời trong năm hiện đang tới qua các_ vẫn rất nhiều còn lên mà thì ở nên bởi""".split())

# ---- 1) nạp văn bản
docs = {}   # (bank, year, lang) -> text; không gộp chéo ngôn ngữ
for jf in sorted((DATA / "text").glob("*.jsonl")):
    for line in open(jf, encoding="utf8"):
        d = json.loads(line)
        if d["doc_type"] not in ("bctn", "bcptbv", "other"): continue
        if not keep(d["bank"], d["year"], d["doc_type"]) or not keep_lang(d.get("lang")): continue
        docs.setdefault((d["bank"], d["year"], d.get("lang") or "vi"), []).append(d["text"])
docs = {k: re.sub(r"[ \t]+", " ", "\n".join(v)) for k, v in docs.items()}
if not docs:
    sys.exit("Chưa có data/text/*.jsonl loại bctn/bcptbv. Chạy bước 1-2 trước.")
keys = sorted(docs); N = len(keys)
LANG = {k: k[2] for k in keys}
if len(set(LANG.values())) > 1:
    print("CẢNH BÁO: tập văn bản lẫn nhiều ngôn ngữ:", dict(collections.Counter(LANG.values())),
          "-> điểm text mining chỉ so sánh được trong cùng ngôn ngữ (đã chuẩn hóa 0-100 riêng từng ngôn ngữ); đừng xếp hạng chéo.")
wlen = {k: max(len(docs[k].split()), 1) for k in keys}
n_lang = collections.Counter(LANG.values())
avgdl = {lang: sum(wlen[k] for k in keys if LANG[k] == lang) / count for lang, count in n_lang.items()}
print(f"{N} văn bản (ngân hàng-năm-ngôn ngữ); độ dài TB riêng từng ngôn ngữ: {avgdl}")

# ---- 2) tần suất từ khóa theo văn bản
PAT = {c: [(k, compile_kw(k, EXACT)) for k in v["keywords"]] for c, v in KW.items()}
tf = {}                                  # (doc, crit, kw) -> count
sent_hits = collections.defaultdict(lambda: [0, 0])   # (doc, crit) -> [số câu chứa từ khóa, số câu có số liệu]
for k in keys:
    sents = [re.sub(r"\s+", " ", s).strip() for s in SENT.split(docs[k])]
    sents = [s for s in sents if len(s) > 20]
    for c, pats in PAT.items():
        for kw, rx in pats:
            n = len(rx.findall(docs[k]))
            if n: tf[(k, c, kw)] = n
        for s in sents:
            if any(rx.search(s) for _, rx in pats):
                sent_hits[(k, c)][0] += 1
                if NUM.search(s): sent_hits[(k, c)][1] += 1
df = collections.Counter(); 
for (k, c, kw), n in tf.items(): df[(LANG[k], c, kw)] += 1
idf = lambda lang, c, kw: math.log(1 + (n_lang[lang] - df[(lang, c, kw)] + 0.5) / (df[(lang, c, kw)] + 0.5))

# ---- 3) BM25, độ phủ, tỷ lệ định lượng theo tiêu chí
rows = []
for k in keys:
    norm = K1 * (1 - B + B * wlen[k] / avgdl[LANG[k]])
    for c, v in KW.items():
        bm = sum(idf(LANG[k], c, kw) * tf[(k, c, kw)] * (K1 + 1) / (tf[(k, c, kw)] + norm) for kw in v["keywords"] if (k, c, kw) in tf)
        hit_kw = [kw for kw in v["keywords"] if (k, c, kw) in tf]
        raw = sum(tf[(k, c, kw)] for kw in hit_kw)
        ns, nn = sent_hits[(k, c)]
        rows.append({"bank": k[0], "year": k[1], "lang": LANG[k], "criterion": c, "pillar": PILLAR[c[0]], "bm25": round(bm, 4), "raw_hits": raw,
                     "coverage": round(len(hit_kw) / len(v["keywords"]), 3), "distinct_kw": len(hit_kw),
                     "sentences_with_kw": ns, "quantified_ratio": round(nn / ns, 3) if ns else None,
                     "hits_per_10k_words": round(raw / wlen[k] * 1e4, 2), "words": wlen[k]})
crit = pd.DataFrame(rows); crit.to_csv(OUT / "tm_criterion.csv", index=False, encoding="utf-8-sig")

# ---- 4) tổng hợp trụ cột, chuẩn hóa 0-100
g = crit.groupby(["bank", "year", "pillar", "lang"]).agg(bm25=("bm25", "mean"), coverage=("coverage", "mean"),
        sent=("sentences_with_kw", "sum"), q=("quantified_ratio", "mean")).reset_index()
def mm(s): return (s - s.min()) / (s.max() - s.min()) * 100 if s.max() > s.min() else s * 0
g["bm25_0_100"] = g.groupby(["pillar", "lang"])["bm25"].transform(mm).round(1)
g["coverage_0_100"] = (g["coverage"] * 100).round(1)
g = g.rename(columns={"q": "quantified_ratio_mean"}); g["quantified_ratio_mean"] = g["quantified_ratio_mean"].round(3)
g.to_csv(OUT / "tm_pillar.csv", index=False, encoding="utf-8-sig")
tot = g.groupby(["bank", "year", "lang"]).agg(bm25_0_100=("bm25_0_100", "mean"), coverage_0_100=("coverage_0_100", "mean")).round(1).reset_index()
print("\nChỉ số text mining tổng hợp (TB 6 trụ cột; chỉ để đối chiếu, KHÔNG phải điểm DBI):\n", tot.to_string(index=False))

# ---- 5) TF-IDF cụm 1-2 từ đặc trưng
def toks(t):
    w = [x for x in re.findall(r"[^\W\d_]+", nfc(t).lower()) if len(x) > 1]
    uni = [x for x in w if x not in STOP]
    bi = [f"{a} {b}" for a, b in zip(w, w[1:]) if a not in STOP and b not in STOP]
    return collections.Counter(uni + bi)
TF = {k: toks(docs[k]) for k in keys}; dfreq = collections.Counter()
for k in keys: dfreq.update((LANG[k], term) for term in TF[k])
out = []
for k in keys:
    L = sum(TF[k].values()); sc = {t: (n / L) * math.log((1 + n_lang[LANG[k]]) / (1 + dfreq[(LANG[k], t)])) for t, n in TF[k].items() if n >= 3}
    for rank, (t, s) in enumerate(sorted(sc.items(), key=lambda x: -x[1])[:25], 1): out.append([k[0], k[1], LANG[k], rank, t, TF[k][t], round(s * 1e4, 3)])
pd.DataFrame(out, columns=["bank", "year", "lang", "rank", "term", "count", "tfidf_x1e4"]).to_csv(OUT / "tm_tfidf_terms.csv", index=False, encoding="utf-8-sig")

# ---- 6) mở rộng từ điển
if "--expand" in sys.argv:
    known = {nfc(kw).lower() for v in KW.values() for kw in v["keywords"]}
    allpats = [rx for pats in PAT.values() for _, rx in pats]
    all_candidates = []
    for lang in sorted(n_lang):
        lang_keys = [k for k in keys if LANG[k] == lang]
        win = collections.Counter(); corp = collections.Counter()
        for k in lang_keys:
            txt = re.sub(r"\s+", " ", docs[k]); corp.update(toks(txt))
            spans = []
            for rx in allpats:
                for m in rx.finditer(txt):
                    a, b = max(0, m.start() - 120), min(len(txt), m.end() + 120)
                    if a > 0 and txt[a - 1] != " ": a = (txt.find(" ", a) + 1) or a     # bỏ từ bị cắt dở ở mép cửa sổ
                    if b < len(txt) and txt[b] != " ":
                        r = txt.rfind(" ", a, b); b = r if r > m.end() else m.end()
                    spans.append([a, b])
            spans.sort(); merged = []
            for a, b in spans:                       # gộp cửa sổ chồng nhau để mỗi đoạn chỉ đếm 1 lần
                if merged and a <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], b)
                else: merged.append([a, b])
            for a, b in merged: win.update(toks(txt[a:b]))
        W = sum(win.values()); C = sum(corp.values()); cand = []
        for t, n in win.items():
            if n < 3 or t in known or any(f" {kk} " in f" {t} " or f" {t} " in f" {kk} " for kk in known): continue   # so khớp theo ranh giới từ, không theo chuỗi con
            ct = max(corp[t], n)   # cụm bị cắt ở mép cửa sổ có thể không có trong toàn văn
            lo = math.log((n / W) / (ct / C))
            if lo > 0: cand.append((lang, t, n, ct, round(lo, 3)))
        cand = sorted(cand, key=lambda x: -(x[4] * math.log(1 + x[2])))[:150]
        all_candidates.extend(cand)
    pd.DataFrame(all_candidates, columns=["lang", "term", "count_near_keywords", "count_corpus", "log_odds"]).to_csv(OUT / "tm_dictionary_expansion.csv", index=False, encoding="utf-8-sig")
    print("\nỨng viên từ khóa mới ->", OUT / "tm_dictionary_expansion.csv", "(duyệt thủ công rồi thêm vào config/keywords.yaml)")

# ---- 7) so sánh với điểm thuật toán
if "--compare" in sys.argv:
    xl = OUT / "coding_auto.xlsx"
    if not xl.exists(): sys.exit("Thiếu out/coding_auto.xlsx: chạy 09c_auto_score.py trước khi --compare.")
    cs = pd.read_excel(xl)
    cs["score"] = pd.to_numeric(cs["final"], errors="coerce")
    cs = cs.dropna(subset=["score"]); cs["pillar"] = cs["criterion"].str[0].map(PILLAR); cs["year"] = cs["year"].astype(str)
    man = cs.groupby(["bank", "year", "pillar"])["score"].mean().div(4).mul(100).rename("dbi_0_100").reset_index()
    g2 = g.copy(); g2["year"] = g2["year"].astype(str)
    mg = man.merge(g2[["bank", "year", "pillar", "lang", "bm25_0_100", "coverage_0_100"]], on=["bank", "year", "pillar"])
    res = []
    for (y, p, lang), sub in mg.groupby(["year", "pillar", "lang"]):
        if len(sub) >= 3:
            res.append([y, p, lang, len(sub), round(sub["dbi_0_100"].rank().corr(sub["bm25_0_100"].rank()), 3), round(sub["dbi_0_100"].rank().corr(sub["coverage_0_100"].rank()), 3)])
    allr = []
    for (y, lang), sub in mg.groupby(["year", "lang"]):
        a = sub.groupby("bank")[["dbi_0_100", "bm25_0_100", "coverage_0_100"]].mean()
        if len(a) >= 3: allr.append([y, "TẤT CẢ TRỤ", lang, len(a), round(a["dbi_0_100"].rank().corr(a["bm25_0_100"].rank()), 3), round(a["dbi_0_100"].rank().corr(a["coverage_0_100"].rank()), 3)])
    pd.DataFrame(allr + res, columns=["year", "pillar", "lang", "n_banks", "spearman_dbi_vs_bm25", "spearman_dbi_vs_coverage"]).to_csv(OUT / "tm_vs_dbi.csv", index=False, encoding="utf-8-sig")
    mg.to_csv(OUT / "tm_vs_dbi_detail.csv", index=False, encoding="utf-8-sig")
    print("\nTương quan hạng điểm thuật toán vs text mining ->", OUT / "tm_vs_dbi.csv")
    print("Lưu ý: n = 5 ngân hàng, chỉ mô tả; tương quan thấp nghĩa là báo cáo 'nói nhiều' không đồng nghĩa 'làm nhiều' hoặc ngược lại -> cần đọc lại bằng chứng.")
