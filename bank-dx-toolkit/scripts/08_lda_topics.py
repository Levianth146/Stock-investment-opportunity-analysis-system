"""LDA TOPIC MODELING trên báo cáo (BCTN + BCPTBV): khám phá chủ đề, KHÔNG thay rubric chấm tay.

Ý tưởng: cắt mỗi báo cáo thành các đoạn ~120 từ, huấn luyện LDA trên toàn bộ đoạn của cả 5 ngân hàng x các năm,
rồi (1) xem mỗi ngân hàng-năm dành bao nhiêu % nội dung cho từng chủ đề, (2) gán chủ đề vào 6 trụ cột DBI bằng độ trùng
với từ điển config/keywords.yaml, (3) so sánh tỷ trọng nội dung theo trụ cột giữa các ngân hàng.

Các bước kiểm soát chất lượng có sẵn:
  - quét K (số chủ đề) bằng độ nhất quán UMass + perplexity (out/lda_k_scan.csv); chọn K bằng mắt đọc top từ, không chỉ theo số.
  - chạy nhiều seed, đo độ ổn định chủ đề (Jaccard top-15 từ giữa các seed) -> chủ đề không ổn định thì bỏ qua.
  - chủ đề không trùng từ điển trụ cột nào được xếp 'khác' (không ép vào trụ cột).

Cách dùng (thư mục scripts/):
  python 08_lda_topics.py [--k 12] [--kmin 6 --kmax 16 --kstep 2] [--seeds 5] [--chunk 120] [--segment]
  --segment : tách từ ghép tiếng Việt bằng pyvi (cải thiện chủ đề; cần pip install pyvi). Mặc định dùng unigram + bigram.
Đầu ra (out/): lda_k_scan.csv, lda_topics.csv, lda_topic_pillar.csv, lda_bank_topic_share.csv, lda_bank_pillar_share.csv
GIỚI HẠN: chủ đề là công cụ khám phá; n = 5 ngân hàng, chỉ mô tả. Tỷ trọng nội dung != mức độ triển khai."""
import collections, json, math, re, sys
import numpy as np, pandas as pd
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer
from common import *

def arg(name, default, cast=float):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default
CHUNK, SEEDS = arg("--chunk", 120, int), arg("--seeds", 5, int)
K_FIX = arg("--k", 0, int); KMIN, KMAX, KSTEP = arg("--kmin", 8, int), arg("--kmax", 20, int), arg("--kstep", 2, int)
SEGMENT = "--segment" in sys.argv
KW = load_yaml("keywords.yaml")
PILLAR = {"K": "Khách hàng", "S": "Chiến lược", "T": "Công nghệ", "O": "Vận hành", "C": "Văn hóa", "D": "Dữ liệu"}
STOP = set("""và của các là có được cho với trong một những này đã không để từ tại theo về như khi năm người hơn đến ra vào trên cũng sẽ
tiếp tục đồng tỷ triệu ngân hàng bank thành phố việt nam công ty cổ phần tổng số hoạt động thực hiện đạt tăng so với cùng kỳ
nhằm đồng thời hiện đang tới qua vẫn rất nhiều còn lên mà thì ở nên bởi báo cáo thường niên năm_ hội đồng quản trị
the of and to in for with on by is are we our page trang""".split())

def words(t):
    t = nfc(t).lower()
    if SEGMENT:
        from pyvi import ViTokenizer
        t = ViTokenizer.tokenize(t)
    return [w for w in re.findall(r"[^\W\d]+(?:_[^\W\d]+)*", t) if len(w) > 1 and w not in STOP]

# ---- 1) nạp, cắt đoạn
chunks, meta = [], []
SKIPPED = set()
for jf in sorted((DATA / "text").glob("*.jsonl")):
    for line in open(jf, encoding="utf8"):
        d = json.loads(line)
        if d["doc_type"] not in ("bctn", "bcptbv", "other"): continue
        if not keep(d["bank"], d["year"], d["doc_type"]): continue
        if not keep_lang(d.get("lang"), "vi"): SKIPPED.add((d["bank"], d["year"], d.get("lang"))); continue
        buf, n = [], 0
        for para in re.split(r"\n\s*\n|(?<=[.;])\n", d["text"]):
            w = words(para)
            if not w: continue
            buf.append(w); n += len(w)
            if n >= CHUNK:
                chunks.append(" ".join(x for b in buf for x in b)); meta.append((d["bank"], d["year"])); buf, n = [], 0
        if n >= CHUNK // 3:
            chunks.append(" ".join(x for b in buf for x in b)); meta.append((d["bank"], d["year"]))
if SKIPPED: print(f"Bỏ qua {len(SKIPPED)} văn bản không phải tiếng Việt (LDA này dùng stopword tiếng Việt): {sorted(SKIPPED)[:8]}... LDA này chỉ hỗ trợ tiếng Việt; dùng bước 07 cho tiếng Anh.")
if len(chunks) < 50: sys.exit(f"Chỉ có {len(chunks)} đoạn; cần ít nhất vài trăm đoạn (báo cáo thật ~ hàng nghìn). Chạy bước 1-2 trước.")
meta = pd.DataFrame(meta, columns=["bank", "year"])
print(f"{len(chunks)} đoạn từ {meta.drop_duplicates().shape[0]} văn bản (ngân hàng-năm)")

cv = CountVectorizer(ngram_range=(1, 2), min_df=max(3, int(0.002 * len(chunks))), max_df=0.6, token_pattern=r"\S+")
X = cv.fit_transform(chunks); vocab = np.array(cv.get_feature_names_out())
print(f"Từ vựng: {len(vocab)} cụm 1-2 từ")

def umass(model, X, topn=10):
    """UMass coherence: dùng đồng xuất hiện trong chính tập đoạn (càng gần 0 càng nhất quán)."""
    Xb = (X > 0).astype(np.float64).tocsc(); df = np.asarray(Xb.sum(0)).ravel(); sc = []
    for comp in model.components_:
        top = np.argsort(comp)[::-1][:topn]; s = 0.0
        for i in range(1, len(top)):
            for j in range(i):
                co = Xb[:, top[i]].multiply(Xb[:, top[j]]).sum()
                s += math.log((co + 1) / df[top[j]])
        sc.append(s / (topn * (topn - 1) / 2))
    return float(np.mean(sc))

def fit(k, seed): return LatentDirichletAllocation(n_components=k, random_state=seed, learning_method="batch", max_iter=60, doc_topic_prior=1.0 / k, topic_word_prior=0.01, n_jobs=-1).fit(X)

# ---- 2) quét K
if K_FIX: K = K_FIX
else:
    scan = []
    for k in range(KMIN, KMAX + 1, KSTEP):
        m = fit(k, 0); scan.append([k, round(umass(m, X), 3), round(m.perplexity(X), 1)]); print("  K =", scan[-1])
    sdf = pd.DataFrame(scan, columns=["K", "umass_coherence", "perplexity"]); sdf.to_csv(OUT / "lda_k_scan.csv", index=False, encoding="utf-8-sig")
    K = int(sdf.sort_values("umass_coherence", ascending=False).iloc[0]["K"])
    print(f"-> K = {K} theo UMass cao nhất (đọc lda_topics.csv và điều chỉnh bằng --k nếu chủ đề khó hiểu)")

# ---- 3) nhiều seed -> độ ổn định
models = [fit(K, s) for s in range(SEEDS)]
tops = [[set(vocab[np.argsort(c)[::-1][:15]]) for c in m.components_] for m in models]
stab = []
for i in range(K):
    js = [max(len(tops[0][i] & o) / len(tops[0][i] | o) for o in tops[s]) for s in range(1, SEEDS)] if SEEDS > 1 else [np.nan]
    stab.append(round(float(np.mean(js)), 3))
M = models[0]; theta = M.transform(X)
beta = M.components_ / M.components_.sum(1, keepdims=True)

# ---- 4) mô tả chủ đề + gán trụ cột theo độ trùng từ điển
KWSYL = {c: [(k, [x for x in re.findall(r"[^\W\d_]+", nfc(k).lower()) if len(x) > 1]) for k in v["keywords"]] for c, v in KW.items()}
rows, maprows = [], []
share = theta.sum(0) / theta.sum()
for i in range(K):
    order = np.argsort(beta[i])[::-1][:40]; terms = vocab[order]; w = beta[i][order]; w = w / w.sum()
    syl = collections.defaultdict(float)             # trọng số theo âm tiết: khớp được cả khi từ ghép bị tách / không tách
    for t, wi in zip(terms, w):
        for x in re.findall(r"[^\W\d_]+", t): syl[x] = max(syl[x], wi)
    pil = collections.Counter(); crit = collections.Counter(); nkw = collections.Counter()
    for c, lst in KWSYL.items():
        for kw, sy in lst:
            if sy and all(x in syl for x in sy):
                crit[c] += sum(syl[x] for x in sy) / len(sy); pil[c[0]] += sum(syl[x] for x in sy) / len(sy); nkw[c[0]] += 1
    best = pil.most_common(1)
    assigned = PILLAR[best[0][0]] if best and nkw[best[0][0]] >= 2 else "khác"     # cần >= 2 từ khóa khác nhau trùng
    rows.append({"topic": i, "share_of_text": round(float(share[i]), 3), "stability": stab[i], "assigned_pillar": assigned,
                 "keyword_overlap": round(best[0][1], 3) if best else 0, "n_keywords_matched": nkw[best[0][0]] if best else 0,
                 "top_terms": ", ".join(terms[:12])})
    for c, v in crit.most_common(3): maprows.append([i, c, round(v, 3)])
tp = pd.DataFrame(rows); tp.to_csv(OUT / "lda_topics.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(maprows, columns=["topic", "criterion", "overlap_weight"]).to_csv(OUT / "lda_topic_pillar.csv", index=False, encoding="utf-8-sig")

# ---- 5) tỷ trọng chủ đề theo ngân hàng-năm, rồi theo trụ cột
th = pd.DataFrame(theta, columns=[f"topic_{i}" for i in range(K)]); th[["bank", "year"]] = meta
bt = th.groupby(["bank", "year"]).mean().round(4).reset_index(); bt.to_csv(OUT / "lda_bank_topic_share.csv", index=False, encoding="utf-8-sig")
bp = pd.DataFrame({"bank": bt["bank"], "year": bt["year"]})
for p in list(PILLAR.values()) + ["khác"]:
    cols = [f"topic_{r.topic}" for r in tp.itertuples() if r.assigned_pillar == p]
    bp[p] = (bt[cols].sum(axis=1) * 100).round(1) if cols else 0.0
bp.to_csv(OUT / "lda_bank_pillar_share.csv", index=False, encoding="utf-8-sig")
print("\nTop chủ đề:\n", tp.sort_values("share_of_text", ascending=False).head(10)[["topic", "share_of_text", "stability", "assigned_pillar", "top_terms"]].to_string(index=False))
print("\nTỷ trọng nội dung theo trụ cột (% đoạn văn):\n", bp.to_string(index=False))
low = tp[tp.stability < 0.4]
if len(low): print(f"\nCảnh báo: {len(low)} chủ đề kém ổn định (Jaccard < 0,4 giữa các seed) -> {list(low.topic)}; đừng diễn giải.")
print("Lưu ý: tỷ trọng chủ đề là 'báo cáo viết nhiều về gì', không phải điểm DBI.")
