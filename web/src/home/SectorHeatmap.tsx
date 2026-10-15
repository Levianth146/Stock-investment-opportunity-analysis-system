import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useTheme } from "../theme";
import { sectorVi } from "../sectors";
import { num } from "../fmt";
import { changeToColor, formatChangeLabel, labelInk } from "./colorScale";
import { squarify, type TreemapItem } from "./squarify";

interface HeatCell {
  symbol: string;
  sector: string;
  change_pct?: { value?: number | null };
  market_cap?: { value?: number | null };
  label?: string | null;
}

interface SectorNode {
  sector: string;
  label: string;
  mcap: number;
  change: number | null;
  symbols: HeatCell[];
}

/** Chiều cao dải tiêu đề ngành (px trong viewBox) — tách khỏi ô mã. */
const SECTOR_TITLE_H = 18;
const SECTOR_TITLE_PAD_X = 4;
const SECTOR_GAP = 2;

function cellChg(c: HeatCell): number | null {
  const v = c.change_pct?.value;
  return typeof v === "number" ? v : null;
}

function cellMcap(c: HeatCell): number {
  const v = c.market_cap?.value;
  return typeof v === "number" && v > 0 ? v : 0;
}

export function SectorHeatmap({
  heatmap,
  profile = "long_term",
  showMetrics = true,
}: {
  heatmap: HeatCell[] | null | undefined;
  profile?: string;
  /** false → ô trung tính, ghi chú chưa có giá trực tiếp. */
  showMetrics?: boolean;
}) {
  const nav = useNavigate();
  const { resolved } = useTheme();
  const dark = resolved === "dark";
  const [tip, setTip] = useState<string | null>(null);

  const sectors = useMemo(() => {
    const map = new Map<string, HeatCell[]>();
    for (const c of heatmap || []) {
      const sec = c.sector || "Khác";
      const list = map.get(sec) || [];
      list.push(c);
      map.set(sec, list);
    }
    const nodes: SectorNode[] = [];
    for (const [sector, symbols] of map) {
      const mcap = symbols.reduce((a, s) => a + cellMcap(s), 0);
      const chgs = showMetrics
        ? symbols.map(cellChg).filter((v): v is number => v != null)
        : [];
      const change =
        chgs.length && mcap > 0
          ? symbols.reduce((a, s) => {
              const ch = showMetrics ? cellChg(s) : null;
              const w = cellMcap(s);
              return a + (ch != null && w > 0 ? ch * w : 0);
            }, 0) /
            (symbols.reduce(
              (a, s) => a + (showMetrics && cellChg(s) != null ? cellMcap(s) : 0),
              0,
            ) || 1)
          : chgs.length
            ? chgs.reduce((a, b) => a + b, 0) / chgs.length
            : null;
      nodes.push({
        sector,
        label: sectorVi(sector),
        mcap: mcap || symbols.length,
        change,
        symbols,
      });
    }
    return nodes.sort((a, b) => b.mcap - a.mcap);
  }, [heatmap, showMetrics]);

  const hasAnyPct = useMemo(() => {
    if (!showMetrics) return false;
    return (heatmap || []).some((c) => cellChg(c) != null);
  }, [heatmap, showMetrics]);

  const W = 640;
  const H = 360;
  const sectorRects = useMemo(() => {
    const items: TreemapItem[] = sectors.map((s) => ({
      id: s.sector,
      weight: Math.max(s.mcap, 1),
      data: s,
    }));
    return squarify(items, W, H);
  }, [sectors]);

  if (!heatmap?.length) {
    return (
      <section className="heatmap-panel" aria-label="Heatmap ngành">
        <h2 className="home-sec-title">Heatmap ngành</h2>
        <p className="muted">Chưa có dữ liệu vốn hoá / % thay đổi.</p>
      </section>
    );
  }

  return (
    <section className="heatmap-panel" aria-label="Heatmap ngành">
      <h2 className="home-sec-title">Heatmap ngành</h2>
      <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "0 0 8px" }}>
        Diện tích: vốn hoá (giá × cổ phiếu). Màu: % thay đổi trong phiên (tạm tính).
      </p>
      {!hasAnyPct && (
        <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "0 0 8px" }}>
          chưa có giá trực tiếp
        </p>
      )}
      <div className="heatmap-wrap">
        <svg
          viewBox={`0 0 ${W} ${H}`}
          width="100%"
          role="img"
          aria-label="Treemap ngành theo vốn hoá và % thay đổi"
        >
          {sectorRects.map((r) => {
            const sec = r.data as SectorNode;
            const titleH = Math.min(SECTOR_TITLE_H, Math.max(r.h * 0.35, 12));
            const bodyY = r.y + titleH;
            const bodyH = Math.max(r.h - titleH - SECTOR_GAP, 1);
            const bodyW = Math.max(r.w - SECTOR_GAP * 2, 1);
            const innerItems: TreemapItem[] = sec.symbols.map((s) => ({
              id: s.symbol,
              weight: Math.max(cellMcap(s), 1),
              data: s,
            }));
            const inner = squarify(innerItems, bodyW, bodyH);
            const titleBg = dark ? "#1a242c" : "#e8eef2";
            return (
              <g key={r.id}>
                {/* Dải tiêu đề ngành — tách khỏi ô mã, có padding */}
                <rect
                  x={r.x}
                  y={r.y}
                  width={r.w}
                  height={titleH}
                  fill={titleBg}
                  stroke="var(--paper)"
                  strokeWidth={1}
                />
                {r.w > 40 && (
                  <text
                    x={r.x + SECTOR_TITLE_PAD_X}
                    y={r.y + titleH / 2 + 3.5}
                    fill="var(--ink)"
                    fontSize={10}
                    fontFamily="var(--font)"
                    style={{ cursor: "pointer" }}
                    onClick={(e) => {
                      e.stopPropagation();
                      nav(
                        `/nganh?profile=${profile}&sector=${encodeURIComponent(sec.sector)}`,
                      );
                    }}
                  >
                    {sec.label}
                  </text>
                )}
                {/* Ô mã chỉ trong phần còn lại dưới dải tiêu đề */}
                {inner.map((ir) => {
                  const cell = ir.data as HeatCell;
                  const ch = hasAnyPct ? cellChg(cell) : null;
                  const bg = changeToColor(ch, { dark });
                  const ink = labelInk(bg);
                  const showLabel = ir.w > 36 && ir.h > 28;
                  const tipText = `${cell.symbol}: ${
                    ch != null ? `${formatChangeLabel(ch)}%` : "—"
                  }, vốn hoá ${num(cellMcap(cell), 0)}`;
                  return (
                    <g
                      key={cell.symbol}
                      transform={`translate(${r.x + SECTOR_GAP + ir.x}, ${bodyY + ir.y})`}
                      style={{ cursor: "pointer" }}
                      onClick={() => nav(`/t/${cell.symbol}?profile=${profile}`)}
                      onMouseEnter={() => setTip(tipText)}
                      onMouseLeave={() => setTip(null)}
                      onFocus={() => setTip(tipText)}
                      onBlur={() => setTip(null)}
                      tabIndex={0}
                      role="link"
                      aria-label={tipText}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" || e.key === " ") {
                          e.preventDefault();
                          nav(`/t/${cell.symbol}?profile=${profile}`);
                        }
                      }}
                    >
                      <rect
                        width={ir.w}
                        height={ir.h}
                        fill={bg}
                        stroke="var(--paper)"
                        strokeWidth={1}
                      />
                      {showLabel && (
                        <>
                          <text
                            x={4}
                            y={14}
                            fill={ink}
                            fontSize={11}
                            fontFamily="var(--font)"
                          >
                            {cell.symbol}
                          </text>
                          <text
                            x={4}
                            y={28}
                            fill={ink}
                            fontSize={10}
                            fontFamily="var(--font)"
                            className="tabular"
                          >
                            {ch != null ? formatChangeLabel(ch) : "—"}
                          </text>
                        </>
                      )}
                    </g>
                  );
                })}
              </g>
            );
          })}
        </svg>
        {tip && (
          <div className="heatmap-tip" role="tooltip">
            {tip}
          </div>
        )}
      </div>

      {/* Bảng thay thế cho trình đọc màn hình / bàn phím */}
      <table className="sr-only" aria-label="Bảng heatmap ngành">
        <thead>
          <tr>
            <th>Ngành</th>
            <th>Mã</th>
            <th>% thay đổi</th>
            <th>Vốn hoá</th>
          </tr>
        </thead>
        <tbody>
          {sectors.flatMap((s) =>
            s.symbols.map((c) => (
              <tr key={`${s.sector}-${c.symbol}`}>
                <td>
                  <Link to={`/nganh?profile=${profile}`}>{s.label}</Link>
                </td>
                <td>
                  <Link to={`/t/${c.symbol}?profile=${profile}`}>{c.symbol}</Link>
                </td>
                <td>
                  {hasAnyPct && cellChg(c) != null
                    ? formatChangeLabel(cellChg(c))
                    : "—"}
                </td>
                <td>{num(cellMcap(c), 0)}</td>
              </tr>
            )),
          )}
        </tbody>
      </table>
    </section>
  );
}
