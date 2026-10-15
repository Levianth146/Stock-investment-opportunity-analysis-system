import type { PeerRow, PercentileBand } from "../api/types";
import { num, vnd } from "../fmt";

function BandChart({
  title,
  value,
  band,
}: {
  title: string;
  value: number | null;
  band: PercentileBand | null | undefined;
}) {
  if (!band || band.p10 == null || band.p90 == null) {
    return (
      <div className="fin-chart-block">
        <h4 className="fin-chart-title">{title}</h4>
        <p className="muted">Chưa đủ phân vị ngành.</p>
      </div>
    );
  }
  const lo = band.p10!;
  const hi = band.p90!;
  const span = hi - lo || 1;
  const pos = (x: number) => `${((x - lo) / span) * 100}%`;
  /** Chỉ nhãn P25/P50/P75; P10/P90 là đầu–cuối dải (tick không chữ). */
  const marks: { key: keyof PercentileBand; lab: string; labeled: boolean }[] = [
    { key: "p10", lab: "P10", labeled: false },
    { key: "p25", lab: "P25", labeled: true },
    { key: "p50", lab: "P50", labeled: true },
    { key: "p75", lab: "P75", labeled: true },
    { key: "p90", lab: "P90", labeled: false },
  ];
  return (
    <div className="fin-chart-block">
      <h4 className="fin-chart-title">{title}</h4>
      <div className="band-track" role="img" aria-label={title}>
        <div
          className="band-fill"
          style={{
            left: pos(band.p25 ?? lo),
            width: `calc(${pos(band.p75 ?? hi)} - ${pos(band.p25 ?? lo)})`,
          }}
        />
        {marks.map((m) => {
          const v = band[m.key];
          if (v == null) return null;
          return (
            <span
              key={m.key}
              className={`band-tick${m.labeled ? "" : " band-tick--end"}`}
              style={{ left: pos(v) }}
              title={`${m.lab}: ${num(v, 2)}`}
            >
              <i />
              {m.labeled && <em>{m.lab}</em>}
            </span>
          );
        })}
        {value != null && (
          <span
            className="band-marker"
            style={{ left: pos(Math.min(hi, Math.max(lo, value))) }}
            title={`Mã: ${num(value, 2)}`}
          >
            {num(value, 1)}
          </span>
        )}
      </div>
      <p className="band-caption muted">
        Đầu–cuối dải P10–P90: {num(lo, 2)} – {num(hi, 2)}.
        {band.p25 != null && band.p75 != null && (
          <> Dải tô P25–P75: {num(band.p25, 2)} – {num(band.p75, 2)}.</>
        )}
        {value != null && <> Mã: {num(value, 2)}</>}
      </p>
    </div>
  );
}

function PeersBar({
  title,
  items,
  field,
}: {
  title: string;
  items: PeerRow[];
  field: "pe" | "pb";
}) {
  const vals = items
    .map((p) => ({ t: p.ticker, v: p[field], self: !!p.is_self }))
    .filter((x) => x.v != null) as Array<{ t: string; v: number; self: boolean }>;
  if (!vals.length) return null;
  const max = Math.max(...vals.map((x) => x.v), 1);
  return (
    <div className="fin-chart-block">
      <h4 className="fin-chart-title">{title}</h4>
      <div className="peer-bars" role="img" aria-label={title}>
        {vals.map((x) => (
          <div className="peer-bar-row" key={x.t}>
            <span className={x.self ? "peer-self" : "muted"}>{x.t}</span>
            <div className="peer-bar-track">
              <div
                className="peer-bar-fill"
                style={{
                  width: `${(x.v / max) * 100}%`,
                  background: x.self ? "var(--accent)" : "var(--series-1)",
                  opacity: x.self ? 1 : 0.55,
                }}
              />
            </div>
            <span className="tabular">{num(x.v, field === "pe" ? 1 : 2)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Thanh biên 52 tuần: low→high, vạch giá hiện tại, vạch tham chiếu ngành
 * chỉ khi |ref/price-1| ≤ 0,5 (đã lọc ở caller qua evaluateRefPrice).
 */
function Range52Bar({
  price,
  refPrice,
  low52,
  high52,
}: {
  price: number | null;
  refPrice: number | null;
  low52: number | null;
  high52: number | null;
}) {
  if (low52 == null || high52 == null || !Number.isFinite(low52) || !Number.isFinite(high52)) {
    return null;
  }
  const lo = Math.min(low52, high52);
  const hi = Math.max(low52, high52);
  const span = hi - lo || 1;
  const pos = (x: number) => Math.max(0, Math.min(100, ((x - lo) / span) * 100));
  const showRef =
    refPrice != null &&
    price != null &&
    price > 0 &&
    Math.abs(refPrice / price - 1) <= 0.5;

  return (
    <div className="fin-chart-block">
      <h4 className="fin-chart-title">Vị trí giá trong biên 52 tuần</h4>
      <div
        className="ff-track ff-track--bar"
        role="img"
        aria-label={`Biên 52 tuần ${vnd(lo)} đến ${vnd(hi)}${
          price != null ? `, giá ${vnd(price)}` : ""
        }`}
      >
        <div className="ff-range ff-range--full" />
        <span className="ff-end-lab ff-end-lab--lo tabular">{vnd(lo)}</span>
        <span className="ff-end-lab ff-end-lab--hi tabular">{vnd(hi)}</span>
        {showRef && refPrice != null && (
          <span
            className="ff-tick ff-tick--ref"
            style={{ left: `${pos(refPrice)}%` }}
            title={`Tham chiếu ngành ${vnd(refPrice)}`}
          >
            <i aria-hidden />
            <em>TC</em>
          </span>
        )}
        {price != null && (
          <span
            className="ff-tick ff-tick--px"
            style={{ left: `${pos(price)}%` }}
            title={`Giá ${vnd(price)}`}
          >
            <i aria-hidden />
            <em>Giá</em>
          </span>
        )}
      </div>
      <div className="chart-legend-row muted" style={{ marginTop: 8 }}>
        {price != null && <span>Giá: {vnd(price)}</span>}
        {showRef && refPrice != null && (
          <span>Tham chiếu ngành: {vnd(refPrice)}</span>
        )}
        {!showRef && refPrice == null && (
          <span>Chỉ biên 52 tuần và giá hiện tại</span>
        )}
      </div>
    </div>
  );
}

export function ValuationCharts(props: {
  isBank: boolean;
  peers: PeerRow[];
  peBand?: PercentileBand | null;
  pbBand?: PercentileBand | null;
  ownPe: number | null;
  ownPb: number | null;
  price: number | null;
  refPrice: number | null;
  low52: number | null;
  high52: number | null;
}) {
  return (
    <div className="fin-charts">
      {!props.isBank && (
        <BandChart title="P/E so với phân vị ngành" value={props.ownPe} band={props.peBand} />
      )}
      <BandChart title="P/B so với phân vị ngành" value={props.ownPb} band={props.pbBand} />
      {!props.isBank && (
        <PeersBar title="P/E cùng ngành" items={props.peers} field="pe" />
      )}
      <PeersBar title="P/B cùng ngành" items={props.peers} field="pb" />
      <Range52Bar
        price={props.price}
        refPrice={props.refPrice}
        low52={props.low52}
        high52={props.high52}
      />
    </div>
  );
}
