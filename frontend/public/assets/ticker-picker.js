/* Full snapshot universe picker. Does not use demo stocks or rankings. */
(function () {
  let catalogRequest;
  function loadTickerCatalog() {
    if (!catalogRequest) {
      catalogRequest = fetch("/api/tickers").then(async response => {
        if (!response.ok) throw new Error("Không tải được danh sách mã cổ phiếu.");
        const data = await response.json();
        if (!Array.isArray(data.items)) throw new Error("Danh sách mã không hợp lệ.");
        return data;
      }).catch(error => { catalogRequest = null; throw error; });
    }
    return catalogRequest;
  }
  const normalize = value => String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase().trim();
  function filterTickers(items, query, exchange = "all") {
    const term = normalize(query);
    return items.filter(item => (exchange === "all" || item.exchange === exchange)
      && normalize(`${item.symbol} ${item.name || ""} ${item.sector || ""}`).includes(term))
      .sort((a, b) => Number(normalize(b.symbol) === term) - Number(normalize(a.symbol) === term) || a.symbol.localeCompare(b.symbol));
  }

  function TickerPicker({ react, jsx, isOpen, onClose, onSelectStock, onOpen, title = "Chọn cổ phiếu từ snapshot", enableShortcut = true }) {
    const [catalog, setCatalog] = react.useState(null);
    const [query, setQuery] = react.useState("");
    const [exchange, setExchange] = react.useState("all");
    const [loading, setLoading] = react.useState(false);
    const [error, setError] = react.useState("");
    const [retry, setRetry] = react.useState(0);
    react.useEffect(() => {
      if (!isOpen) return;
      let active = true;
      setLoading(true); setError("");
      loadTickerCatalog().then(data => { if (active) setCatalog(data); })
        .catch(() => { if (active) setError("Không tải được danh sách mã từ backend. Hãy kiểm tra kết nối rồi thử lại."); })
        .finally(() => { if (active) setLoading(false); });
      return () => { active = false; };
    }, [isOpen, retry]);
    react.useEffect(() => {
      const keydown = event => {
        if (event.key === "Escape" && isOpen) onClose();
        if (enableShortcut && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
          event.preventDefault();
          if (isOpen) onClose(); else onOpen?.();
        }
      };
      window.addEventListener("keydown", keydown);
      return () => window.removeEventListener("keydown", keydown);
    }, [isOpen, onClose, onOpen, enableShortcut]);
    if (!isOpen) return null;
    const h = (type, props, key) => (Array.isArray(props.children) ? jsx.jsxs : jsx.jsx)(type, props, key);
    const all = catalog?.items || [];
    const matches = filterTickers(all, query, exchange);
    const exchanges = Array.from(new Set(all.map(item => item.exchange).filter(Boolean))).sort();
    const titleId = enableShortcut ? "ticker-picker-title" : "market-picker-title";
    const number = value => Number.isFinite(value) ? value.toLocaleString("vi-VN", { maximumFractionDigits: 2 }) : "—";
    const choose = item => {
      if (!item || item.snapshot_status === "error") return;
      onSelectStock(item.symbol); onClose();
    };
    return h("div", { className: "fixed inset-0 z-50 flex items-start justify-center pt-20 p-4", children: [
      h("button", { type: "button", "aria-label": "Đóng bộ chọn mã", onClick: onClose, className: "absolute inset-0 bg-[#001735]/40 backdrop-blur-xs" }),
      h("section", { role: "dialog", "aria-modal": true, "aria-labelledby": titleId,
        className: "relative bg-white rounded-xl shadow-2xl border border-[#BFDBFE] p-4 space-y-4", style: { width: "100%", maxWidth: "720px", maxHeight: "80vh", overflowY: "auto" }, children: [
          h("div", { className: "flex items-center justify-between gap-3", children: [
            h("h2", { id: titleId, className: "text-base font-bold", children: title }),
            h("button", { type: "button", onClick: onClose, className: "text-xs text-[#1A56DB]", children: "Đóng (Esc)" })
          ] }),
          h("div", { className: "flex flex-wrap gap-3", children: [
            h("input", { autoFocus: true, type: "search", "aria-label": "Tìm mã hoặc tên doanh nghiệp", value: query,
              placeholder: "Tìm mã, tên doanh nghiệp hoặc ngành (có thể gõ không dấu)",
              onChange: event => setQuery(event.target.value), onKeyDown: event => { if (event.key === "Enter") choose(matches[0]); },
              className: "border border-[#BFDBFE] rounded-lg px-3 py-2 text-sm", style: { flex: "1", minWidth: "220px" } }),
            h("select", { "aria-label": "Lọc sàn giao dịch", value: exchange, onChange: event => setExchange(event.target.value),
              className: "border border-[#BFDBFE] rounded-lg px-3 py-2 text-xs", children: [
                h("option", { value: "all", children: "Tất cả sàn" }, "all"),
                ...exchanges.map(value => h("option", { value, children: value }, value))
              ] })
          ] }),
          h("p", { role: "status", className: "text-xs text-[#68788C]", children: loading ? "Đang tải danh sách mã…"
            : error || `${matches.length} kết quả / ${all.length} mã có snapshot · ${catalog?.asof || "—"}. Giá đóng cửa theo snapshot, đơn vị VND/cổ phiếu.` }),
          error ? h("button", { type: "button", onClick: () => setRetry(value => value + 1), className: "text-xs text-[#1A56DB]", children: "Thử tải lại" }) : null,
          !loading && !error ? h("div", { className: "divide-y divide-[#E1E7EF]", style: { maxHeight: "50vh", overflowY: "auto" }, children: matches.length
            ? matches.map(item => h("button", { type: "button", disabled: item.snapshot_status === "error", onClick: () => choose(item),
              className: "w-full text-left p-3 flex items-center justify-between gap-3 hover:bg-[#EFF6FF] rounded-lg", children: [
                h("div", { children: [h("strong", { className: "text-sm text-[#1A56DB]", children: item.symbol }),
                  h("p", { className: "text-xs text-[#0C1D2D]", children: item.name || item.symbol }),
                  h("p", { className: "text-xs text-[#68788C]", children: `${item.exchange || "Chưa rõ sàn"} · ${item.sector || "Chưa rõ ngành"}` })] }),
                h("div", { className: "text-right text-xs", children: [
                  h("strong", { children: number(item.current_price) }),
                  h("p", { children: Number.isFinite(item.price_change_percent) ? number(item.price_change_percent) + "%" : "—" }),
                  h("p", { className: "text-[#68788C]", children: item.snapshot_status === "error" ? "Không đọc được snapshot" : item.price_date || "Chưa có giá" })
                ] })
              ] }, item.symbol)) : h("p", { className: "text-xs p-4", children: "Không có mã phù hợp trong danh sách snapshot." })
          }) : null
        ] })
    ] });
  }

  Object.assign(window.StockAI, { TickerPicker, loadTickerCatalog, filterTickers });
})();
