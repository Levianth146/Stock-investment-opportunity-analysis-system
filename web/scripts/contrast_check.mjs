/** Kiểm tra tương phản WCAG AA (4.5:1 chữ thường) cho token 014d. */

function hexToRgb(hex) {
  const h = hex.replace("#", "");
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255,
  ];
}

function lin(c) {
  return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function lum(hex) {
  const [r, g, b] = hexToRgb(hex).map(lin);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a, b) {
  const L1 = lum(a);
  const L2 = lum(b);
  const hi = Math.max(L1, L2);
  const lo = Math.min(L1, L2);
  return (hi + 0.05) / (lo + 0.05);
}

const light = {
  paper: "#F4F6F7",
  ink: "#11202B",
  ink2: "#52606B",
  ink3: "#5A6772",
  accent: "#0B6E87",
  strongBuy: "#0B7A4B",
  buy: "#1B7A50",
  hold: "#5E6B76",
  reduce: "#9A5A12",
  sell: "#C62F2F",
};

const dark = {
  paper: "#0E1418",
  ink: "#E6EDF2",
  ink2: "#9AA8B3",
  ink3: "#7C8A95",
  accent: "#4FB6CE",
  strongBuy: "#3DAB72",
  buy: "#4DB887",
  hold: "#9AA8B3",
  reduce: "#E0944A",
  sell: "#E05555",
};

function report(name, theme) {
  const pairs = [
    ["ink/paper", theme.ink, theme.paper],
    ["ink-2/paper", theme.ink2, theme.paper],
    ["ink-3/paper", theme.ink3, theme.paper],
    ["accent/paper", theme.accent, theme.paper],
    ["strong-buy/paper", theme.strongBuy, theme.paper],
    ["buy/paper", theme.buy, theme.paper],
    ["hold/paper", theme.hold, theme.paper],
    ["reduce/paper", theme.reduce, theme.paper],
    ["sell/paper", theme.sell, theme.paper],
  ];
  console.log(`\n=== ${name} ===`);
  let fail = 0;
  for (const [label, fg, bg] of pairs) {
    const r = contrast(fg, bg);
    const ok = r >= 4.5;
    if (!ok) fail += 1;
    console.log(
      `${ok ? "OK" : "FAIL"} ${label}: ${r.toFixed(2)}:1 (${fg} on ${bg})`,
    );
  }
  return fail;
}

const f = report("light", light) + report("dark", dark);
process.exit(f ? 1 : 0);
