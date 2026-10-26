import { priceKind } from "../live/staleness";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import { useTheme } from "../theme";
import { useLiveQuotes } from "../live/LiveContext";
import { changeToColor } from "../home/colorScale";
import { analyze, withLive, VERDICT_VI, type Bar, type Gauge, type Sig } from "../technical/indicators";
import { narrate } from "../technical/narrative";

const SIG_VI: Record<Sig, string> = { buy: "Mua", neutral: "Trung tính", sell: "Bán" };

function todayVN(): string {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date());
}

function GaugeDial({ title, g, dark }: { title: string; g: Gauge; dark: boolean }) {
  const cx = 80;
  const cy = 76;
  const r = 60;
  const stops = [-5, -2, 0, 2, 5];
  const arc = (i: number) => {
    const a0 = Math.PI * (1 - i / 5);
    const a1 = Math.PI * (1 - (i + 1) / 5);
    const p = (a: number) => `${cx + r * Math.cos(a)},${cy - r * Math.sin(a)}`;
    return `M ${p(a0)} A ${r} ${r} 0 0 1 ${p(a1)}`;
  };
  const ang = Math.PI * (1 - (g.score + 1) / 2);
  const nx = cx + (r - 8) * Math.cos(ang);
  const ny = cy - (r - 8) * Math.sin(ang);
  return (
    <figure className="ta-gauge">
      <figcaption className="ta-gauge-title">{title}</figcaption>
      <svg viewBox="0 0 160 92" width="160" height="92" role="img" aria-label={`${title}: ${VERDICT_VI[g.verdict]}`}>
        {stops.map((s, i) => (
          <path key={s} d={arc(i)} stroke={changeToColor(s, { dark })} strokeWidth="12" fill="none" />
        ))}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="var(--ink)" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx={cx} cy={cy} r="4" fill="var(--ink)" />
      </svg>
      <div className="ta-gauge-verdict">{VERDICT_VI[g.verdict]}</div>
      <div className="muted ta-gauge-counts tabular">
        Mua {g.buy} · Trung tính {g.neutral} · Bán {g.sell}
      </div>
    </figure>
  );
}

export function TechnicalSummary({ symbol }: { symbol: string }) {
  const { resolved } = useTheme();
  const dark = resolved === "dark";
  const q = useQuery({
    queryKey: ["prices-ta", symbol],
    queryFn: () => api.prices(symbol, { range: "all", include_index: false, include_indicators: false }),
    staleTime: 300_000,
  });
  const quote = useLiveQuotes([symbol])[symbol];
  const kind = priceKind(quote);
  const liveOk = kind !== "eod";

  const bars = useMemo<Bar[]>(() => {
    return (q.data?.ohlcv || [])
      .filter((b) => b.close != null)
      .map((b) => ({
        time: b.time,
        open: b.open ?? b.close!,
        high: b.high ?? b.close!,
        low: b.low ?? b.close!,
        close: b.close!,
        volume: b.volume ?? 0,
      }));
  }, [q.data]);

  const lastBarDate = bars.length ? bars[bars.length - 1]!.time.slice(0, 10) : null;
  const price = liveOk ? quote!.price! : null;
  const volume = liveOk ? (quote!.volume ?? null) : null;
  const high = liveOk ? (quote!.high ?? null) : null;
  const low = liveOk ? (quote!.low ?? null) : null;
  const res = useMemo(() => {
    const live = price != null ? { price, volume, high, low } : null;
    return analyze(withLive(bars, live, todayVN()));
  }, [bars, price, volume, high, low]);
  const blocks = useMemo(() => (res ? narrate(res) : []), [res]);

  if (q.isLoading) return <div className="skeleton" aria-busy="true" />;
  if (!res) return <p className="muted">Chưa đủ dữ liệu giá (cần ≥30 phiên) để phân tích kỹ thuật.</p>;

  return (
    <section className="ta-summary" aria-label="Phân tích kỹ thuật">
      <p className="muted ta-basis">
        {liveOk
          ? kind === "close"
            ? `Tính trên ${res.bars} phiên, nến hôm nay dùng giá chốt phiên ${res.last.toLocaleString("vi-VN")} (tạm tính, chưa có dữ liệu EOD).`
            : `Tính trên ${res.bars} phiên, nến hôm nay dùng giá trực tiếp ${res.last.toLocaleString("vi-VN")} (cập nhật theo luồng giá).`
          : `Tính trên ${res.bars} phiên đến ${lastBarDate ?? "—"} (giá đóng cửa; chưa có giá trực tiếp).`}
      </p>
      <div className="ta-gauges">
        <GaugeDial title="Đường trung bình" g={res.ma} dark={dark} />
        <GaugeDial title="Chỉ báo dao động" g={res.osc} dark={dark} />
        <GaugeDial title="Tổng hợp" g={res.all} dark={dark} />
      </div>
      <h3 className="ta-h">Diễn giải</h3>
      <dl className="ta-narr">
        {blocks.map((b) => (
          <div key={b.head}>
            <dt>{b.head}</dt>
            <dd>{b.text}</dd>
          </div>
        ))}
      </dl>
      <h3 className="ta-h">Chi tiết chỉ báo</h3>
      <table className="ta-table">
        <thead>
          <tr>
            <th scope="col">Chỉ báo</th>
            <th scope="col">Giá trị</th>
            <th scope="col">Tín hiệu</th>
            <th scope="col">Ghi chú</th>
          </tr>
        </thead>
        <tbody>
          {res.rows.map((r) => (
            <tr key={r.id}>
              <td>{r.name}</td>
              <td className="tabular">{r.value}</td>
              <td className={`ta-sig ta-sig--${r.signal}`}>{SIG_VI[r.signal]}</td>
              <td className="muted">{r.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
