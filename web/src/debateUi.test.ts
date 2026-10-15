import { describe, expect, it } from "vitest";
import {
  debateFailLine,
  debateSourceLabel,
  viJobFailReason,
} from "./debateUi";

const formatWhen = (iso: string) => {
  const d = iso.slice(0, 10);
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(d);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
};

describe("debateSourceLabel", () => {
  it("idle → tạo: chỉ nhãn trung tính, không giữ lỗi cũ", () => {
    expect(
      debateSourceLabel({
        isCreating: true,
        source: "TEMPLATE",
        formatWhen,
      }),
    ).toBe("Đang tạo bằng AI…");
  });

  it("idle → tạo → ok: hiện AI · model · ngày", () => {
    expect(
      debateSourceLabel({
        isCreating: false,
        source: "LLM",
        model: "mock-flash",
        createdAt: "2026-10-14T12:00:00Z",
        formatWhen,
      }),
    ).toBe("AI · mock-flash · 14/10/2026");
  });

  it("khi tạo không hiện nhãn AI cũ", () => {
    expect(
      debateSourceLabel({
        isCreating: true,
        source: "LLM",
        model: "old-model",
        createdAt: "2026-01-01T00:00:00Z",
        formatWhen,
      }),
    ).toBe("Đang tạo bằng AI…");
  });
});

describe("debateFailLine", () => {
  it("idle → tạo: ẩn dòng lỗi", () => {
    expect(
      debateFailLine({
        isCreating: true,
        jobError: "AI không tạo được lần này — đang hiện luận điểm từ chỉ số.",
        clickedAi: true,
        viReason: viJobFailReason,
      }),
    ).toBeNull();
  });

  it("idle → tạo → failed: một lý do tiếng Việt", () => {
    expect(
      debateFailLine({
        isCreating: false,
        jobError: null,
        clickedAi: true,
        aiAttemptState: "failed",
        reasonCode: "all_providers_failed",
        viReason: viJobFailReason,
      }),
    ).toBe("AI không tạo được lần này — đang hiện luận điểm từ chỉ số.");
  });

  it("failed → tạo lại: lỗi biến mất ngay khi isCreating", () => {
    const failed = debateFailLine({
      isCreating: false,
      jobError: "AI không tạo được lần này — đang hiện luận điểm từ chỉ số.",
      clickedAi: true,
      viReason: viJobFailReason,
    });
    expect(failed).toMatch(/AI không tạo được/);
    expect(
      debateFailLine({
        isCreating: true,
        jobError: null,
        clickedAi: true,
        viReason: viJobFailReason,
      }),
    ).toBeNull();
  });
});
