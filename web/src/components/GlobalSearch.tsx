import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Profile } from "../api/types";
import { score } from "../fmt";
import { searchRankings } from "../search";
import { sectorVi } from "../sectors";

export function GlobalSearch({ profile = "long_term" }: { profile?: Profile }) {
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const wrapRef = useRef<HTMLDivElement>(null);

  const rankingsQ = useQuery({
    queryKey: ["rankings-all", profile],
    queryFn: () =>
      api.rankings({
        profile,
        limit: 500,
        include_unranked: true,
        sort: "score",
        order: "desc",
      }),
    staleTime: 120_000,
  });

  const hits = useMemo(
    () => searchRankings(rankingsQ.data?.items || [], q, 8),
    [rankingsQ.data, q],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (e.key === "/" && tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
        e.preventDefault();
        inputRef.current?.focus();
        setOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  useEffect(() => setActive(0), [q]);

  const go = (ticker: string) => {
    setOpen(false);
    setQ("");
    nav(`/t/${ticker}?profile=${profile}`);
  };

  return (
    <div className="global-search" ref={wrapRef}>
      <input
        ref={inputRef}
        type="search"
        placeholder="Tìm mã hoặc tên công ty"
        value={q}
        aria-label="Tìm mã hoặc tên công ty"
        aria-autocomplete="list"
        aria-expanded={open && hits.length > 0}
        aria-controls="global-search-list"
        onChange={(e) => {
          setQ(e.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setActive((i) => Math.min(i + 1, Math.max(0, hits.length - 1)));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActive((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter") {
            e.preventDefault();
            const hit = hits[active] || hits[0];
            if (hit) go(hit.ticker);
          } else if (e.key === "Escape") {
            setOpen(false);
            inputRef.current?.blur();
          }
        }}
      />
      {open && q.trim() && (
        <ul id="global-search-list" className="global-search-list" role="listbox">
          {hits.length === 0 && (
            <li className="muted" role="option" aria-selected={false}>
              Không có kết quả
            </li>
          )}
          {hits.map((h, i) => (
            <li key={h.ticker} role="option" aria-selected={i === active}>
              <button
                type="button"
                className={i === active ? "gs-active" : undefined}
                onMouseEnter={() => setActive(i)}
                onClick={() => go(h.ticker)}
              >
                <strong>{h.ticker}</strong>
                <span className="muted gs-name">{h.name || "—"}</span>
                <span className="muted gs-sec">{sectorVi(h.sector)}</span>
                <span className="tabular gs-score">{score(h.score)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
