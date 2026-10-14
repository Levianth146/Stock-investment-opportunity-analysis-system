"""PHOBERT: (A) lọc câu bằng chứng sai bằng bộ phân loại tinh chỉnh, (B) gợi ý mức rubric bằng neo ngữ nghĩa.

Vì sao dùng: từ khóa bắt được rất nhiều câu "trúng chữ, trật nghĩa" (vd 'cloud' trong câu quảng cáo). PhoBERT đọc cả câu
nên lọc được phần lớn các trường hợp này, SAU KHI bạn đã chấm tay đủ nhiều câu để dạy nó. Điểm cuối vẫn do người chấm theo rubric.

Các chế độ (chạy riêng từng cái):
  --build-train   Đọc out/evidence_candidates.csv (bạn điền thêm cột `valid` = 1 nếu câu đúng là bằng chứng của tiêu chí đó, 0 nếu sai)
                  -> out/phobert_train.csv (text, label = mã tiêu chí hoặc 'none').
  --finetune      Tinh chỉnh PhoBERT trên out/phobert_train.csv. Có CV phân tầng (--cv 5) báo macro-F1 TRƯỚC khi huấn luyện mô hình cuối.
                  Lưu models/phobert_evidence/. Cần >= ~30 câu/tiêu chí cho kết quả đáng tin; ít hơn thì chỉ dùng tham khảo.
  --predict       Chạy mô hình trên mọi câu chứa từ khóa trong data/text -> out/phobert_predictions.csv và phobert_evidence_counts.csv
                  (số câu được xác nhận theo tiêu chí x ngân hàng x năm, với ngưỡng --tau 0.7).
  --anchors       KHÔNG cần dữ liệu huấn luyện: nhúng các câu chứa từ khóa và 96 mô tả mức rubric (config/rubric_anchors.csv),
                  gán mỗi câu vào mức gần nhất theo cosine -> out/phobert_anchor_suggestions.csv (gợi ý cho người chấm).
                  Embedding PhoBERT thô không được huấn luyện cho độ tương đồng câu, nên chất lượng thấp hơn --finetune. Chỉ dùng để gợi ý.

Chỉ xử lý văn bản tiếng Việt (cột lang trong data/text); văn bản tiếng Anh bị bỏ qua, xem 07 cho BM25/coverage song ngữ.
Lọc: --bank tcb --year 2024 --only-lang vi.
Tham số: --model vinai/phobert-base-v2 (hoặc đường dẫn thư mục local) --maxlen 256 --epochs 4 --bs 16 --lr 2e-5 --cv 5 --tau 0.7 --max-sent 20000
         --no-segment (bỏ tách từ; PhoBERT được huấn luyện trên văn bản đã tách từ nên mặc định tách bằng pyvi)
Yêu cầu: pip install torch transformers pyvi scikit-learn (cần mạng để tải model lần đầu; máy có GPU thì nhanh hơn nhiều)."""
import collections, csv, json, re, sys
import numpy as np, pandas as pd
from common import *

def arg(name, default, cast=str):
    return cast(sys.argv[sys.argv.index(name) + 1]) if name in sys.argv else default
MODEL = arg("--model", "vinai/phobert-base-v2"); MAXLEN = arg("--maxlen", 256, int); EPOCHS = arg("--epochs", 4, int)
BS = arg("--bs", 16, int); LR = arg("--lr", 2e-5, float); CVK = arg("--cv", 5, int); TAU = arg("--tau", 0.7, float)
MAXS = arg("--max-sent", 20000, int); SEG = "--no-segment" not in sys.argv
MODEL_DIR = ROOT / "models" / "phobert_evidence"
KW = load_yaml("keywords.yaml"); EXACT = "--exact" in sys.argv
SENT = re.compile(r"(?<=[.;!?])\s+|\n{2,}")

_vt = None
def seg(t):
    global _vt
    t = re.sub(r"\s+", " ", nfc(t)).strip()
    if not SEG: return t
    if _vt is None:
        try:
            from pyvi import ViTokenizer; _vt = ViTokenizer.tokenize
        except ImportError:
            print("Cảnh báo: thiếu pyvi, bỏ qua tách từ (kết quả kém hơn). pip install pyvi"); _vt = lambda x: x
    return _vt(t)

def libs():
    try:
        import torch, transformers
    except ImportError: sys.exit("Thiếu torch/transformers: pip install torch transformers")
    return torch, transformers

def keyword_sentences():
    """Mọi câu chứa >= 1 từ khóa: (bank, year, doc_type, page, criterion, keyword, sentence)."""
    PAT = {c: [(k, compile_kw(k, EXACT)) for k in v["keywords"]] for c, v in KW.items()}; out = []; skipped = set()
    for jf in sorted((DATA / "text").glob("*.jsonl")):
        for line in open(jf, encoding="utf8"):
            d = json.loads(line)
            if d["doc_type"] not in ("bctn", "bcptbv", "other"): continue
            if not keep(d["bank"], d["year"], d["doc_type"]): continue
            if not keep_lang(d.get("lang"), "vi"): skipped.add((d["bank"], d["year"])); continue   # PhoBERT chỉ cho tiếng Việt
            for s in SENT.split(d["text"]):
                s = re.sub(r"\s+", " ", s).strip()
                if len(s) < 25 or len(s) > 700: continue
                for c, pats in PAT.items():
                    for kw, rx in pats:
                        if rx.search(s): out.append((d["bank"], d["year"], d["doc_type"], d["page"], c, kw, s)); break
    if skipped: print(f"Bỏ qua {len(skipped)} văn bản không phải tiếng Việt (PhoBERT chỉ dành cho tiếng Việt): {sorted(skipped)[:8]}")
    return out[:MAXS]

def batches(items, bs):
    for i in range(0, len(items), bs): yield items[i:i + bs]

def encode(tok, texts, torch, dev):
    e = tok([seg(t) for t in texts], padding=True, truncation=True, max_length=MAXLEN, return_tensors="pt")
    return {k: v.to(dev) for k, v in e.items()}

# ---------------------------------------------------------------- build-train
if "--build-train" in sys.argv:
    p = OUT / "evidence_candidates.csv"
    if not p.exists(): sys.exit("Thiếu out/evidence_candidates.csv (chạy 03_locate_evidence.py rồi điền cột valid)")
    ev = pd.read_csv(p)
    if "valid" not in ev.columns: sys.exit("Thêm cột `valid` (1 = bằng chứng đúng của tiêu chí; 0 = sai) vào evidence_candidates.csv rồi chạy lại")
    if "lang" not in ev:
        sys.exit("Thiếu cột lang: chạy lại bước 03 và gắn nhãn valid để bảo đảm dữ liệu huấn luyện tiếng Việt.")
    ev = ev[ev["lang"].map(lambda lang: keep_lang(lang, "vi")).astype(bool)].copy()
    selected = pd.Series((keep(r.bank, r.year, getattr(r, "doc_type", None)) for r in ev.itertuples()),
                         index=ev.index, dtype=bool)
    ev = ev.loc[selected]
    ev = ev[ev["valid"].isin([0, 1])].copy()
    ev["label"] = np.where(ev["valid"] == 1, ev["criterion"], "none"); ev["text"] = ev["snippet"].astype(str)
    ev[["text", "label", "criterion", "bank", "year", "lang"]].to_csv(OUT / "phobert_train.csv", index=False, encoding="utf-8-sig")
    print(ev["label"].value_counts().to_string()); print("-> out/phobert_train.csv")

# ---------------------------------------------------------------- finetune
def train_model(tr_texts, tr_y, n_labels, torch, transformers, dev, seed=0):
    torch.manual_seed(seed); np.random.seed(seed)
    tok = transformers.AutoTokenizer.from_pretrained(MODEL)
    model = transformers.AutoModelForSequenceClassification.from_pretrained(MODEL, num_labels=n_labels).to(dev)
    # trọng số lớp để bù mất cân bằng ('none' thường nhiều hơn hẳn)
    cnt = np.bincount(tr_y, minlength=n_labels).astype(float); wt = torch.tensor(np.where(cnt > 0, cnt.sum() / (n_labels * np.maximum(cnt, 1)), 0.0), dtype=torch.float, device=dev)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=0.01)
    steps = EPOCHS * ((len(tr_texts) + BS - 1) // BS); sched = transformers.get_linear_schedule_with_warmup(opt, int(0.1 * steps), steps)
    lossf = torch.nn.CrossEntropyLoss(weight=wt); idx = np.arange(len(tr_texts)); model.train()
    for ep in range(EPOCHS):
        np.random.shuffle(idx); tot = 0.0
        for b in batches(list(idx), BS):
            enc = encode(tok, [tr_texts[i] for i in b], torch, dev); y = torch.tensor([tr_y[i] for i in b], device=dev)
            loss = lossf(model(**enc).logits, y); loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sched.step(); opt.zero_grad(); tot += loss.item() * len(b)
        print(f"    epoch {ep + 1}/{EPOCHS} loss {tot / len(tr_texts):.4f}")
    return tok, model

def predict_proba(tok, model, texts, torch, dev):
    model.eval(); P = []
    with torch.no_grad():
        for b in batches(texts, 32): P.append(torch.softmax(model(**encode(tok, b, torch, dev)).logits, -1).cpu().numpy())
    return np.vstack(P) if P else np.zeros((0, 1))

if "--finetune" in sys.argv:
    tr = pd.read_csv(OUT / "phobert_train.csv")
    if "lang" not in tr or tr.empty or not tr["lang"].eq("vi").all():
        sys.exit("Dữ liệu huấn luyện phải có lang=vi và có ít nhất một câu. Chạy lại --build-train.")
    torch, tf = libs(); dev = "cuda" if torch.cuda.is_available() else "cpu"; print("Thiết bị:", dev)
    labels = sorted(tr["label"].unique()); l2i = {l: i for i, l in enumerate(labels)}
    X = tr["text"].astype(str).tolist(); y = np.array([l2i[l] for l in tr["label"]])
    print(f"{len(X)} câu, {len(labels)} nhãn; số câu/nhãn nhỏ nhất = {np.bincount(y).min()}")
    if CVK >= 2 and np.bincount(y).min() >= CVK:
        from sklearn.metrics import f1_score
        from sklearn.model_selection import StratifiedKFold
        f1s = []
        for f, (a, b) in enumerate(StratifiedKFold(CVK, shuffle=True, random_state=0).split(X, y)):
            print(f"  Fold {f + 1}/{CVK}"); tok, m = train_model([X[i] for i in a], y[a], len(labels), torch, tf, dev, seed=f)
            pr = predict_proba(tok, m, [X[i] for i in b], torch, dev).argmax(1); f1s.append(f1_score(y[b], pr, average="macro")); print(f"    macro-F1 = {f1s[-1]:.3f}")
            del m
        print(f"CV macro-F1 = {np.mean(f1s):.3f} ± {np.std(f1s):.3f}  (dưới ~0,6 thì chưa đủ dữ liệu/nhãn quá mơ hồ -> chấm thêm câu, đừng dùng để lọc)")
    else: print("Bỏ qua CV (lớp nhỏ nhất ít hơn số fold hoặc --cv < 2). Mô hình cuối chưa có đánh giá độc lập.")
    tok, model = train_model(X, y, len(labels), torch, tf, dev)
    MODEL_DIR.mkdir(parents=True, exist_ok=True); model.save_pretrained(MODEL_DIR); tok.save_pretrained(MODEL_DIR)
    json.dump(labels, open(MODEL_DIR / "labels.json", "w", encoding="utf8"), ensure_ascii=False); print("Đã lưu", MODEL_DIR)

# ---------------------------------------------------------------- predict
if "--predict" in sys.argv:
    torch, tf = libs(); dev = "cuda" if torch.cuda.is_available() else "cpu"
    if not (MODEL_DIR / "labels.json").exists(): sys.exit("Chưa có mô hình: chạy --build-train rồi --finetune")
    labels = json.load(open(MODEL_DIR / "labels.json", encoding="utf8")); l2i = {l: i for i, l in enumerate(labels)}
    tok = tf.AutoTokenizer.from_pretrained(MODEL_DIR); model = tf.AutoModelForSequenceClassification.from_pretrained(MODEL_DIR).to(dev)
    cand = keyword_sentences(); print(len(cand), "câu chứa từ khóa")
    if not cand: sys.exit("Không có câu tiếng Việt chứa từ khóa với bộ lọc đã chọn.")
    P = predict_proba(tok, model, [c[6] for c in cand], torch, dev)
    rows = []
    for c, p in zip(cand, P):
        own = p[l2i[c[4]]] if c[4] in l2i else float("nan"); top = labels[int(p.argmax())]
        rows.append({"bank": c[0], "year": c[1], "doc_type": c[2], "page": c[3], "criterion": c[4], "keyword": c[5], "p_criterion": round(float(own), 3),
                     "p_none": round(float(p[l2i["none"]]), 3) if "none" in l2i else None, "top_label": top,
                     "accepted": bool(top == c[4] and own >= TAU), "sentence": c[6]})
    pr = pd.DataFrame(rows); pr.to_csv(OUT / "phobert_predictions.csv", index=False, encoding="utf-8-sig")
    cnt = pr.groupby(["criterion", "bank", "year"]).agg(keyword_sentences=("accepted", "size"), accepted_sentences=("accepted", "sum")).reset_index()
    cnt["accepted_ratio"] = (cnt["accepted_sentences"] / cnt["keyword_sentences"]).round(3)
    cnt.to_csv(OUT / "phobert_evidence_counts.csv", index=False, encoding="utf-8-sig")
    print(cnt.groupby("bank")[["keyword_sentences", "accepted_sentences"]].sum().to_string())
    print("-> out/phobert_predictions.csv, out/phobert_evidence_counts.csv. Đọc lại ~30 câu 'accepted' và ~30 câu bị loại để kiểm tra trước khi tin.")

# ---------------------------------------------------------------- anchors (zero-shot)
if "--anchors" in sys.argv:
    torch, tf = libs(); dev = "cuda" if torch.cuda.is_available() else "cpu"
    an = pd.read_csv(CONF / "rubric_anchors.csv"); cand = keyword_sentences(); print(len(cand), "câu chứa từ khóa;", len(an), "neo rubric")
    if not cand: sys.exit("Không có câu tiếng Việt chứa từ khóa với bộ lọc đã chọn.")
    tok = tf.AutoTokenizer.from_pretrained(MODEL); enc_model = tf.AutoModel.from_pretrained(MODEL).to(dev).eval()
    def embed(texts):
        E = []
        with torch.no_grad():
            for b in batches(texts, 32):
                e = encode(tok, b, torch, dev); h = enc_model(**e).last_hidden_state; m = e["attention_mask"].unsqueeze(-1).float()
                v = (h * m).sum(1) / m.sum(1); E.append(torch.nn.functional.normalize(v, dim=-1).cpu().numpy())
        return np.vstack(E)
    EA = embed(an["text"].astype(str).tolist()); ES = embed([c[6] for c in cand]) if cand else np.zeros((0, EA.shape[1]))
    rows = []
    for c, e in zip(cand, ES):
        m = (an["criterion"] == c[4]).values; sims = EA[m] @ e; lv = an.loc[m, "level"].values; j = int(sims.argmax())
        rows.append({"bank": c[0], "year": c[1], "page": c[3], "criterion": c[4], "keyword": c[5], "nearest_level": int(lv[j]),
                     "cosine": round(float(sims[j]), 3), "margin_vs_second": round(float(np.sort(sims)[-1] - np.sort(sims)[-2]), 3), "sentence": c[6]})
    sg = pd.DataFrame(rows); sg.to_csv(OUT / "phobert_anchor_suggestions.csv", index=False, encoding="utf-8-sig")
    # gợi ý cấp tiêu chí: mức cao nhất có >= 2 câu hỗ trợ (cosine >= phân vị 75 của chính tiêu chí đó, tránh ngưỡng cố định)
    summ = []
    for (c, b, y), s in sg.groupby(["criterion", "bank", "year"]):
        thr = sg.loc[sg.criterion == c, "cosine"].quantile(0.75); good = s[s.cosine >= thr]
        lvl = int(good.nearest_level.max()) if len(good) >= 2 else 0
        summ.append([c, b, y, len(s), len(good), lvl])
    pd.DataFrame(summ, columns=["criterion", "bank", "year", "keyword_sentences", "strong_sentences", "suggested_level_0_4"]).to_csv(OUT / "phobert_anchor_summary.csv", index=False, encoding="utf-8-sig")
    print("-> out/phobert_anchor_suggestions.csv, out/phobert_anchor_summary.csv (gợi ý để người chấm xem trước, KHÔNG phải điểm)")

if not any(f in sys.argv for f in ("--build-train", "--finetune", "--predict", "--anchors")):
    print(__doc__)
