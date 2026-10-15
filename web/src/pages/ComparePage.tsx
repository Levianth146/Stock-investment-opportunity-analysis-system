/** So sánh tối đa 4 mã cạnh nhau (điểm, trụ cột, giá tham chiếu). Chọn qua ?s=AAA,BBB. */
import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Profile, RankingRow } from "../api/types";
import { num, pct, score } from "../fmt";
import { ratingClass } from "../ratings";
import { sectorVi } from "../sectors";

export const COMPARE_MAX = 4;

export function parseSymbols(raw: string | null): string[] {
  const out: string[] = [];
  for (const p of (raw || "").split(",")) {
    const s = p.trim().toUpperCase();
    if (/^[A-Z0-9]{2,5}$/.test(s) && !out.includes(s)) out.push(s);
    if (out.length >= COMPARE_MAX) break;
  }
  return out;
}

/** Chỉ số tốt nhất của một hàng: cao hơn tốt (R thấp hơn tốt). */
export function bestIndex(vals: Array<number | null | undefined>, lowerBetter = false): number {
  let best = -1;
  vals.forEach((v, i) => {
    if (v == null || Number.isNaN(v)) return;
    if (best < 0) best = i;
    else {
      const b = vals[best] as number;
      if (lowerBetter ? v < b : v > b) best = i;
    }
  });
  const n = vals.filter((v) => v != null && !Number.isNaN(v as number)).length;
  return n >= 2 ? best : -1;
}

export function ComparePage() {
  const [sp, setSp] = useSearchParams();
  const profile = (sp.get("profile") as Profile) || "long_term";
  const symbols = useMemo(() => parseSymbols(sp.get("s")), [sp]);
  const [q, setQ] = useState("");

  const rankQ = useQuery({
    queryKey: ["rankings-all", profile],
    queryFn: () =>
      api.rankings({ profile, limit: 500, include_unranked: true, sort: "score", order: "desc" }),
  });
  const rows = rankQ.data?.items || [];
  const bySym = useMemo(() => new Map(rows.map((r) => [r.ticker, r])), [rows]);
  const picked = symbols.map((s) => bySym.get(s)).filter(Boolean) as RankingRow[];

  const setSymbols = (next: string[]) => {
    const n = new URLSearchParams(sp);
    if (next.length) n.set("s", next.join(","));
    else n.delete("s");
    setSp(n, { replace: true });
  };
  const add = (s: string) => {
    if (!s || symbols.includes(s) || symbols.length >= COMPARE_MAX) return;
    setSymbols([...symbols, s]);
    setQ("");
  };

  const suggestions = useMemo(() => {
    const t = q.trim().toUpperCase();
    if (!t) return [];
    return rows
      .filter((r) => !symbols.includes(r.ticker))
      .filter((r) => r.ticker.startsWith(t) || (r.name || "").toUpperCase().includes(t))
      .slice(0, 6);
  }, [q, rows, symbols]);

  type Line = {
    label: string;
    vals: Array<number | null | undefined>;
    fmt: (v: number | null | undefined) => string;
    lowerBetter?: boolean;
    hint?: string;
  };
  const lines: Line[] = [
    { label: "Điểm tổng", vals: picked.map((r) => r.score), fmt: score },
    { label: "F · Cơ bản", vals: picked.map((r) => r.scores?.F), fmt: score },
    { label: "T · Kỹ thuật", vals: picked.map((r) => r.scores?.T), fmt: score },
    { label: "V · Định giá", vals: picked.map((r) => r.scores?.V), fmt: score },
    { label: "S · Tin tức", vals: picked.map((r) => r.scores?.S), fmt: score },
    {
      label: "R · Rủi ro",
      vals: picked.map((r) => r.scores?.R),
      fmt: score,
      lowerBetter: true,
      hint: "thấp hơn là tốt hơn",
    },
    { label: "Giá đóng cửa", vals: picked.map((r) => r.price), fmt: (v) => num(v, 2) },
    { label: "Giá tham chiếu ngành", vals: picked.map((r) => r.reference_price), fmt: (v) => num(v, 2) },
    {
      label: "Chênh lệch so với giá tham chiếu",
      vals: picked.map((r) => r.upside_pct),
      fmt: (v) => pct(v),
      hint: "không phải dự báo giá",
    },
  ];

  return (
    <div className="compare-page">
      <h1 style={{ fontSize: "var(--fs-lg)" }}>So sánh mã</h1>
      <p className="muted" style={{ maxWidth: "62ch" }}>
        Chọn tối đa {COMPARE_MAX} mã. Điểm lấy từ khung điểm đã công bố ở trang Phương pháp
        (điểm EOD, không đổi theo giá trong phiên).
      </p>

      <div className="compare-pick">
        <label htmlFor="cmp-q" className="muted">
          Thêm mã
        </label>
        <input
          id="cmp-q"
          className="compare-input"
          value={q}
          disabled={symbols.length >= COMPARE_MAX}
          placeholder={symbols.length >= COMPARE_MAX ? "Đã đủ số mã" : "Mã hoặc tên công ty"}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && suggestions[0]) add(suggestions[0].ticker);
          }}
          autoComplete="off"
        />
        {suggestions.length > 0 && (
          <ul className="compare-suggest">
            {suggestions.map((r) => (
              <li key={r.ticker}>
                <button type="button" onClick={() => add(r.ticker)}>
                  <strong>{r.ticker}</strong> <span className="muted">{r.name}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {rankQ.isLoading && <p className="muted">Đang tải…</p>}
      {rankQ.isError && <p role="alert">Không tải được dữ liệu xếp hạng.</p>}

      {symbols.length === 0 && !rankQ.isLoading && (
        <p className="muted">Chưa chọn mã nào. Gõ mã ở ô trên, hoặc dùng nút “So sánh” trong trang một mã.</p>
      )}
      {symbols.length > 0 && picked.length < symbols.length && !rankQ.isLoading && (
        <p className="muted">
          Không tìm thấy: {symbols.filter((s) => !bySym.has(s)).join(", ")}.
        </p>
      )}

      {picked.length > 0 && (
        <div className="table-wrap">
          <table className="fin-table compare-table">
            <thead>
              <tr>
                <th style={{ textAlign: "left" }}> </th>
                {picked.map((r) => (
                  <th key={r.ticker}>
                    <Link to={`/t/${r.ticker}?profile=${profile}`}>{r.ticker}</Link>
                    <div className="muted" style={{ fontSize: "var(--fs-xs)", fontWeight: 400 }}>
                      {sectorVi(r.sector)}
                    </div>
                    <button
                      type="button"
                      className="compare-remove"
                      onClick={() => setSymbols(symbols.filter((s) => s !== r.ticker))}
                      aria-label={`Bỏ ${r.ticker}`}
                    >
                      Bỏ
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td style={{ textAlign: "left" }}>Khuyến nghị</td>
                {picked.map((r) => (
                  <td key={r.ticker}>
                    <span className={`compare-rating ${ratingClass(r.rating)}`}>{r.rating || "—"}</span>
                    {r.quality_gate?.tier === "limited" && (
                      <div className="muted" style={{ fontSize: "var(--fs-xs)" }}>
                        dữ liệu hạn chế
                      </div>
                    )}
                  </td>
                ))}
              </tr>
              {lines.map((ln) => {
                const b = bestIndex(ln.vals, ln.lowerBetter);
                return (
                  <tr key={ln.label}>
                    <td style={{ textAlign: "left" }}>
                      {ln.label}
                      {ln.hint && (
                        <div className="muted" style={{ fontSize: "var(--fs-xs)" }}>
                          {ln.hint}
                        </div>
                      )}
                    </td>
                    {ln.vals.map((v, i) => (
                      <td
                        key={picked[i]!.ticker}
                        className={`tabular${i === b && ln.label !== "Giá đóng cửa" && ln.label !== "Giá tham chiếu ngành" ? " compare-best" : ""}`}
                      >
                        {ln.fmt(v)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted" style={{ fontSize: "var(--fs-xs)", marginTop: 16 }}>
        Ô đậm là giá trị tốt nhất trong hàng. Công cụ hỗ trợ phân tích, không phải lời khuyên đầu tư.
      </p>
    </div>
  );
}
