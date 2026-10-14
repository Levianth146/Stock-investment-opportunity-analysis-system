import { useEffect, useRef } from "react";
import {
  createChart,
  type IChartApi,
  type Time,
  type MouseEventParams,
} from "lightweight-charts";
import type { PricesResponse } from "../api/types";
import { chartColors, rebaseTo100 } from "./chartTheme";
import {
  applyViTimeScale,
  chartLocalization,
  priceFormatter,
  timeTickFormatter,
} from "./chartLocale";

const PRICE_CHART_MIN_H = 280;

/** Giá 1 năm + MA50; bên dưới biểu đồ riêng so với VN-Index (gốc 100). */
export function OverviewPriceChart({ data }: { data: PricesResponse }) {
  const priceRef = useRef<HTMLDivElement>(null);
  const cmpRef = useRef<HTMLDivElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!priceRef.current) return;
    const el = priceRef.current;
    const c = chartColors();
    const chart: IChartApi = createChart(el, {
      width: Math.max(el.clientWidth, 1),
      height: Math.max(el.clientHeight || PRICE_CHART_MIN_H, PRICE_CHART_MIN_H),
      layout: {
        background: { color: "transparent" },
        textColor: c.ink3,
      },
      localization: chartLocalization("price"),
      grid: {
        vertLines: { color: "transparent" },
        horzLines: { color: c.grid },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { mode: 0 },
    });
    applyViTimeScale(chart);

    const line = chart.addLineSeries({
      color: c.series1,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
    });
    const closes = data.ohlcv
      .filter((b) => b.close != null)
      .map((b) => ({ time: b.time as Time, value: Number(b.close) }));
    line.setData(closes);

    if (data.indicators?.ma50?.length) {
      const ma = chart.addLineSeries({
        color: c.series2,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      ma.setData(
        data.indicators.ma50
          .filter((p) => p.value != null)
          .map((p) => ({ time: p.time as Time, value: Number(p.value) })),
      );
    }

    chart.subscribeCrosshairMove((param: MouseEventParams) => {
      const tip = tipRef.current;
      if (!tip) return;
      if (!param.time || !param.point) {
        tip.style.display = "none";
        return;
      }
      const hit = closes.find((p) => p.time === param.time);
      if (!hit) {
        tip.style.display = "none";
        return;
      }
      tip.style.display = "block";
      tip.textContent = `${timeTickFormatter(String(param.time))}  ${priceFormatter(hit.value)}`;
    });

    chart.timeScale().fitContent();

    const applySize = () => {
      const w = Math.max(el.clientWidth, 1);
      const h = Math.max(el.clientHeight || PRICE_CHART_MIN_H, PRICE_CHART_MIN_H);
      chart.applyOptions({ width: w, height: h });
    };
    applySize();
    const ro = new ResizeObserver(() => applySize());
    ro.observe(el);
    window.addEventListener("resize", applySize);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", applySize);
      chart.remove();
    };
  }, [data]);

  useEffect(() => {
    if (!cmpRef.current || !data.index?.series?.length) return;
    const el = cmpRef.current;
    const c = chartColors();
    const priceReb = rebaseTo100(
      data.ohlcv.map((b) => ({ time: b.time, close: b.close })),
    );
    const idxReb = rebaseTo100(data.index.series);
    if (!priceReb.length && !idxReb.length) return;

    const chart: IChartApi = createChart(el, {
      width: Math.max(el.clientWidth, 1),
      height: Math.max(el.clientHeight || 140, 140),
      layout: {
        background: { color: "transparent" },
        textColor: c.ink3,
      },
      localization: chartLocalization("ratio"),
      grid: {
        vertLines: { color: "transparent" },
        horzLines: { color: c.grid },
      },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { mode: 0 },
    });
    applyViTimeScale(chart);

    if (priceReb.length) {
      const px = chart.addLineSeries({
        color: c.series1,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      px.setData(
        priceReb.map((p) => ({ time: p.time as Time, value: p.value })),
      );
    }
    if (idxReb.length) {
      const idx = chart.addLineSeries({
        color: c.ink2,
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      idx.setData(
        idxReb.map((p) => ({ time: p.time as Time, value: p.value })),
      );
    }

    chart.timeScale().fitContent();
    const applySize = () => {
      const w = Math.max(el.clientWidth, 1);
      const h = Math.max(el.clientHeight || 140, 140);
      chart.applyOptions({ width: w, height: h });
    };
    applySize();
    const ro = new ResizeObserver(() => applySize());
    ro.observe(el);
    window.addEventListener("resize", applySize);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", applySize);
      chart.remove();
    };
  }, [data]);

  const hasIndex = !!data.index?.series?.length;

  return (
    <div className="overview-price-stack">
      <div className="chart-legend-row muted">
        <span>
          <i
            style={{
              display: "inline-block",
              width: 12,
              height: 2,
              background: "var(--series-1)",
              marginRight: 4,
              verticalAlign: "middle",
            }}
            aria-hidden
          />
          Giá
        </span>
        <span>
          <i
            style={{
              display: "inline-block",
              width: 12,
              height: 2,
              background: "var(--series-2)",
              marginRight: 4,
              verticalAlign: "middle",
            }}
            aria-hidden
          />
          MA50
        </span>
      </div>
      <div ref={tipRef} className="chart-tooltip" style={{ display: "none" }} />
      <div
        className="chart-box chart-box--price"
        ref={priceRef}
        role="img"
        aria-label="Biểu đồ giá 1 năm"
      />
      {hasIndex && (
        <>
          <div className="chart-pane-label muted">So với VN-Index (gốc 100)</div>
          <div className="chart-legend-row muted">
            <span>
              <i
                style={{
                  display: "inline-block",
                  width: 12,
                  height: 2,
                  background: "var(--series-1)",
                  marginRight: 4,
                  verticalAlign: "middle",
                }}
                aria-hidden
              />
              Mã (gốc 100)
            </span>
            <span>
              <i
                style={{
                  display: "inline-block",
                  width: 12,
                  height: 2,
                  background: "var(--ink-2)",
                  marginRight: 4,
                  verticalAlign: "middle",
                }}
                aria-hidden
              />
              VN-Index (gốc 100)
            </span>
          </div>
          <div
            className="chart-box chart-box--cmp"
            ref={cmpRef}
            role="img"
            aria-label="So với VN-Index gốc 100"
          />
        </>
      )}
    </div>
  );
}
