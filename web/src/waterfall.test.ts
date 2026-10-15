import { describe, expect, it } from "vitest";
import { buildIncomeBridge, sumPeriodItems } from "./waterfall";

describe("buildIncomeBridge", () => {
  it("reconciles within 1e-6", () => {
    const b = buildIncomeBridge({
      revenue: 1000,
      gross_profit: 400,
      selling_expense: 50,
      admin_expense: 50,
      ebit: 280,
      interest_expense: 30,
      pretax_profit: 240,
      net_income_parent: 200,
    });
    expect(b).not.toBeNull();
    expect(b!.reconcile_ok).toBe(true);
    let check = b!.start;
    for (const s of b!.steps.slice(1)) {
      if (s.kind === "delta") check += s.value;
      else {
        expect(Math.abs(check - s.value)).toBeLessThanOrEqual(1e-6);
        check = s.value;
      }
    }
    expect(Math.abs(check - b!.end)).toBeLessThanOrEqual(1e-6);
  });

  it("merges missing into Khác", () => {
    const b = buildIncomeBridge({ revenue: 500, net_income_parent: 80 });
    expect(b!.reconcile_ok).toBe(true);
    const deltas = b!.steps.filter((s) => s.kind === "delta").reduce((a, s) => a + s.value, 0);
    expect(Math.abs(b!.start + deltas - b!.end)).toBeLessThanOrEqual(1e-6);
  });
});

describe("sumPeriodItems", () => {
  it("sums TTM", () => {
    const acc = sumPeriodItems(
      [
        { items: { revenue: 10, net_income_parent: 1 } },
        { items: { revenue: 20, net_income_parent: 2 } },
        { items: { revenue: 30 } },
        { items: { revenue: 40, net_income_parent: 4 } },
      ],
      ["revenue", "net_income_parent"],
    );
    expect(acc.revenue).toBe(100);
    expect(acc.net_income_parent).toBe(7);
  });
});
