import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Profile, RankingRow } from "../api/types";
import { score } from "../fmt";
import { ratingsFromMeta } from "../ratings";
import { sectorVi } from "../sectors";

/** Màu điểm phân kỳ quanh 50 (xác nhận khoảng). */
export function scoreColor(sc: number | null | undefined): string {
  if (sc == null || Number.isNaN(sc)) return "var(--ink-3)";
  const t = Math.max(0, Math.min(100, sc));
  if (t >= 60) {
    const a = (t - 60) / 40;
    return `color-mix(in srgb, var(--rating-strong-buy) ${Math.round(40 + a * 50)}%, var(--panel))`;
  }
  if (t <= 40) {
    const a = (40 - t) / 40;
    return `color-mix(in srgb, var(--rating-sell) ${Math.round(40 + a * 50)}%, var(--panel))`;
  }
  return `color-mix(in srgb, var(--rating-hold) 35%, var(--panel))`;
}

function median(vals: number[]): number | null {
  if (!vals.length) return null;
  const s = [...vals].sort((a, b) => a - b);
  const m = Math.floor(s.length / 2);
  return s.length % 2 ? s[m]! : (s[m - 1]! + s[m]!) / 2;
}

type SectorGroup = {
  sector: string;
  label: string;
  n: number;
  median: number | null;
  dist: Record<string, number>;
  rows: RankingRow[];
  equalTiles: boolean;
  missingCapPct: number;
};

function buildGroupTiles(rows: RankingRow[]): {
  tiles: Array<RankingRow & { area: number }>;
  equalTiles: boolean;
  missingCapPct: number;
} {
  const n = rows.length || 1;
  const missing = rows.filter(
    (r) => !(typeof r.market_cap === "number" && r.market_cap > 0),
  ).length;
  const missingCapPct = missing / n;
  const equalTiles = missingCapPct > 0.3;
  const tiles = rows.map((r) => {
    const cap =
      typeof r.market_cap === "number" && r.market_cap > 0 ? r.market_cap : null;
    const area = equalTiles ? 1 : cap ?? 1;
    return { ...r, area };
  });
  return { tiles, equalTiles, missingCapPct };
}

export function SectorPage() {
  const [sp, setSp] = useSearchParams();
  const profile = (sp.get("profile") as Profile) || "long_term";
  const [narrow, setNarrow] = useState(
    typeof window !== "undefined" ? window.innerWidth <= 360 : false,
  );

  useEffect(() => {
    const on = () => setNarrow(window.innerWidth <= 360);
    on();
    window.addEventListener("resize", on);
    return () => window.removeEventListener("resize", on);
  }, []);

  const rankingsQ = useQuery({
    queryKey: ["rankings-all", profile],
    queryFn: () =>
      api.rankings({
        profile,
        limit: 500,
        include_unranked: false,
        sort: "score",
        order: "desc",
      }),
  });
  const sectorsQ = useQuery({
    queryKey: ["sectors", profile],
    queryFn: () => api.sectors(profile),
  });
  const metaQ = useQuery({ queryKey: ["meta"], queryFn: () => api.meta() });
  const ratings = ratingsFromMeta(metaQ.data);

  const bySector = useMemo(() => {
    const map = new Map<string, RankingRow[]>();
    for (const row of rankingsQ.data?.items || []) {
      if (!row.ranked || row.score == null) continue;
      const sec = row.sector || "Khác";
      if (!map.has(sec)) map.set(sec, []);
      map.get(sec)!.push(row);
    }
    return map;
  }, [rankingsQ.data]);

  const sectorGroups: SectorGroup[] = useMemo(() => {
    const fromApi = sectorsQ.data?.items || [];
    const keys = new Set<string>([
      ...fromApi.map((s) => s.sector),
      ...bySector.keys(),
    ]);
    const groups: SectorGroup[] = [];
    for (const sector of keys) {
      const rows = bySector.get(sector) || [];
      if (!rows.length) continue;
      const apiHit = fromApi.find((s) => s.sector === sector);
      const scores = rows
        .map((r) => r.score)
        .filter((v): v is number => typeof v === "number");
      const { equalTiles, missingCapPct } = buildGroupTiles(rows);
      groups.push({
        sector,
        label: sectorVi(apiHit?.label || sector),
        n: rows.length,
        median: median(scores),
        dist: apiHit?.rating_distribution || {},
        rows,
        equalTiles,
        missingCapPct,
      });
    }
    return groups.sort((a, b) => b.n - a.n || a.label.localeCompare(b.label, "vi"));
  }, [sectorsQ.data, bySector]);

  return (
    <main className="sector-page">
      <div className="toolbar" style={{ justifyContent: "space-between" }}>
        <h1 style={{ margin: 0, fontSize: "var(--fs-lg)", fontWeight: 600 }}>
          Ngành
        </h1>
        <label>
          <span className="muted">Kiểu đầu tư </span>
          <select
            value={profile}
            onChange={(e) => {
              const n = new URLSearchParams(sp);
              n.set("profile", e.target.value);
              setSp(n, { replace: true });
            }}
            aria-label="Kiểu đầu tư"
          >
            <option value="long_term">Dài hạn</option>
            <option value="swing">Lướt sóng</option>
          </select>
        </label>
      </div>

      <div className="treemap-legend muted" aria-label="Chú thích">
        <span>Diện tích: vốn hoá trong ngành</span>
        <span>
          Màu: điểm thấp{" "}
          <i className="leg-swatch" style={{ background: scoreColor(20) }} /> →
          cao <i className="leg-swatch" style={{ background: scoreColor(80) }} />
        </span>
      </div>

      {rankingsQ.isLoading && <div className="skeleton" aria-busy="true" />}
      {rankingsQ.isError && (
        <div className="error-box">Không tải được dữ liệu ngành.</div>
      )}

      {sectorGroups.map((g) => {
        const { tiles } = buildGroupTiles(g.rows);
        const headingNote = g.equalTiles
          ? " — diện tích bằng nhau (thiếu vốn hoá > 30%)"
          : "";
        return (
          <section key={g.sector} className="sector-group" aria-labelledby={`sec-${g.sector}`}>
            <h2
              id={`sec-${g.sector}`}
              style={{ fontSize: "var(--fs-md)", margin: "20px 0 6px", fontWeight: 600 }}
            >
              {g.label}
              <span className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>
                {g.n} mã có điểm
                {g.median != null ? ` · trung vị ${score(g.median)}` : ""}
                {headingNote}
              </span>
            </h2>

            {!narrow && tiles.length > 0 && (
              <div
                className="treemap"
                role="list"
                aria-label={`Treemap ${g.label}`}
              >
                {tiles.map((t) => (
                  <Link
                    key={t.ticker}
                    role="listitem"
                    className="treemap-tile"
                    to={`/t/${t.ticker}?profile=${profile}`}
                    style={{
                      flexGrow: Math.max(t.area, 1),
                      flexBasis: 56,
                      background: scoreColor(t.score),
                    }}
                    title={`${t.ticker} · ${score(t.score)}`}
                  >
                    <span className="tm-sym">{t.ticker}</span>
                    <span className="tm-sc tabular">{score(t.score)}</span>
                  </Link>
                ))}
              </div>
            )}

            {(narrow || tiles.length === 0) && tiles.length > 0 && (
              <ul className="sector-fallback-list">
                {tiles.map((t) => (
                  <li key={t.ticker}>
                    <Link to={`/t/${t.ticker}?profile=${profile}`}>
                      {t.ticker}
                    </Link>{" "}
                    <span className="tabular">{score(t.score)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        );
      })}

      <h2 style={{ fontSize: "var(--fs-md)", marginTop: 28 }}>Theo ngành</h2>
      <div className="table-wrap">
        <table className="fin-table sector-table">
          <thead>
            <tr>
              <th style={{ textAlign: "left" }}>Ngành</th>
              <th>Số mã</th>
              <th>Trung vị điểm</th>
              <th style={{ textAlign: "left" }}>Phân bố khuyến nghị</th>
            </tr>
          </thead>
          <tbody>
            {sectorGroups.map((s) => (
              <tr key={s.sector}>
                <td style={{ textAlign: "left" }}>
                  {s.label}
                  <div className="muted" style={{ fontSize: "var(--fs-xs)" }}>
                    {s.n} mã có điểm
                    {s.median != null ? ` · trung vị ${score(s.median)}` : ""}
                  </div>
                </td>
                <td className="tabular">{s.n}</td>
                <td className="tabular">{score(s.median)}</td>
                <td>
                  <RatingStack dist={s.dist} ratings={ratings.map((r) => r.label)} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}

function RatingStack({
  dist,
  ratings,
}: {
  dist: Record<string, number>;
  ratings: string[];
}) {
  const total = Object.values(dist).reduce((a, b) => a + b, 0) || 1;
  const order = ratings.length ? ratings : Object.keys(dist);
  return (
    <div className="rating-stack" title={JSON.stringify(dist)}>
      {order.map((lab) => {
        const n = dist[lab] || 0;
        if (!n) return null;
        const pctW = (n / total) * 100;
        return (
          <span
            key={lab}
            style={{ width: `${pctW}%` }}
            className={`rs-seg rating-${lab.toLowerCase().includes("mạnh") ? "strong-buy" : lab.toLowerCase().includes("mua") ? "buy" : lab.toLowerCase().includes("giảm") ? "reduce" : lab.toLowerCase().includes("bán") ? "sell" : "hold"}`}
            title={`${lab}: ${n}`}
          />
        );
      })}
    </div>
  );
}
