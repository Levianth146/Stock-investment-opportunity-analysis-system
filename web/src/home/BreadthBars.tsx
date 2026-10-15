import { num } from "../fmt";
import { breadthSum, type BreadthCounts } from "./breadth";

function val(v: { value?: number } | number | null | undefined): number {
  if (v == null) return 0;
  if (typeof v === "number") return v;
  return Number(v.value) || 0;
}

export function BreadthBars({
  breadth,
}: {
  breadth: Record<string, unknown> | null | undefined;
}) {
  if (!breadth) return null;
  const counts: BreadthCounts = {
    up: val(breadth.up as { value?: number }),
    down: val(breadth.down as { value?: number }),
    flat: val(breadth.flat as { value?: number }),
    unmatched: val(breadth.unmatched as { value?: number }),
  };
  const total = breadthSum(counts) || 1;
  const liquid = val(breadth.liquid_count as number) || total;
  const note = typeof breadth.note === "string" ? breadth.note : null;

  const segs: { key: keyof BreadthCounts; label: string; cls: string }[] = [
    { key: "up", label: "Tăng", cls: "breadth-up" },
    { key: "down", label: "Giảm", cls: "breadth-down" },
    { key: "flat", label: "Đứng", cls: "breadth-flat" },
    { key: "unmatched", label: "Chưa khớp", cls: "breadth-unmatched" },
  ];

  return (
    <section className="breadth-panel" aria-label="Độ rộng thị trường">
      <h2 className="home-sec-title">Độ rộng</h2>
      <div className="breadth-bar" role="img" aria-label={`Tăng ${counts.up}, giảm ${counts.down}, đứng ${counts.flat}, chưa khớp ${counts.unmatched}`}>
        {segs.map((s) => {
          const n = counts[s.key];
          if (!n) return null;
          return (
            <span
              key={s.key}
              className={`breadth-seg ${s.cls}`}
              style={{ width: `${(n / total) * 100}%` }}
              title={`${s.label}: ${n}`}
            />
          );
        })}
      </div>
      <ul className="breadth-legend">
        {segs.map((s) => (
          <li key={s.key}>
            <i className={`breadth-dot ${s.cls}`} aria-hidden />
            {s.label}{" "}
            <span className="tabular">{num(counts[s.key], 0)}</span>
          </li>
        ))}
      </ul>
      <div className="breadth-extra muted">
        <span>
          Trên SMA50{" "}
          <span className="tabular">{num(val(breadth.above_sma50 as { value?: number }), 0)}</span>
          {" / "}
          SMA200{" "}
          <span className="tabular">{num(val(breadth.above_sma200 as { value?: number }), 0)}</span>
          {" · EOD"}
        </span>
        <span>
          52 tuần cao{" "}
          <span className="tabular">{num(val(breadth.hit_52w_high as { value?: number }), 0)}</span>
          {" / thấp "}
          <span className="tabular">{num(val(breadth.hit_52w_low as { value?: number }), 0)}</span>
        </span>
      </div>
      <p className="muted" style={{ fontSize: "var(--fs-xs)", margin: "6px 0 0" }}>
        {note || `Trên ${liquid} mã thanh khoản đủ.`}
      </p>
    </section>
  );
}
