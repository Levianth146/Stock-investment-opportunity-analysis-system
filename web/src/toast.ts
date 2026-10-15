/** Toast tối giản — một dòng, tự ẩn. */

let host: HTMLDivElement | null = null;
let hideTimer: ReturnType<typeof setTimeout> | null = null;

function ensureHost(): HTMLDivElement {
  if (host && document.body.contains(host)) return host;
  host = document.createElement("div");
  host.className = "toast-host";
  host.setAttribute("role", "status");
  host.setAttribute("aria-live", "polite");
  document.body.appendChild(host);
  return host;
}

export function showToast(message: string, ms = 2800): void {
  const el = ensureHost();
  el.textContent = message;
  el.dataset.visible = "1";
  if (hideTimer) clearTimeout(hideTimer);
  hideTimer = setTimeout(() => {
    el.dataset.visible = "0";
  }, ms);
}
