import { useEffect, useId, useMemo, useState } from "react";
import {
  DEFAULT_RATINGS,
  ratingTone,
  thresholdMarks,
  zoneLabels,
  type RatingThreshold,
} from "../ratings";
import { score as fmtScore } from "../fmt";

export interface ScoreMarker {
  value: number;
  label: string;
  kind?: "primary" | "secondary" | "highlight";
}

export interface ScoreRulerProps {
  markers?: ScoreMarker[];
  /** Tất cả điểm (rug). */
  rug?: number[];
  /** Điểm đang lọc — tô accent trên rug. */
  rugHighlight?: number[];
  ratings?: RatingThreshold[];
  /** Mini 120px, chỉ chấm điểm. */
  compact?: boolean;
  /** Trượt marker primary từ 50 → value (ticker header). */
  animatePrimary?: boolean;
  className?: string;
  "aria-label"?: string;
}

function clamp01(v: number): number {
  return Math.max(0, Math.min(100, v));
}

function prefersReducedMotion(): boolean {
  if (typeof window === "undefined") return true;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** CSS var tô vùng (fill nhạt) theo nhãn khuyến nghị. */
function zoneFillVar(label: string): string {
  const t = ratingTone(label);
  if (t === "none") return "var(--rating-hold-fill)";
  return `var(--rating-${t}-fill)`;
}

export function ScoreRuler({
  markers = [],
  rug,
  rugHighlight,
  ratings = DEFAULT_RATINGS,
  compact = false,
  animatePrimary = false,
  className = "",
  "aria-label": ariaLabel = "Thước điểm 0–100",
}: ScoreRulerProps) {
  const uid = useId();
  const thresholds = useMemo(() => thresholdMarks(ratings), [ratings]);
  const zones = useMemo(() => zoneLabels(ratings), [ratings]);
  const edges = useMemo(() => [0, ...thresholds, 100], [thresholds]);

  const primary = markers.find((m) => (m.kind || "primary") === "primary");
  const [animVal, setAnimVal] = useState(
    animatePrimary && primary && !prefersReducedMotion() ? 50 : primary?.value ?? null,
  );
  const [narrow, setNarrow] = useState(
    typeof window !== "undefined" ? window.innerWidth <= 480 : false,
  );

  useEffect(() => {
    const onResize = () => setNarrow(window.innerWidth <= 480);
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    if (!animatePrimary || primary == null) {
      setAnimVal(primary?.value ?? null);
      return;
    }
    if (prefersReducedMotion()) {
      setAnimVal(primary.value);
      return;
    }
    setAnimVal(50);
    let raf = 0;
    const start = performance.now();
    const from = 50;
    const to = clamp01(primary.value);
    const dur = 400;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / dur);
      const e = 1 - (1 - t) ** 3;
      setAnimVal(from + (to - from) * e);
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [animatePrimary, primary?.value]);

  const displayMarkers = markers.map((m) => {
    if ((m.kind || "primary") === "primary" && animVal != null) {
      return { ...m, value: animVal };
    }
    return m;
  });

  const highlightSet = useMemo(() => {
    if (!rugHighlight?.length) return null;
    return new Set(rugHighlight.map((v) => Math.round(v * 10) / 10));
  }, [rugHighlight]);

  /** Ở <=480px chỉ giữ 2 nhãn gần marker nhất. */
  const visibleZoneIdx = useMemo(() => {
    if (!narrow) return new Set(zones.map((_, i) => i));
    const anchor = primary?.value ?? 50;
    const mids = zones.map((_, i) => {
      if (i + 1 >= edges.length) return { i, mid: 50, dist: 999 };
      const mid = (edges[i]! + edges[i + 1]!) / 2;
      return { i, mid, dist: Math.abs(mid - anchor) };
    });
    mids.sort((a, b) => a.dist - b.dist);
    return new Set(mids.slice(0, 2).map((x) => x.i));
  }, [narrow, zones, edges, primary?.value]);

  if (compact) {
    const v = primary?.value;
    const x = v != null ? clamp01(v) : null;
    return (
      <svg
        className={`score-ruler score-ruler--compact ${className}`.trim()}
        viewBox="0 0 120 14"
        width={120}
        height={14}
        role="img"
        aria-label={ariaLabel}
      >
        {zones.map((lab, i) => {
          if (i + 1 >= edges.length) return null;
          const x0 = (edges[i]! / 100) * 120;
          const x1 = (edges[i + 1]! / 100) * 120;
          return (
            <rect
              key={`zc-${lab}-${i}`}
              x={x0}
              y={4}
              width={Math.max(0, x1 - x0)}
              height={6}
              fill={zoneFillVar(lab)}
            />
          );
        })}
        <line x1={0} y1={7} x2={120} y2={7} stroke="var(--rule)" strokeWidth={1} />
        {thresholds.map((t) => (
          <line
            key={t}
            x1={(t / 100) * 120}
            x2={(t / 100) * 120}
            y1={3}
            y2={11}
            stroke="var(--ink-3)"
            strokeWidth={1}
          />
        ))}
        {x != null && (
          <circle cx={(x / 100) * 120} cy={7} r={3.5} fill="var(--accent)" />
        )}
      </svg>
    );
  }

  const W = 640;
  const H = 78;
  const padX = 12;
  const barY = 30;
  const barH = 14;
  const plotW = W - padX * 2;
  const xOf = (v: number) => padX + (clamp01(v) / 100) * plotW;

  return (
    <svg
      className={`score-ruler ${className}`.trim()}
      viewBox={`0 0 ${W} ${H}`}
      width="100%"
      role="img"
      aria-label={ariaLabel}
    >
      {/* Vùng tô nhạt 5 bậc khuyến nghị */}
      {zones.map((lab, i) => {
        if (i + 1 >= edges.length) return null;
        const x0 = xOf(edges[i]!);
        const x1 = xOf(edges[i + 1]!);
        return (
          <rect
            key={`zfill-${lab}-${i}`}
            x={x0}
            y={barY - barH / 2}
            width={Math.max(0, x1 - x0)}
            height={barH}
            fill={zoneFillVar(lab)}
          />
        );
      })}
      <line
        x1={padX}
        x2={W - padX}
        y1={barY}
        y2={barY}
        stroke="var(--rule)"
        strokeWidth={1}
      />
      {(rug || []).map((s, i) => {
        const xv = xOf(s);
        const key = Math.round(s * 10) / 10;
        const hi = highlightSet ? highlightSet.has(key) : true;
        return (
          <line
            key={`${uid}-r-${i}`}
            x1={xv}
            x2={xv}
            y1={barY - (hi ? 10 : 7)}
            y2={barY + (hi ? 10 : 7)}
            stroke={hi ? "var(--accent)" : "var(--ink-3)"}
            strokeWidth={hi ? 1.2 : 0.8}
            opacity={hi ? 0.9 : 0.5}
          />
        );
      })}
      {thresholds.map((t) => (
        <line
          key={`t-${t}`}
          x1={xOf(t)}
          x2={xOf(t)}
          y1={barY - 12}
          y2={barY + 12}
          stroke="var(--ink-3)"
          strokeWidth={1.25}
        />
      ))}
      {/* Số ngưỡng */}
      {[0, ...thresholds, 100].map((t) => (
        <text
          key={`n-${t}`}
          x={xOf(t)}
          y={barY + 24}
          textAnchor={t <= 0 ? "start" : t >= 100 ? "end" : "middle"}
          className="score-ruler-num"
          fill="var(--ink-3)"
          fontSize={11}
        >
          {t}
        </text>
      ))}
      {/* Nhãn vùng — một hàng, căn giữa từng zone */}
      {zones.map((lab, i) => {
        if (i + 1 >= edges.length) return null;
        if (!visibleZoneIdx.has(i)) return null;
        const mid = (edges[i]! + edges[i + 1]!) / 2;
        return (
          <text
            key={`z-${lab}-${i}`}
            x={xOf(mid)}
            y={barY + 40}
            textAnchor="middle"
            className="score-ruler-zone"
            fill="var(--ink-2)"
            fontSize={11}
          >
            {lab}
          </text>
        );
      })}
      {/* Markers: primary = chấm; secondary (trung vị ngành) = tam giác */}
      {displayMarkers.map((m, i) => {
        const xv = xOf(m.value);
        const kind = m.kind || "primary";
        const labelY = barY - 16 - (i % 2) * 12;
        if (kind === "secondary") {
          const tri = `${xv},${barY - 9} ${xv - 6},${barY + 2} ${xv + 6},${barY + 2}`;
          return (
            <g key={`${uid}-m-${i}`}>
              <polygon points={tri} fill="var(--series-2)" />
              <text
                x={xv}
                y={labelY}
                textAnchor="middle"
                fill="var(--ink)"
                fontSize={11}
                fontWeight={600}
              >
                {m.label.includes("Trung vị")
                  ? m.label
                  : `Trung vị ngành ${fmtScore(m.value)}`}
              </text>
            </g>
          );
        }
        const fill = kind === "highlight" ? "var(--series-2)" : "var(--accent)";
        return (
          <g key={`${uid}-m-${i}`}>
            <line
              x1={xv}
              x2={xv}
              y1={barY - 14}
              y2={barY + 14}
              stroke={fill}
              strokeWidth={2}
            />
            <circle cx={xv} cy={barY} r={5} fill={fill} />
            <text
              x={xv}
              y={labelY}
              textAnchor="middle"
              fill="var(--ink)"
              fontSize={11}
              fontWeight={600}
            >
              {m.label}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
