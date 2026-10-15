import { Link, Outlet, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { Profile } from "../api/types";
import { dateVi } from "../fmt";
import { useTheme } from "../theme";
import { GlobalSearch } from "./GlobalSearch";
import { MarketStrip } from "./MarketStrip";

function ThemeIcon({ mode }: { mode: "light" | "dark" | "system" }) {
  if (mode === "dark") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <path d="M21 14.5A8.5 8.5 0 0 1 9.5 3 7 7 0 1 0 21 14.5z" />
      </svg>
    );
  }
  if (mode === "light") {
    return (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3v18" />
      <path d="M12 3a9 9 0 0 1 0 18" fill="currentColor" opacity="0.35" />
    </svg>
  );
}

export function Layout() {
  const { mode, cycle } = useTheme();
  const [sp] = useSearchParams();
  const profile = (sp.get("profile") as Profile) || "long_term";
  const meta = useQuery({ queryKey: ["meta"], queryFn: () => api.meta() });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: (q) =>
      q.state.data?.status === "warming" ? 1500 : false,
  });
  const warming = health.data?.status === "warming";

  const themeSr =
    mode === "light"
      ? "Giao diện sáng — nhấn để đổi"
      : mode === "dark"
        ? "Giao diện tối — nhấn để đổi"
        : "Giao diện theo hệ thống — nhấn để đổi";

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-header-left">
          <Link to="/" className="brand">
            StockAI
          </Link>
          <nav className="app-nav" aria-label="Chính">
            <Link to={`/?profile=${profile}`}>Xếp hạng</Link>
            <Link to={`/theo-doi?profile=${profile}`}>Theo dõi</Link>
            <Link to={`/nganh?profile=${profile}`}>Ngành</Link>
            <Link to={`/so-sanh?profile=${profile}`}>So sánh</Link>
            <Link to="/phuong-phap">Phương pháp</Link>
          </nav>
        </div>
        <GlobalSearch profile={profile} />
        <div className="app-header-right">
          <MarketStrip />
          <span className="meta tabular">
            {warming && "Đang chuẩn bị dữ liệu…"}
            {!warming && meta.isLoading && "Đang tải…"}
            {!warming && meta.isError && "Không lấy được ngày dữ liệu — tải lại trang"}
            {!warming && meta.data && <>Dữ liệu đến {dateVi(meta.data.asof)}</>}
          </span>
          <button
            type="button"
            className="theme-toggle"
            onClick={cycle}
            aria-label={themeSr}
            title={themeSr}
          >
            <ThemeIcon mode={mode} />
          </button>
        </div>
      </header>
      {warming && (
        <div className="warmup-banner muted" role="status">
          Đang chuẩn bị dữ liệu…
        </div>
      )}
      <Outlet />
      <footer
        className="muted"
        style={{
          marginTop: 32,
          fontSize: "var(--fs-xs)",
          borderTop: "1px solid var(--rule)",
          paddingTop: 12,
          maxWidth: "70ch",
        }}
      >
        {meta.data?.disclaimer ||
          "Đây không phải lời khuyên đầu tư. Điểm số mang tính minh họa."}
      </footer>
    </div>
  );
}
