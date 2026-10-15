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
  /** Vốn hoá theo giá đóng cửa trước × CP lưu hành — cố định trong phiên, dùng cho diện tích. */
  market_cap_ref?: number | null;
  label?: string | null;
}

interface SectorNode {
  sector: string;
  label: string;
  mcap: number;
  symbols: HeatCell[];
}

/** Nhãn ngành cắt theo bề rộng ô (SVG không có text-overflow) — thêm "…", đủ tên ở <title>. */
export function fitLabel(label: string, widthPx: number, charPx = 5.8): string {
  const max = Math.floor(widthPx / charPx);
  if (max < 3) return "";
  if (label.length <= max) return label;
  return label.slice(0, Math.max(max - 1, 1)).trimEnd() + "…";
}

const LEGEND_STOPS = [-5, -3, -1, 0, 1, 3, 5];

/** Chiều cao dải tiêu đề ngành (px trong viewBox) — tách khỏi ô mã. */
const SECTOR_TITLE_H = 18;
const SECTOR_TITLE_PAD_X = 4;
const SECTOR_GAP = 2;

function cellChg(c: HeatCell): number | null {
  const v = c.change_pct?.value;
  return typeof v === "number" ? v : null;
}

function cellMcap(c: HeatCell): number {
  const ref = c.market_cap_ref;
  if (typeof ref === "number" && ref > 0) return ref;
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

  // Bố cục chỉ phụ thuộc cấu trúc (mã, ngành, vốn hoá tham chiếu) — KHÔNG đổi theo tick.
  const structKey = (heatmap || [])
    .map((c) => `${c.symbol}|${c.sector}|${cellMcap(c)}`)
    .join(";");

  const W = 640;
  const H = 360;
  const layout = useMemo(() => {
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
      nodes.push({ sector, label: sectorVi(sector), mcap: mcap || symbols.length, symbols });
    }
    nodes.sort((a, b) => b.mcap - a.mcap);
    const items: TreemapItem[] = nodes.map((n) => ({
      id: n.sector,
      weight: Math.max(n.mcap, 1),
      data: n,
    }));
    const rects = squarify(items, W, H).map((r) => {
      const sec = r.data as SectorNode;
      const titleH = Math.min(SECTOR_TITLE_H, Math.max(r.h * 0.35, 12));
      const bodyH = Math.max(r.h - titleH - SECTOR_GAP, 1);
      const bodyW = Math.max(r.w - SECTOR_GAP * 2, 1);
      const inner = squarify(
        sec.symbols.map((s) => ({
          id: s.symbol,
          weight: Math.max(cellMcap(s), 1),
          data: s.symbol,
        })),
        bodyW,
        bodyH,
      );
      return { r, sec, titleH, inner };
    });
    return { nodes, rects };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [structKey]);

  const bySym = useMemo(() => {
    const m = new Map<string, HeatCell>();
    for (const c of heatmap || []) m.set(c.symbol, c);
    return m;
  }, [heatmap]);

  const hasAnyPct = useMemo(() => {
    if (!showMetrics) return false;
    return (heatmap || []).some((c) => cellChg(c) != null);
  }, [heatmap, showMetrics]);

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
        Diện tích: vốn hoá theo giá đóng cửa trước (cố định trong phiên). Màu: % thay đổi trong phiên (tạm tính).
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
          {layout.rects.map(({ r, sec, titleH, inner }) => {
            const bodyY = r.y + titleH;
            const titleBg = dark ? "#1a242c" : "#e8eef2";
            const shown = fitLabel(sec.label, r.w - SECTOR_TITLE_PAD_X * 2);
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
                {shown && (
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
                    <title>{sec.label}</title>
                    {shown}
                  </text>
                )}
                {/* Ô mã chỉ trong phần còn lại dưới dải tiêu đề */}
                {inner.map((ir) => {
                  const cell = bySym.get(String(ir.data)) as HeatCell;
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
                      <title>{tipText}</title>
                      <rect
                        className="heat-rect"
                        width={ir.w}
                        height={ir.h}
                        style={{ fill: bg }}
                        stroke="var(--paper)"
                        strokeWidth={1}
                      />
                      {showLabel && (
                        <>
                          <text x={4} y={14} fill={ink} fontSize={11} fontFamily="var(--font)">
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
      <ul className="heat-legend" aria-label="Chú giải màu % thay đổi">
        {LEGEND_STOPS.map((v) => (
          <li key={v}>
            <span className="heat-legend-sw" style={{ background: changeToColor(v, { dark }) }} />
            <span className="tabular">
              {v === -5 ? "≤−5%" : v === 5 ? "≥+5%" : v === 0 ? "0%" : `${v > 0 ? "+" : "−"}${Math.abs(v)}%`}
            </span>
          </li>
        ))}
        <li>
          <span className="heat-legend-sw" style={{ background: changeToColor(null, { dark }) }} />
          <span>chưa có dữ liệu</span>
        </li>
      </ul>

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
          {layout.nodes.flatMap((s) =>
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
