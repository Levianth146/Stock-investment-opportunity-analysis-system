import { describe, expect, it } from "vitest";
import { buildIncomeFlow, checkConservation } from "./incomeFlow";

describe("buildIncomeFlow", () => {
  it("bảo toàn trong sai số 0,5% (fixture đủ chỉ tiêu)", () => {
    const f = buildIncomeFlow({
      revenue: 1000,
      gross_profit: 400,
      selling_expense: 50,
      admin_expense: 50,
      interest_expense: 30,
      pretax_profit: 240,
      net_income: 200,
      net_income_parent: 180,
    });
    expect(f).not.toBeNull();
    expect(f!.conservation_ok).toBe(true);
    expect(checkConservation(f!.nodes, f!.links)).toBe(true);
    expect(f!.links.every((l) => l.value >= 0)).toBe(true);
    // Giá vốn + LN gộp = doanh thu
    const cogs = f!.nodes.find((n) => n.id === "cogs")!.value;
    const gp = f!.nodes.find((n) => n.id === "gross_profit")!.value;
    expect(Math.abs(cogs + gp - 1000)).toBeLessThanOrEqual(5);
    expect(f!.nodes.some((n) => n.id === "other_balance")).toBe(true);
    expect(f!.nodes.find((n) => n.id === "other_balance")!.derived).toBe(true);
  });

  it("thiếu chỉ tiêu → bỏ nút + note, không điền 0", () => {
    const f = buildIncomeFlow({
      revenue: 500,
      gross_profit: 200,
      net_income_parent: 80,
    });
    expect(f).not.toBeNull();
    expect(f!.conservation_ok).toBe(true);
    expect(f!.nodes.some((n) => n.id === "selling")).toBe(false);
    expect(f!.nodes.some((n) => n.id === "admin")).toBe(false);
    expect(f!.nodes.some((n) => n.id === "interest")).toBe(false);
    expect(f!.notes.some((n) => /bán hàng/i.test(n))).toBe(true);
    // Không có nút value === 0 bịa ra cho expense thiếu
    expect(f!.nodes.every((n) => n.value > 0)).toBe(true);
  });

  it("LNST âm → nút Lỗ + Thu nhập khác (ròng) khi cần; link ≥ 0", () => {
    const f = buildIncomeFlow({
      revenue: 200,
      gross_profit: 40,
      selling_expense: 30,
      admin_expense: 20,
      interest_expense: 5,
      pretax_profit: -10,
      net_income: -15,
      net_income_parent: -15,
    });
    expect(f).not.toBeNull();
    expect(f!.loss).toBe(true);
    expect(f!.nodes.some((n) => n.id === "loss")).toBe(true);
    expect(f!.nodes.find((n) => n.id === "loss")!.kind).toBe("loss");
    expect(f!.nodes.some((n) => n.id === "npat")).toBe(false);
    expect(f!.links.every((l) => l.value >= 0)).toBe(true);
    expect(f!.conservation_ok).toBe(true);
    expect(f!.notes.some((n) => /Lỗ/i.test(n))).toBe(true);
    // Chi phí vượt LN gộp → nguồn bổ sung
    expect(f!.nodes.some((n) => n.id === "other_income")).toBe(true);
  });

  it("thiếu doanh thu hoặc LNST → null", () => {
    expect(buildIncomeFlow({ revenue: 100 })).toBeNull();
    expect(buildIncomeFlow({ net_income_parent: 10 })).toBeNull();
  });
});
