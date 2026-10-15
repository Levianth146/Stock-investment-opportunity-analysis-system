/* Snapshot-backed panels for the supplied React build. Port to source when restored. */
(function () {
  const labels = {
    close: "Giá đóng cửa", ma20: "SMA 20", ma50: "SMA 50", ma200: "SMA 200",
    rsi14: "RSI 14", macd: "MACD", macd_signal: "Đường tín hiệu MACD", macd_histogram: "MACD Histogram",
    volume: "Khối lượng phiên cuối", volume_ma20: "Khối lượng trung bình 20 phiên", volume_ratio_20: "Khối lượng / Trung bình 20 phiên",
    atr14: "ATR 14", atr_pct: "ATR / Giá đóng cửa", observations: "Số phiên tính chỉ báo", invalid_price_rows: "Dòng giá không hợp lệ",
    trend_score: "Điểm xu hướng", momentum_score: "Điểm động lượng", volume_score: "Điểm khối lượng",
    volatility_score: "Điểm biến động", technical_score: "Điểm kỹ thuật tổng hợp",
    price_close: "Giá dùng để định giá", eps_used: "EPS dùng để định giá", book_per_share: "Giá trị sổ sách / Cổ phiếu",
    pe: "P/E", pb: "P/B", sector_median_pe: "P/E trung vị tham chiếu", sector_median_pb: "P/B trung vị tham chiếu",
    sector_n_pe: "Số mẫu P/E tham chiếu", sector_n_pb: "Số mẫu P/B tham chiếu", sector_stats_version: "Phiên bản thống kê tham chiếu",
    v_pe_leg: "Điểm thành phần P/E", v_pb_leg: "Điểm thành phần P/B", score_V: "Điểm định giá",
    aligned_observations: "Số phiên khớp cổ phiếu và chỉ số", future_rows_excluded: "Dòng tương lai đã loại", gap_returns_excluded: "Lợi suất gián đoạn đã loại",
    annualized_volatility: "Biến động lịch sử quy đổi năm", benchmark_volatility: "Biến động chỉ số tham chiếu",
    beta: "Beta so với chỉ số", max_drawdown: "Mức sụt giảm tối đa lịch sử", benchmark_max_drawdown: "Sụt giảm tối đa của chỉ số",
    historical_var_95: "VaR lịch sử 95% / Phiên", historical_cvar_95: "CVaR lịch sử 95% / Phiên",
    negative_sessions: "Số phiên giảm", positive_sessions: "Số phiên tăng", last_aligned_date: "Số ngày từ phiên khớp cuối",
    volatility_risk_subscore: "Điểm rủi ro biến động", drawdown_risk_subscore: "Điểm rủi ro sụt giảm",
    var_risk_subscore: "Điểm rủi ro VaR", tail_risk_subscore: "Điểm rủi ro đuôi", beta_risk_subscore: "Điểm rủi ro Beta",
    news_input_count: "Số tin đầu vào", news_relevant_count: "Số tin liên quan", news_directional_count: "Tin có sắc thái tích cực / tiêu cực",
    news_positive_count: "Tin tích cực", news_negative_count: "Tin tiêu cực", news_neutral_count: "Tin trung tính",
    news_duplicate_count: "Tin trùng đã loại", news_future_excluded: "Tin tương lai đã loại", news_old_excluded: "Tin quá cũ đã loại",
    news_offtopic_excluded: "Tin ngoài chủ đề đã loại", news_distinct_sources: "Số nguồn phân biệt", news_newest_age_days: "Tuổi tin mới nhất",
    news_story_count: "Số câu chuyện tin tức", news_multi_ticker_weighted: "Tin nhiều mã được giảm trọng số",
    sentiment_confidence: "Độ phủ heuristic (0–1)", sentiment_polarity: "Sắc thái tổng hợp (−1 đến 1)", sentiment_score: "Điểm sentiment (0–100)",
    roe: "ROE", roa: "ROA", revenue_growth: "Tăng trưởng doanh thu", net_income_growth: "Tăng trưởng lợi nhuận"
  };
  const units = { "VND/share": "VND/cổ phiếu", shares: "cổ phiếu", points: "điểm", score_0_100: "điểm / 100",
    times: "lần", x: "lần", sessions: "phiên", rows: "dòng", returns: "lợi suất", days: "ngày", count: "mẫu", int: "",
    articles: "tin", stories: "câu chuyện", sources: "nguồn", index: "chỉ số" };
  const statusLabels = { ok: "Đầy đủ", partial: "Chưa đầy đủ", missing: "Chưa có dữ liệu", stub: "Chưa có kết quả thực", error: "Lỗi tính toán", warn: "Có cảnh báo", pass: "Đạt", fail: "Không đạt" };
  const methodLabels = { relative_multiples_pe_pb: "So sánh P/E và P/B" };
  const number = value => Number.isFinite(value) ? value.toLocaleString("vi-VN", { maximumFractionDigits: 2 }) : "—";
  const text = value => value === null || value === undefined ? "—" : typeof value === "object" ? JSON.stringify(value) : String(value);
  const analysisOf = stock => stock.backendAnalysis?.ticker === stock.symbol ? stock.backendAnalysis : null;
  const moduleOf = (data, key) => {
    const result = data?.modules?.[key];
    return result && ["ok", "partial"].includes(result.status) ? result : null;
  };

  function ui(jsx) {
    const h = (type, props, key) => (Array.isArray(props.children) ? jsx.jsxs : jsx.jsx)(type, props, key);
    const card = (title, children, key = title) => h("section", { className: "bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs space-y-4", children: [
      h("h3", { className: "font-bold text-[#0C1D2D]", children: title }), ...children
    ] }, key);
    const paragraph = content => h("p", { className: "text-xs text-[#68788C]", children: content });
    const table = (headers, rows) => h("div", { className: "overflow-x-auto custom-scrollbar", children:
      h("table", { className: "w-full text-left text-xs", children: [
        h("thead", { className: "bg-[#EEF4FF] text-[#3D6187]", children: h("tr", { children:
          headers.map((label, index) => h("th", { scope: "col", className: "px-3 py-2.5", children: label }, index)) }) }),
        h("tbody", { className: "divide-y divide-[#E1E7EF]", children: rows.map((row, index) => h("tr", { children:
          row.map((value, column) => h(column ? "td" : "th", {
            scope: column ? undefined : "row", className: "px-3 py-2.5", style: { textAlign: "left" }, children: value
          }, column))
        }, index)) })
      ] })
    });
    const metrics = (module, fields) => table(["Chỉ số", "Giá trị", "Đơn vị", "Ghi chú từ nguồn"], fields.map(key => {
      const metric = module?.metrics?.[key];
      return [labels[key] || key, number(metric?.value), units[metric?.unit] ?? metric?.unit ?? "—", metric?.note || "—"];
    }));
    const list = (items, empty) => items?.length ? h("ul", { className: "text-xs space-y-4", children:
      items.map((item, index) => h("li", { children: typeof item === "string" ? item : item.text + (item.source_id ? ` (nguồn: ${item.source_id})` : "") }, index))
    }) : paragraph(empty);
    const evidence = module => card("Căn cứ và cảnh báo", [
      list(module?.evidence, "Chưa có căn cứ được trả về."), list(module?.flags, "Không có cờ cảnh báo được trả về.")
    ]);
    const heading = (title, stock, data, moduleKey) => card(`${title} (${stock.symbol})`, [
      paragraph(data ? `Snapshot ${data.as_of} · Hồ sơ ${data.profile} · Trạng thái: ${statusLabels[data.modules?.[moduleKey]?.status] || data.modules?.[moduleKey]?.status || "Chưa có dữ liệu"}`
        : "Chưa tải được dữ liệu phân tích cho mã này. Hãy kiểm tra kết nối backend."),
      paragraph(`Điểm: ${number(moduleOf(data, moduleKey)?.score)} / 100`)
    ], "heading");
    return { h, card, paragraph, table, metrics, list, evidence, heading };
  }

  function TechnicalAnalysis({ react, jsx, stock, compact = false }) {
    const [range, setRange] = react.useState("3m");
    const [selection, setSelection] = react.useState(null);
    const { h, card, paragraph, metrics, evidence, heading } = ui(jsx);
    const data = analysisOf(stock), module = moduleOf(data, "m3");
    const history = (data?.price_history || []).filter(row => Number.isFinite(row.close));
    const points = history.slice(-({ "3m": 63, "6m": 126, "1y": 252 }[range]));
    let chart;
    if (points.length > 1) {
      const min = Math.min(...points.map(row => row.close)), max = Math.max(...points.map(row => row.close));
      const coordinates = points.map((row, index) => `${50 + index / (points.length - 1) * 690},${20 + (max - row.close) / (max - min || 1) * 180}`).join(" ");
      const selectedIndex = selection?.data === data && selection?.range === range ? selection.index : null;
      const selected = points[selectedIndex];
      const select = index => setSelection({ data, range, index });
      const hover = event => {
        const svg = event.currentTarget;
        const matrix = svg.getScreenCTM();
        if (!matrix) return;
        const cursor = svg.createSVGPoint();
        cursor.x = event.clientX;
        cursor.y = event.clientY;
        const local = cursor.matrixTransform(matrix.inverse());
        select(Math.round(Math.max(0, Math.min(1, (local.x - 50) / 690)) * (points.length - 1)));
      };
      const x = selected ? 50 + selectedIndex / (points.length - 1) * 690 : 0;
      const y = selected ? 20 + (max - selected.close) / (max - min || 1) * 180 : 0;
      const tooltipX = Math.max(50, Math.min(540, x - 100));
      const tooltipY = y < 85 ? y + 14 : y - 64;
      chart = h("svg", { viewBox: "0 0 760 240", role: "img", "aria-label": `Biểu đồ giá đóng cửa ${stock.symbol} từ ${points[0].date} đến ${points.at(-1).date}`,
        tabIndex: 0, onPointerMove: hover, onPointerDown: hover,
        onPointerLeave: () => setSelection(null), onBlur: () => setSelection(null),
        onFocus: () => select(points.length - 1),
        onKeyDown: event => {
          if (!["ArrowLeft", "ArrowRight", "Home", "End", "Escape"].includes(event.key)) return;
          event.preventDefault();
          if (event.key === "Escape") return setSelection(null);
          const current = selectedIndex ?? points.length - 1;
          select(event.key === "Home" ? 0 : event.key === "End" ? points.length - 1
            : Math.max(0, Math.min(points.length - 1, current + (event.key === "ArrowLeft" ? -1 : 1))));
        },
        style: { width: "100%", minWidth: "300px", maxHeight: "320px" }, children: [
          h("desc", { children: "Trỏ chuột hoặc chạm để xem ngày và giá. Dùng phím mũi tên trái/phải để chọn phiên." }),
          h("rect", { x: 0, y: 0, width: 760, height: 240, fill: "transparent" }),
          h("text", { x: 0, y: 18, fontSize: 10, children: number(max) }),
          h("text", { x: 0, y: 205, fontSize: 10, children: number(min) }),
          h("polyline", { points: coordinates, fill: "none", stroke: "#1A56DB", strokeWidth: 2 }),
          h("text", { x: 50, y: 230, fontSize: 11, children: points[0].date }),
          h("text", { x: 740, y: 230, textAnchor: "end", fontSize: 11, children: points.at(-1).date }),
          selected ? h("g", { pointerEvents: "none", children: [
            h("line", { x1: x, x2: x, y1: 20, y2: 200, stroke: "#94A3B8", strokeDasharray: "4 4" }),
            h("circle", { cx: x, cy: y, r: 4, fill: "#1A56DB", stroke: "white", strokeWidth: 2 }),
            h("g", { role: "status", "aria-live": "polite", children: [
              h("rect", { x: tooltipX, y: tooltipY, width: 200, height: 50, rx: 6, fill: "#0C1D2D" }),
              h("text", { x: tooltipX + 10, y: tooltipY + 19, fill: "white", fontSize: 11, children: selected.date }),
              h("text", { x: tooltipX + 10, y: tooltipY + 37, fill: "white", fontSize: 11, children: `${number(selected.close)} VND/cổ phiếu` })
            ] })
          ] }) : null
        ] });
    } else chart = paragraph("Chưa đủ dữ liệu lịch sử giá để vẽ biểu đồ.");
    const historyCard = card("Lịch sử giá đóng cửa", [
        h("div", { className: "flex gap-2", children: ["3m", "6m", "1y"].map(key => h("button", {
          type: "button", "aria-pressed": range === key, onClick: () => setRange(key),
          className: "px-3 py-1.5 rounded-md text-xs " + (range === key ? "bg-[#1A56DB] text-white" : "bg-[#EFF6FF] text-[#1A56DB]"),
          children: { "3m": "3 tháng", "6m": "6 tháng", "1y": "1 năm" }[key]
        }, key)) }), chart,
        paragraph(`Giá theo snapshot, đơn vị VND/cổ phiếu. ${points.length} phiên hiển thị. Trỏ chuột hoặc chạm vào biểu đồ để xem ngày và giá. Các chỉ báo bên dưới tính tại phiên cuối, không đổi theo phạm vi biểu đồ.`)
      ]);
    if (compact) return historyCard;
    return h("div", { className: "space-y-4", children: [
      heading("Phân tích kỹ thuật", stock, data, "m3"), historyCard,
      card("Xu hướng và động lượng", [metrics(module, ["close", "ma20", "ma50", "ma200", "rsi14", "macd", "macd_signal", "macd_histogram"])]),
      card("Khối lượng và biến động", [metrics(module, ["volume", "volume_ma20", "volume_ratio_20", "atr14", "atr_pct"])]),
      card("Thành phần điểm kỹ thuật", [metrics(module, ["trend_score", "momentum_score", "volume_score", "volatility_score", "technical_score", "observations", "invalid_price_rows"])]),
      evidence(data?.modules?.m3)
    ] });
  }

  function ValuationAnalysis({ jsx, stock }) {
    const { h, card, paragraph, table, metrics, list, evidence, heading } = ui(jsx);
    const data = analysisOf(stock), module = moduleOf(data, "m4");
    // Only the published target is allowed: the quality gate may suppress the raw M4 target.
    const target = data?.target;
    const targetAvailable = module && Number.isFinite(target?.base);
    const price = data?.current_price;
    return h("div", { className: "space-y-4", children: [
      heading("Định giá & Giá mục tiêu", stock, data, "m4"),
      card("Giá mục tiêu theo kịch bản", targetAvailable ? [
        paragraph(`Phương pháp: ${methodLabels[target.method] || target.method || "—"}. Giá đóng cửa: ${number(price)} VND/cổ phiếu (${data.price_date || "—"}).`),
        table(["Kịch bản", "Giá mục tiêu (VND/cổ phiếu)", "Chênh lệch so giá đóng cửa"],
          [["bear", "Thận trọng"], ["base", "Cơ sở"], ["bull", "Tích cực"]].map(([key, label]) => [
            label, number(target[key]), Number.isFinite(target[key]) && Number.isFinite(price) && price > 0 ? number((target[key] / price - 1) * 100) + "%" : "—"
          ])),
        list(target.assumptions, "Chưa có giả định định giá được trả về.")
      ] : [paragraph("Chưa có giá mục tiêu được công bố cho mã này; kết quả có thể bị chặn bởi kiểm tra chất lượng dữ liệu."),
        list(data?.quality_gate?.reasons, "")]),
      card("Hệ số và dữ liệu định giá", [metrics(module, ["price_close", "eps_used", "book_per_share", "pe", "pb", "sector_median_pe", "sector_median_pb", "sector_n_pe", "sector_n_pb"])]),
      card("Thành phần điểm định giá", [metrics(module, ["v_pe_leg", "v_pb_leg", "score_V", "sector_stats_version"])]),
      evidence(data?.modules?.m4)
    ] });
  }

  function RiskAnalysis({ jsx, stock }) {
    const { h, card, paragraph, table, metrics, list, evidence, heading } = ui(jsx);
    const data = analysisOf(stock), module = moduleOf(data, "m6");
    const validation = data?.validation;
    return h("div", { className: "space-y-4", children: [
      heading("Rủi ro & Kiểm tra dữ liệu", stock, data, "m6"),
      paragraph("Điểm rủi ro của mô hình càng cao thể hiện rủi ro đo được càng cao. VaR/CVaR là ước lượng từ lịch sử, không phải giới hạn lỗ tối đa."),
      card("Rủi ro thị trường", [metrics(module, ["annualized_volatility", "benchmark_volatility", "beta", "max_drawdown", "benchmark_max_drawdown", "historical_var_95", "historical_cvar_95"])]),
      card("Mẫu quan sát và thành phần điểm", [metrics(module, ["aligned_observations", "negative_sessions", "positive_sessions", "last_aligned_date", "future_rows_excluded", "gap_returns_excluded", "volatility_risk_subscore", "drawdown_risk_subscore", "var_risk_subscore", "tail_risk_subscore", "beta_risk_subscore"])]),
      card("Kiểm tra chất lượng kết quả", [
        paragraph(validation ? `Trạng thái: ${statusLabels[validation.status] || validation.status || "—"} · Số kiểm tra: ${number(validation.checked)}` : "Chưa có kết quả kiểm tra dữ liệu."),
        paragraph("Đây là kiểm tra dữ liệu và tính nhất quán của hệ thống; thông tin này không xác nhận BCTC đã được kiểm toán độc lập."),
        validation?.issues?.length ? table(["Mức độ", "Nội dung", "Vị trí"], validation.issues.map(issue => [issue.severity || "—", issue.message || "—", issue.where || "—"]))
          : paragraph(validation ? "Không có vấn đề được trả về trong kết quả kiểm tra." : "—"),
        data?.quality_gate ? table(["Điều kiện chất lượng", "Kết quả"], Object.entries(data.quality_gate).map(([key, value]) => [key, text(value)])) : paragraph("Chưa có thông tin điều kiện chất lượng."),
        list(data?.flags, "Không có cờ tổng hợp được trả về.")
      ]),
      evidence(data?.modules?.m6)
    ] });
  }

  function StockSummaryHeader({ jsx, stock, isWatchlisted, onToggleWatchlist }) {
    const { h, card, paragraph, table } = ui(jsx);
    const data = analysisOf(stock), company = data?.company;
    const metric = (module, key) => moduleOf(data, module)?.metrics?.[key];
    const pe = metric("m4", "pe"), pb = metric("m4", "pb"), roe = metric("m2", "roe");
    return card(`${stock.symbol}${company?.name ? " · " + company.name : ""}`, [
      paragraph(data ? `${company?.exchange || "Chưa có sàn"} · ${company?.sector || "Chưa có ngành"} · Snapshot ${data.as_of}` : "Đang tải hoặc chưa có dữ liệu cho mã này."),
      table(["Chỉ số", "Giá trị"], [["P/E", number(pe?.value)], ["P/B", number(pb?.value)],
        ["ROE", number(roe?.value) + (roe?.unit ? " " + (units[roe.unit] ?? roe.unit) : "")]]),
      onToggleWatchlist ? h("button", { type: "button", onClick: onToggleWatchlist,
        className: "px-3 py-1.5 bg-[#EFF6FF] text-[#1A56DB] rounded-md text-xs", children: isWatchlisted ? "Bỏ theo dõi" : "Theo dõi mã này" }) : null
    ]);
  }

  function OverviewAnalysis({ react, jsx, stock, onNavigateTab }) {
    const { h, card, paragraph, table, list } = ui(jsx);
    const data = analysisOf(stock);
    const factors = [["F", "Cơ bản", "m2", "financials"], ["T", "Kỹ thuật", "m3", "technical"],
      ["V", "Định giá", "m4", "valuation"], ["S", "Sentiment", "m5", "news"], ["R", "Rủi ro", "m6", "risks"]];
    return h("div", { className: "space-y-4", children: [
      card(`Tổng quan (${stock.symbol})`, [
        paragraph(data ? `Snapshot ${data.as_of} · Hồ sơ ${data.profile} · Giá tại ${data.price_date || "—"}` : "Chưa tải được dữ liệu tổng quan cho mã này."),
        table(["Thông tin", "Giá trị"], [
          ["Giá đóng cửa (VND/cổ phiếu)", number(data?.current_price)],
          ["Thay đổi so phiên trước (VND)", number(data?.price_change)],
          ["Thay đổi so phiên trước (%)", number(data?.price_change_percent)],
          ["Khối lượng (cổ phiếu)", number(data?.volume)], ["Điểm tổng hợp / 100", number(data?.score)],
          ["Khuyến nghị", data?.recommendation || "—"], ["Giá mục tiêu cơ sở (VND/cổ phiếu)", number(data?.target?.base)],
          ["Chênh lệch giá mục tiêu (%)", number(data?.upside)]
        ])
      ]),
      h(TechnicalAnalysis, { react, jsx, stock, compact: true }),
      card("Điểm nhân tố", [table(["Nhân tố", "Điểm / 100", "Trạng thái", "Chi tiết"], factors.map(([key, label, module, tab]) => [
        label, number(data?.scores?.[key]), statusLabels[data?.modules?.[module]?.status] || data?.modules?.[module]?.status || "Chưa có dữ liệu",
        h("button", { type: "button", onClick: () => onNavigateTab?.(tab), className: "text-[#1A56DB] cursor-pointer", children: "Xem chi tiết" })
      ])), paragraph("Điểm R cao thể hiện rủi ro đo được cao hơn. Các điểm là kết quả mô hình, không phải xác suất tăng giá.")]),
      card("Luận điểm chính", [list(data?.bull, "Chưa có luận điểm hỗ trợ."), list(data?.bear, "Chưa có luận điểm bất lợi."),
        h("button", { type: "button", onClick: () => onNavigateTab?.("bullbear"), className: "text-xs text-[#1A56DB] cursor-pointer", children: "Xem Bull & Bear và căn cứ" })]),
      card("Chất lượng dữ liệu", [
        paragraph(data?.validation ? `Kiểm tra: ${statusLabels[data.validation.status] || data.validation.status} · ${number(data.validation.checked)} kiểm tra` : "Chưa có kết quả kiểm tra."),
        list(data?.quality_gate?.reasons, "Không có lý do chặn điểm được trả về."),
        list(data?.flags, "Không có cờ cảnh báo được trả về.")
      ])
    ] });
  }

  const safeUrl = value => typeof value === "string" && /^https?:\/\//i.test(value) ? value : null;
  const sentimentLabel = value => ({ pos: "Tích cực", neg: "Tiêu cực", neutral: "Trung tính" }[value] || "Chưa phân loại");

  function NewsAnalysis({ react, jsx, stock }) {
    const [filter, setFilter] = react.useState("all");
    const { h, card, paragraph, metrics, evidence } = ui(jsx);
    const data = analysisOf(stock), module = moduleOf(data, "m5");
    const all = data?.news || [];
    const items = all.filter(item => filter === "all" || item.label === filter);
    return h("div", { className: "space-y-4", children: [
      card(`Tin tức & Sentiment (${stock.symbol})`, [
        paragraph(data ? `Snapshot ${data.as_of} · Điểm sentiment: ${number(module?.score)} / 100` : "Chưa tải được dữ liệu tin tức cho mã này."),
        paragraph("Sentiment được chấm bằng quy tắc từ tiêu đề, không phải phân tích AI toàn văn. Độ phủ heuristic không phải xác suất hoặc độ chính xác đã hiệu chỉnh."),
        metrics(module, ["news_relevant_count", "news_positive_count", "news_negative_count", "news_neutral_count", "news_distinct_sources", "sentiment_polarity", "sentiment_confidence"])
      ]),
      card("Tin tiêu biểu làm căn cứ chấm điểm", [
        paragraph(`Có ${all.length} tin tiêu biểu được backend trích dẫn; danh sách không phải toàn bộ tin trong snapshot.`),
        h("label", { className: "text-xs", children: ["Lọc sắc thái ", h("select", {
          "aria-label": "Lọc sắc thái", value: filter, onChange: event => setFilter(event.target.value),
          className: "border border-[#E1E7EF] rounded-md px-3 py-1.5", children:
            [["all", "Tất cả"], ["pos", "Tích cực"], ["neg", "Tiêu cực"], ["neutral", "Trung tính"]].map(([value, label]) => h("option", { value, children: label }, value))
        })] }),
        ...items.map(item => h("article", { id: `news-${encodeURIComponent(item.id)}`, className: "border border-[#E1E7EF] rounded-lg p-4 space-y-4", children: [
          h("h4", { className: "text-sm font-bold text-[#0C1D2D]", children: safeUrl(item.url)
            ? h("a", { href: safeUrl(item.url), target: "_blank", rel: "noopener noreferrer", children: item.title || "Chưa có tiêu đề" }) : item.title || "Chưa có tiêu đề" }),
          paragraph(`${sentimentLabel(item.label)} · ${item.source || "Chưa có nguồn"} · ${item.published_at || "Chưa có ngày công bố"}`),
          item.summary ? paragraph(item.summary) : null
        ] }, item.id)),
        items.length ? null : paragraph(all.length ? "Không có tin tiêu biểu khớp bộ lọc." : "Chưa có tin tiêu biểu được trả về cho mã này.")
      ]),
      card("Phạm vi dữ liệu tin tức", [metrics(module, ["news_input_count", "news_story_count", "news_directional_count", "news_duplicate_count", "news_future_excluded", "news_old_excluded", "news_offtopic_excluded", "news_multi_ticker_weighted", "news_newest_age_days"])]),
      evidence(data?.modules?.m5)
    ] });
  }

  function BullBearAnalysis({ jsx, stock }) {
    const { h, card, paragraph } = ui(jsx);
    const data = analysisOf(stock);
    const source = data?.debate_source === "template" ? "Luận điểm theo quy tắc từ kết quả mô hình" : data?.debate_source || "Chưa có thông tin nguồn luận điểm";
    const reference = ref => {
      const newsId = data?.news_ref_map?.[ref];
      if (newsId) {
        const news = data.news?.find(item => item.id === newsId);
        return h("li", { children: news ? (safeUrl(news.url) ? h("a", { href: safeUrl(news.url),
          target: "_blank", rel: "noopener noreferrer", className: "text-[#1A56DB]", children: `${ref}: ${news.title}` }) : `${ref}: ${news.title}`)
          : `${ref}: Chưa có tin nguồn để đối chiếu.` }, ref);
      }
      const [module, key] = ref.split(".");
      const metric = moduleOf(data, module)?.metrics?.[key];
      return h("li", { children: `${labels[key] || ref}: ${number(metric?.value)} ${units[metric?.unit] ?? metric?.unit ?? ""}` }, ref);
    };
    const side = (key, title) => card(`${title} (${data?.[key]?.length || 0} luận điểm)`, [
      ...(data?.[key] || []).map((item, index) => h("article", { className: "border border-[#E1E7EF] rounded-lg p-4 space-y-4", children: [
        h("p", { className: "text-sm font-semibold", children: item.text }),
        item.refs?.length ? h("ul", { className: "text-xs space-y-4", children: item.refs.map(reference) }) : paragraph("Chưa có tham chiếu cho luận điểm này.")
      ] }, index)),
      data?.[key]?.length ? null : paragraph(`Chưa có luận điểm ${key === "bull" ? "hỗ trợ" : "bất lợi"} cho mã này.`)
    ]);
    return h("div", { className: "space-y-4", children: [
      card(`Bull & Bear (${stock.symbol})`, [paragraph(data ? `Snapshot ${data.as_of} · ${source}` : "Chưa tải được luận điểm cho mã này."),
        paragraph("Luận điểm phản ánh các nhân tố hỗ trợ hoặc gây áp lực lên điểm tổng hợp; không phải bình chọn cộng đồng hay xác suất tăng/giảm giá.")]),
      h("div", { className: "grid grid-cols-1 md:grid-cols-2 gap-4", children: [side("bull", "Luận điểm hỗ trợ — Bull"), side("bear", "Luận điểm bất lợi — Bear")] })
    ] });
  }

  Object.assign(window.StockAI, { TechnicalAnalysis, ValuationAnalysis, RiskAnalysis, StockSummaryHeader, OverviewAnalysis, NewsAnalysis, BullBearAnalysis });
})();
