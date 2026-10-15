/** Định dạng trục/tooltip lightweight-charts kiểu Việt Nam. */

import type { IChartApi } from "lightweight-charts";
import { dateVi, num } from "../fmt";

/** Giá: 0 chữ số thập phân (30.000). */
export function priceFormatter(v: number): string {
  return num(v, 0);
}

/** Tỷ số (P/E…): 1 chữ số. */
export function ratioFormatter(v: number): string {
  return num(v, 1);
}

/** Beta: 2 chữ số. */
export function betaFormatter(v: number): string {
  return num(v, 2);
}

/** Trục thời gian: dd/MM. */
export function timeTickFormatter(time: string | number): string {
  const s = String(time);
  if (/^\d{4}-\d{2}-\d{2}/.test(s)) {
    return `${s.slice(8, 10)}/${s.slice(5, 7)}`;
  }
  return dateVi(s).slice(0, 5);
}

/** Tuỳ chọn localization chung cho createChart. */
export function chartLocalization(kind: "price" | "ratio" | "volume" = "price") {
  const fmt =
    kind === "ratio"
      ? ratioFormatter
      : kind === "volume"
        ? (v: number) => num(v, 0)
        : priceFormatter;
  return {
    locale: "vi-VN",
    dateFormat: "dd/MM",
    priceFormatter: fmt,
  };
}

/** timeScale.tickMarkFormatter — ép kiểu vì bản typings 4.2 thiếu field. */
export function applyViTimeScale(chart: IChartApi): void {
  chart.timeScale().applyOptions({
    tickMarkFormatter: (t: unknown) =>
      timeTickFormatter(t as string | number),
  } as Parameters<ReturnType<IChartApi["timeScale"]>["applyOptions"]>[0]);
}
