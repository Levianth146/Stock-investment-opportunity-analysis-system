/** Số giá tabular — fade màu ~600ms khi đổi; tôn trọng prefers-reduced-motion. */
import { useEffect, useRef, useState } from "react";
import { num } from "../fmt";

export function LivePrice({
  value,
  digits = 0,
  className = "",
}: {
  value: number | null | undefined;
  digits?: number;
  className?: string;
}) {
  const prev = useRef<number | null>(null);
  const [flash, setFlash] = useState<"up" | "down" | null>(null);

  useEffect(() => {
    if (value == null || !Number.isFinite(value)) return;
    const p = prev.current;
    prev.current = value;
    if (p == null || p === value) return;
    const dir = value > p ? "up" : "down";
    const reduced =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return;
    setFlash(dir);
    const t = window.setTimeout(() => setFlash(null), 600);
    return () => clearTimeout(t);
  }, [value]);

  return (
    <span
      className={`live-price tabular ${flash ? `live-price--${flash}` : ""} ${className}`.trim()}
    >
      {num(value ?? null, digits)}
    </span>
  );
}

export function LiveChangePct({
  value,
  className = "",
}: {
  value: number | null | undefined;
  className?: string;
}) {
  if (value == null || Number.isNaN(value)) {
    return <span className={`tabular muted ${className}`.trim()}>—</span>;
  }
  const up = value >= 0;
  return (
    <span className={`tabular ${up ? "pos" : "neg"} ${className}`.trim()}>
      {up ? "+" : ""}
      {num(value, 2)}%
    </span>
  );
}
