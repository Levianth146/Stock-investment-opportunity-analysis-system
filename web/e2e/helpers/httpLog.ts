/** Ghi mọi HTTP status >= 400 vào test report (không nuốt 404). */
import type { Page, TestInfo } from "@playwright/test";

export function attachHttpErrorLog(page: Page, _testInfo: TestInfo): string[] {
  const lines: string[] = [];
  page.on("response", (res) => {
    if (res.status() < 400) return;
    const line = `${res.status()} ${res.request().method()} ${res.url()}`;
    lines.push(line);
    // eslint-disable-next-line no-console
    console.log(`[http>=400] ${line}`);
  });
  return lines;
}

export async function flushHttpErrorLog(
  lines: string[],
  testInfo: TestInfo,
): Promise<void> {
  const body = lines.length ? lines.join("\n") : "(không có status >= 400)";
  await testInfo.attach("http-errors", {
    body,
    contentType: "text/plain",
  });
}
