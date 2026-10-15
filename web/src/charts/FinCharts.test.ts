import { describe, expect, it } from "vitest";
import { formatQuarterLabel, maxXLabels } from "./FinCharts";

describe("FinCharts labels", () => {
  it("formats Q2/26", () => {
    expect(formatQuarterLabel("2026Q2")).toBe("Q2/26");
    expect(formatQuarterLabel("2025-Q4")).toBe("Q4/25");
  });

  it("thins x labels by width", () => {
    expect(maxXLabels(360, 12)).toBeLessThanOrEqual(4);
    expect(maxXLabels(1280, 12)).toBe(12);
  });
});
