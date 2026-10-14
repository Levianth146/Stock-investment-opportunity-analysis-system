import { useEffect, useRef } from "react";
import {
  createChart,
  type IChartApi,
  type CandlestickData,
  type Time,
  type MouseEventParams,
} from "lightweight-charts";
import type { PricesResponse } from "../api/types";
import { chartColors } from "./chartTheme";
import {
  applyViTimeScale,
  chartLocalization,
  priceFormatter,
  timeTickFormatter,
} from "./chartLocale";

/** Pane đồng bộ: nến+MA, volume, RSI, MACD. VN-Index không trên trục giá. */
export function TechnicalChart({ data }: { data: PricesResponse }) {
  const priceRef = useRef<HTMLDivElement>(null);
  const volRef = useRef<HTMLDivElement>(null);
  const rsiRef = useRef<HTMLDivElement>(null);
  const macdRef = useRef<HTMLDivElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!priceRef.current || !volRef.current || !rsiRef.current || !macdRef.current)
      return;
    const c = chartColors();
    const charts: IChartApi[] = [];
    const mk = (el: HTMLDivElement, h: number, kind: "price" | "ratio" | "volume" = "price") => {
      const chart = createChart(el, {
        width: el.clientWidth,
        height: h,
        layout: { background: { color: "transparent" }, textColor: c.ink3 },
        localization: chartLocalization(kind),
        grid: {
          vertLines: { color: "transparent" },
          horzLines: { color: c.grid },
        },
        rightPriceScale: { borderVisible: false },
        timeScale: { borderVisible: false, visible: el === macdRef.current },
        crosshair: { mode: 0 },
      });
      applyViTimeScale(chart);
      charts.push(chart);
      return chart;
    };

    const priceChart = mk(priceRef.current, 260, "price");
    const candles = priceChart.addCandlestickSeries({
      upColor: c.up,
      downColor: c.down,
      borderVisible: false,
      wickUpColor: c.up,
      wickDownColor: c.down,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    const bars: CandlestickData[] = data.ohlcv
      .filter((b) => b.close != null && b.open != null && b.high != null && b.low != null)
      .map((b) => ({
        time: b.time as Time,
        open: Number(b.open),
        high: Number(b.high),
        low: Number(b.low),
        close: Number(b.close),
      }));
    candles.setData(bars);

    const addMa = (
      points: { time: string; value: number | null }[] | undefined,
      color: string,
    ) => {
      if (!points?.length) return;
      const s = priceChart.addLineSeries({
        color,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      s.setData(
        points
          .filter((p) => p.value != null)
          .map((p) => ({ time: p.time as Time, value: Number(p.value) })),
      );
    };
    addMa(data.indicators?.ma20, c.series1);
    addMa(data.indicators?.ma50, c.series2);
    addMa(data.indicators?.ma200, c.series3);

    const volChart = mk(volRef.current, 80, "volume");
    const vol = volChart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceLineVisible: false,
    });
    vol.setData(
      data.ohlcv
        .filter((b) => b.volume != null && b.close != null && b.open != null)
        .map((b) => ({
          time: b.time as Time,
          value: Number(b.volume),
          color:
            Number(b.close) >= Number(b.open)
              ? `${c.up}99`
              : `${c.down}99`,
        })),
    );

    const rsiChart = mk(rsiRef.current, 90, "ratio");
    const rsi = rsiChart.addLineSeries({
      color: c.series1,
      lineWidth: 2,
      priceLineVisible: false,
    });
    if (data.indicators?.rsi14) {
      rsi.setData(
        data.indicators.rsi14
          .filter((p) => p.value != null)
          .map((p) => ({ time: p.time as Time, value: Number(p.value) })),
      );
    }
    const mark = (level: number) => {
      const first = bars[0];
      const last = bars[bars.length - 1];
      if (!first || !last) return;
      const s = rsiChart.addLineSeries({
        color: c.ink2,
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      });
      s.setData([
        { time: first.time, value: level },
        { time: last.time, value: level },
      ]);
    };
    if (bars.length >= 2) {
      mark(30);
      mark(70);
    }

    const macdChart = mk(macdRef.current, 100, "ratio");
    if (data.indicators?.hist) {
      const hist = macdChart.addHistogramSeries({
        priceLineVisible: false,
      });
      hist.setData(
        data.indicators.hist
          .filter((p) => p.value != null)
          .map((p) => ({
            time: p.time as Time,
            value: Number(p.value),
            color: Number(p.value) >= 0 ? `${c.up}aa` : `${c.down}aa`,
          })),
      );
    }
    if (data.indicators?.macd) {
      const macd = macdChart.addLineSeries({
        color: c.series1,
        lineWidth: 2,
        priceLineVisible: false,
      });
      macd.setData(
        data.indicators.macd
          .filter((p) => p.value != null)
          .map((p) => ({ time: p.time as Time, value: Number(p.value) })),
      );
    }
    if (data.indicators?.signal) {
      const sig = macdChart.addLineSeries({
        color: c.series2,
        lineWidth: 2,
        priceLineVisible: false,
      });
      sig.setData(
        data.indicators.signal
          .filter((p) => p.value != null)
          .map((p) => ({ time: p.time as Time, value: Number(p.value) })),
      );
    }

    const syncing = { lock: false };
    const syncRange = (source: IChartApi) => {
      source.timeScale().subscribeVisibleLogicalRangeChange((range) => {
        if (!range || syncing.lock) return;
        syncing.lock = true;
        for (const ch of charts) {
          if (ch !== source) ch.timeScale().setVisibleLogicalRange(range);
        }
        syncing.lock = false;
      });
    };
    charts.forEach(syncRange);

    priceChart.subscribeCrosshairMove((param: MouseEventParams) => {
      const tip = tipRef.current;
      if (!tip) return;
      if (!param.time || !param.point) {
        tip.style.display = "none";
        return;
      }
      const bar = bars.find((b) => b.time === param.time);
      if (!bar) {
        tip.style.display = "none";
        return;
      }
      tip.style.display = "block";
      tip.textContent = `${timeTickFormatter(String(param.time))}  O ${priceFormatter(bar.open)}  H ${priceFormatter(bar.high)}  L ${priceFormatter(bar.low)}  C ${priceFormatter(bar.close)}`;
    });

    priceChart.timeScale().fitContent();
    const onResize = () => {
      for (const ch of charts) {
        const host = ch === priceChart
          ? priceRef.current
          : ch === volChart
            ? volRef.current
            : ch === rsiChart
              ? rsiRef.current
              : macdRef.current;
        if (host) ch.applyOptions({ width: host.clientWidth });
      }
    };
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      charts.forEach((ch) => ch.remove());
    };
  }, [data]);

  return (
    <div className="tech-stack">
      <div className="chart-legend-row muted">
        <span>
          <i style={{ display: "inline-block", width: 12, height: 2, background: "var(--series-1)", marginRight: 4, verticalAlign: "middle" }} aria-hidden />
          MA20
        </span>
        <span>
          <i style={{ display: "inline-block", width: 12, height: 2, background: "var(--series-2)", marginRight: 4, verticalAlign: "middle" }} aria-hidden />
          MA50
        </span>
        <span>
          <i style={{ display: "inline-block", width: 12, height: 2, background: "var(--series-3)", marginRight: 4, verticalAlign: "middle" }} aria-hidden />
          MA200
        </span>
      </div>
      <div ref={tipRef} className="chart-tooltip" style={{ display: "none" }} />
      <div className="chart-box chart-box--tight" ref={priceRef} role="img" aria-label="Nến và MA" />
      <div className="chart-pane-label muted">Khối lượng</div>
      <div className="chart-box chart-box--tight" ref={volRef} role="img" aria-label="Khối lượng" />
      <div className="chart-pane-label muted">RSI14 (30 / 70)</div>
      <div className="chart-box chart-box--tight" ref={rsiRef} role="img" aria-label="RSI" />
      <div className="chart-pane-label muted">MACD</div>
      <div className="chart-box chart-box--tight" ref={macdRef} role="img" aria-label="MACD" />
    </div>
  );
}
