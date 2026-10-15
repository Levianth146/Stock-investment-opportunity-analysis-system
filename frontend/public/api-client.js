/* Integration adapter for the supplied build. Port into React when source is restored. */
(function () {
  const labels = {
    "Mua mạnh": "MUA MẠNH", "Mua": "MUA", "Nắm giữ": "GIỮ",
    "Giảm tỷ trọng": "GIẢM TỶ TRỌNG", "Bán": "BÁN", "Không xếp hạng": "KHÔNG XẾP HẠNG"
  };

  function showStatus(message, failed) {
    let banner = document.getElementById("backend-status");
    if (!banner) {
      banner = document.createElement("div");
      banner.id = "backend-status";
      banner.setAttribute("role", "status");
      banner.style.cssText = "padding:12px 24px;font:13px Inter,sans-serif;line-height:1.6";
      document.body.insertBefore(banner, document.getElementById("root"));
    }
    banner.style.background = failed ? "#fff1f2" : "#eff6ff";
    banner.style.color = failed ? "#9f1239" : "#1e40af";
    banner.textContent = message;
  }

  function toStock(data, demo) {
    const stock = {
      symbol: data.ticker,
      name: data.company?.name || data.ticker,
      exchange: data.company?.exchange || "—",
      industry: data.company?.sector || "—",
      marketOpen: false,
      tradingTime: `Snapshot ${data.price_date || data.as_of}`,
      aiRecommendation: labels[data.recommendation] || data.recommendation || "KHÔNG XẾP HẠNG",
      aiModelVersion: `StockAI · ${data.profile} · ${data.as_of}`,
      aiThesis: data.bull.map(item => item.text).join(" "),
      aiConfidence: "Chưa hiệu chỉnh",
      valuationMethod: data.target?.method || "Chưa có định giá",
      bullCase: data.bull.map(item => item.text),
      bearCase: data.bear.map(item => item.text),
      financialReports: data.financial_reports || { unit: null, annual: [] },
      backendAnalysis: data,
      factors: { ...demo.factors }
    };
    const fields = {
      current_price: "currentPrice", price_change: "priceChange",
      price_change_percent: "priceChangePercent", volume: "volume",
      score: "aiScore", target_price: "targetPrice", upside: "upside"
    };
    const missing = [];
    for (const [apiKey, uiKey] of Object.entries(fields)) {
      if (Number.isFinite(data[apiKey])) stock[uiKey] = data[apiKey];
      else missing.push(apiKey);
    }
    for (const [key, field] of Object.entries({F: "fFundamental", T: "tTechnical", V: "vValuation", S: "sSentiment", R: "rRisk"})) {
      if (Number.isFinite(data.scores?.[key])) {
        stock.factors[field] = { score: data.scores[key], text: `Điểm ${key} từ pipeline StockAI (0–100)` };
      }
    }
    showStatus(`Đã kết nối FastAPI · ${data.ticker} · snapshot ${data.as_of}. Các tab phân tích theo mã dùng dữ liệu backend, mục thiếu dữ liệu hiển thị —. Sentiment dựa trên tiêu đề; Bull/Bear là luận điểm theo quy tắc. Danh mục, bảng thị trường và các công cụ ngoài tab phân tích vẫn có phần demo.${missing.length ? ` Trường còn thiếu: ${missing.join(", ")}.` : ""} ${data.disclaimer}`, false);
    return stock;
  }

  const statements = {
    income: {
      label: "Kết Quả Kinh Doanh",
      rows: [
        [null, "Doanh thu và chi phí"],
        ["revenue", "Doanh thu thuần"], ["cost_of_goods", "Giá vốn hàng bán"],
        ["gross_profit", "Lợi nhuận gộp"],
        ["selling_expense", "Chi phí bán hàng"], ["admin_expense", "Chi phí quản lý"],
        ["interest_expense", "Chi phí lãi vay"], ["depreciation", "Khấu hao"],
        [null, "Kết quả và thu nhập cổ đông"],
        ["ebit", "EBIT"], ["ebitda", "EBITDA"],
        ["pretax_profit", "Lợi nhuận trước thuế"], ["income_tax", "Chi phí thuế TNDN (ròng)"],
        ["net_income", "Lợi nhuận sau thuế"],
        ["net_income_parent", "Lợi nhuận sau thuế của CĐ công ty mẹ"],
        ["minority_income", "Lợi nhuận thuộc cổ đông không kiểm soát"],
        ["eps", "EPS (VND / cổ phiếu)"],
        [null, "Biên lợi nhuận"],
        ["gross_margin", "Biên lợi nhuận gộp (%)"], ["ebit_margin", "Biên EBIT (%)"],
        ["net_margin", "Biên lợi nhuận sau thuế (%)"]
      ]
    },
    balance: {
      label: "Bảng Cân Đối",
      rows: [
        [null, "Tài sản"],
        ["total_assets", "Tổng tài sản"], ["current_assets", "Tài sản ngắn hạn"],
        ["cash", "Tiền và tương đương tiền"], ["receivables", "Các khoản phải thu"],
        ["trade_receivables", "Phải thu khách hàng"], ["inventory", "Hàng tồn kho"],
        ["noncurrent_assets", "Tài sản dài hạn"],
        [null, "Nợ phải trả và vốn chủ sở hữu"],
        ["total_liabilities", "Nợ phải trả"], ["current_liabilities", "Nợ ngắn hạn"],
        ["noncurrent_liabilities", "Nợ dài hạn"],
        ["trade_payables", "Phải trả người bán"], ["short_term_debt", "Vay ngắn hạn"],
        ["long_term_debt", "Vay dài hạn"], ["total_equity", "Vốn chủ sở hữu"],
        [null, "Cơ cấu tài chính và thanh khoản"],
        ["total_debt", "Tổng vay ngắn hạn và dài hạn"], ["net_debt", "Vay ròng sau khi trừ tiền"],
        ["working_capital", "Vốn lưu động ròng"],
        ["liabilities_assets", "Nợ phải trả / Tổng tài sản (%)"],
        ["debt_equity", "Tổng vay / Vốn chủ sở hữu (lần)"],
        ["current_ratio", "Hệ số thanh toán hiện hành (lần)"]
      ]
    },
    cashflow: {
      label: "Lưu Chuyển Tiền Tệ",
      rows: [
        [null, "Dòng tiền theo hoạt động"],
        ["cfo", "Lưu chuyển tiền thuần từ hoạt động kinh doanh"],
        ["cfi", "Lưu chuyển tiền thuần từ hoạt động đầu tư"],
        ["cff", "Lưu chuyển tiền thuần từ hoạt động tài chính"],
        ["net_cashflow", "Tổng lưu chuyển tiền thuần từ ba hoạt động"],
        [null, "Đầu tư và phân phối tiền"],
        ["capex", "Chi đầu tư tài sản cố định (CAPEX)"],
        ["dividends_paid", "Cổ tức đã trả"], ["depreciation", "Khấu hao"],
        ["free_cashflow", "Dòng tiền tự do (CFO − CAPEX)"],
        [null, "Chất lượng dòng tiền"],
        ["cash_conversion", "CFO / Lợi nhuận sau thuế (lần)"],
        ["capex_cfo", "CAPEX / CFO (%)"]
      ]
    }
  };

  const bankIncome = [
    [null, "Thu nhập và chi phí ngân hàng"],
    ["net_interest_income", "Thu nhập lãi thuần"], ["total_operating_income", "Tổng thu nhập hoạt động"],
    ["interest_expense", "Chi phí lãi"], ["opex", "Chi phí hoạt động (theo dấu nguồn)"],
    ["provision_expense", "Chi phí dự phòng (theo dấu nguồn)"],
    [null, "Kết quả và thu nhập cổ đông"],
    ["pretax_profit", "Lợi nhuận trước thuế"], ["net_income", "Lợi nhuận sau thuế"],
    ["net_income_parent", "Lợi nhuận sau thuế của CĐ công ty mẹ"],
    ["minority_income", "Lợi nhuận thuộc cổ đông không kiểm soát"], ["eps", "EPS (VND / cổ phiếu)"],
    [null, "Hiệu quả hoạt động ngân hàng"],
    ["nim", "Biên lãi ròng NIM (%)"], ["cir", "Chi phí / Thu nhập CIR (%)"]
  ];
  const bankBalance = [
    [null, "Tài sản và tín dụng"], ["total_assets", "Tổng tài sản"],
    ["cash", "Tiền và tương đương tiền (theo nguồn)"], ["customer_loans", "Cho vay khách hàng"],
    [null, "Nguồn vốn"], ["total_liabilities", "Nợ phải trả"],
    ["customer_deposits", "Tiền gửi khách hàng"], ["total_equity", "Vốn chủ sở hữu"],
    [null, "Cơ cấu tài chính"], ["loans_deposits", "Cho vay / Tiền gửi khách hàng (%)"],
    ["liabilities_assets", "Nợ phải trả / Tổng tài sản (%)"],
    ["equity_assets", "Vốn chủ sở hữu / Tổng tài sản (%)"]
  ];
  const calculations = {
    cost_of_goods: ["Doanh thu thuần − Lợi nhuận gộp", ["revenue", "gross_profit"], (a, b) => a - b],
    income_tax: ["Lợi nhuận trước thuế − Lợi nhuận sau thuế", ["pretax_profit", "net_income"], (a, b) => a - b],
    minority_income: ["LNST − LNST của CĐ công ty mẹ", ["net_income", "net_income_parent"], (a, b) => a - b],
    noncurrent_assets: ["Tổng tài sản − Tài sản ngắn hạn", ["total_assets", "current_assets"], (a, b) => a - b],
    noncurrent_liabilities: ["Nợ phải trả − Nợ ngắn hạn", ["total_liabilities", "current_liabilities"], (a, b) => a - b],
    total_debt: ["Vay ngắn hạn + Vay dài hạn", ["short_term_debt", "long_term_debt"], (a, b) => a + b],
    net_debt: ["Vay ngắn hạn + Vay dài hạn − Tiền", ["short_term_debt", "long_term_debt", "cash"], (a, b, c) => a + b - c],
    working_capital: ["Tài sản ngắn hạn − Nợ ngắn hạn", ["current_assets", "current_liabilities"], (a, b) => a - b],
    net_cashflow: ["CFO + CFI + CFF; chưa gồm ảnh hưởng tỷ giá", ["cfo", "cfi", "cff"], (a, b, c) => a + b + c],
    free_cashflow: ["CFO − |CAPEX|", ["cfo", "capex"], (a, b) => a - Math.abs(b)],
    gross_margin: ["Lợi nhuận gộp / Doanh thu thuần × 100", ["gross_profit", "revenue"], (a, b) => b > 0 ? a / b * 100 : null, "%"],
    ebit_margin: ["EBIT / Doanh thu thuần × 100", ["ebit", "revenue"], (a, b) => b > 0 ? a / b * 100 : null, "%"],
    net_margin: ["LNST / Doanh thu thuần × 100", ["net_income", "revenue"], (a, b) => b > 0 ? a / b * 100 : null, "%"],
    liabilities_assets: ["Nợ phải trả / Tổng tài sản × 100", ["total_liabilities", "total_assets"], (a, b) => b > 0 ? a / b * 100 : null, "%"],
    equity_assets: ["Vốn chủ sở hữu / Tổng tài sản × 100", ["total_equity", "total_assets"], (a, b) => b > 0 ? a / b * 100 : null, "%"],
    debt_equity: ["(Vay ngắn hạn + Vay dài hạn) / Vốn chủ sở hữu", ["short_term_debt", "long_term_debt", "total_equity"], (a, b, c) => c > 0 ? (a + b) / c : null, "ratio"],
    current_ratio: ["Tài sản ngắn hạn / Nợ ngắn hạn", ["current_assets", "current_liabilities"], (a, b) => b > 0 ? a / b : null, "ratio"],
    cash_conversion: ["CFO / LNST; không tính khi LNST ≤ 0", ["cfo", "net_income"], (a, b) => b > 0 ? a / b : null, "ratio"],
    capex_cfo: ["|CAPEX| / CFO × 100; không tính khi CFO ≤ 0", ["capex", "cfo"], (a, b) => b > 0 ? Math.abs(a) / b * 100 : null, "%"],
    loans_deposits: ["Cho vay khách hàng / Tiền gửi khách hàng × 100; không phải LDR theo quy định", ["customer_loans", "customer_deposits"], (a, b) => b > 0 ? a / b * 100 : null, "%"]
  };

  function financialValue(row, key) {
    const value = row?.items?.[key];
    if (Number.isFinite(value)) return value;
    const calc = calculations[key];
    if (!calc) return null;
    const inputs = calc[1].map(field => row?.items?.[field]);
    if (!inputs.every(Number.isFinite)) return null;
    const result = calc[2](...inputs);
    return Number.isFinite(result) ? result : null;
  }

  // The supplied frontend has no React source. The bundle mounts this readable component.
  function FinancialReports({ react, jsx, stock }) {
    const [tab, setTab] = react.useState("income");
    const [frequency, setFrequency] = react.useState("annual");
    const [displayUnit, setDisplayUnit] = react.useState("billion");
    const [periodCount, setPeriodCount] = react.useState("5");
    const h = (type, props, key) => (Array.isArray(props.children) ? jsx.jsxs : jsx.jsx)(type, props, key);
    const report = stock.financialReports || { unit: null, annual: [] };
    const periods = report[frequency] || [];
    const visible = periodCount === "all" ? periods : periods.slice(-Number(periodCount));
    const statement = statements[tab];
    const rows = report.is_bank && tab === "income" ? bankIncome
      : report.is_bank && tab === "balance" ? bankBalance : statement.rows;
    const scale = report.unit === "VND" ? ({ billion: 1e9, million: 1e6, original: 1 }[displayUnit]) : 1;
    const unit = report.unit === "VND" ? ({ billion: "Tỷ đồng", million: "Triệu đồng", original: "VND" }[displayUnit]) : (report.unit || "Chưa rõ đơn vị");
    const kind = key => ["nim", "cir"].includes(key) ? "%" : calculations[key]?.[3];
    const number = value => value.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
    const format = (value, key) => {
      if (!Number.isFinite(value)) return "—";
      if (["nim", "cir"].includes(key)) return number(value * 100) + "%";
      if (kind(key) === "%") return number(value) + "%";
      if (kind(key) === "ratio") return number(value) + " lần";
      return number(value / (key === "eps" ? 1 : scale));
    };
    const latest = periods[periods.length - 1];
    const match = String(latest?.period || "").match(/^(\d{4})(Q[1-4])?$/);
    const previousPeriod = match ? String(Number(match[1]) - 1) + (match[2] || "") : null;
    const previous = periods.find(row => row.period === previousPeriod);
    const compare = key => {
      const current = financialValue(latest, key), prior = financialValue(previous, key);
      if (!Number.isFinite(current) || !Number.isFinite(prior)) return "—";
      if (kind(key) === "%") {
        const delta = (current - prior) * (["nim", "cir"].includes(key) ? 100 : 1);
        return (delta > 0 ? "+" : "") + number(delta) + " đpt";
      }
      if (kind(key) === "ratio") return number(current - prior) + " lần";
      if (prior <= 0) return "—";
      const delta = (current / prior - 1) * 100;
      return (delta > 0 ? "+" : "") + number(delta) + "%";
    };
    const cell = (tag, text, key, extra = {}) => h(tag, {
      className: "py-2.5 px-3 " + (tag === "th" ? "font-semibold" : "font-mono-numbers"),
      children: text, ...extra
    }, key);
    const hasData = visible.some(row => rows.some(([key]) => key && Number.isFinite(financialValue(row, key))));
    const formulas = rows.filter(([key]) => calculations[key]);
    const select = (label, value, onChange, options) => h("label", { className: "text-xs text-[#3D6187]", children: [
      label + " ", h("select", { "aria-label": label, value, onChange: event => onChange(event.target.value),
        className: "border border-[#E1E7EF] rounded-md px-3 py-1.5 bg-white",
        children: options.map(([id, text]) => h("option", { value: id, children: text }, id)) })
    ] }, label);
    return h("section", { className: "space-y-4", children: [
      h("div", { className: "bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs space-y-4", children: [
        h("h2", { className: "text-base font-bold text-[#0C1D2D]", children: `Báo cáo tài chính ${frequency === "annual" ? "năm" : "quý"} (${stock.symbol})` }),
        h("p", { className: "text-xs text-[#68788C]", children: "Dữ liệu lịch sử từ snapshot. Đơn vị: " + unit + ". EPS dùng VND/cổ phiếu. Dấu —: chưa có dữ liệu hoặc không đủ cơ sở tính. Dấu *: tính từ khoản mục nguồn." }),
        h("div", { role: "tablist", "aria-label": "Loại báo cáo tài chính", className: "flex flex-wrap gap-1 p-1 bg-[#EFF6FF] rounded-lg", children:
          Object.entries(statements).map(([key, item]) => h("button", {
            type: "button", role: "tab", "aria-selected": tab === key,
            "aria-controls": "financial-report-panel", id: `financial-tab-${key}`,
            onClick: () => setTab(key),
            className: "px-3 py-1.5 rounded-md text-xs font-semibold cursor-pointer " + (tab === key ? "bg-[#1A56DB] text-white shadow-xs" : "text-[#1A56DB]"),
            children: item.label
          }, key))
        }),
        h("div", { className: "flex flex-wrap gap-3", children: [
          select("Kỳ báo cáo", frequency, setFrequency, [["annual", "Năm"], ["quarterly", "Quý"]]),
          select("Số kỳ", periodCount, setPeriodCount, [["5", "5 kỳ gần nhất"], ["8", "8 kỳ gần nhất"], ["all", "Tất cả"]]),
          report.unit === "VND" ? select("Đơn vị", displayUnit, setDisplayUnit, [["billion", "Tỷ đồng"], ["million", "Triệu đồng"], ["original", "VND"]]) : null
        ] }),
        h("p", { className: "text-xs text-[#68788C]", children: `Có ${periods.length} kỳ, đang hiển thị ${visible.length} kỳ. ${frequency === "quarterly" ? "Số liệu quý giữ nguyên cách ghi nhận của nguồn; không tự tách lũy kế hoặc quy đổi thành năm." : ""}` })
      ] }),
      h("div", { role: "tabpanel", id: "financial-report-panel", "aria-labelledby": `financial-tab-${tab}`,
        className: "bg-white rounded-xl border border-[#E1E7EF] p-4 sm:p-5 shadow-xs overflow-x-auto custom-scrollbar", children:
        hasData ? h("table", { className: "w-full text-left text-xs", children: [
          h("caption", { className: "text-left font-bold pb-3", children: statement.label }),
          h("thead", { className: "bg-[#EEF4FF] text-[#3D6187] border-b border-[#E1E7EF]", children:
            h("tr", { children: [cell("th", `Khoản mục (${unit})`, "item", { scope: "col" }),
              ...visible.map(row => cell("th", row.period, row.period, { scope: "col", style: { textAlign: "right", whiteSpace: "nowrap" } })),
              cell("th", `So cùng kỳ (${latest?.period || "—"} / ${previousPeriod || "—"})`, "yoy", { scope: "col", style: { textAlign: "right" } })] })
          }),
          h("tbody", { className: "divide-y divide-[#E1E7EF]", children: [
            ...rows.map(([key, label]) => key ? h("tr", { children: [
              cell("th", label + (calculations[key] ? " *" : ""), "label", { scope: "row", title: calculations[key]?.[0], style: { minWidth: "260px" } }),
              ...visible.map(row => cell("td", format(financialValue(row, key), key), row.period, {
                style: { textAlign: "right", whiteSpace: "nowrap" },
                title: calculations[key] && !Number.isFinite(row.items?.[key]) ? "Tính: " + calculations[key][0] : "Khoản mục từ snapshot"
              })), cell("td", compare(key), "yoy", { style: { textAlign: "right", whiteSpace: "nowrap" } })
            ] }, key) : h("tr", { className: "bg-[#EFF6FF] text-[#1A56DB]", children:
              cell("th", label, "group", { colSpan: visible.length + 2, scope: "rowgroup", style: { textAlign: "left" } })
            }, label)),
            h("tr", { children: [cell("th", "Ngày công bố (* ước lượng)", "label", { scope: "row" }),
              ...visible.map(row => cell("td", (row.published_at || "—") + (row.published_at_estimated ? " *" : ""), row.period, { style: { textAlign: "right", whiteSpace: "nowrap" } })), cell("td", "", "yoy")] }, "published"),
            h("tr", { children: [cell("th", "Mã nguồn dữ liệu", "label", { scope: "row" }),
              ...visible.map(row => cell("td", row.source_id || "—", row.period, { style: { textAlign: "right" } })), cell("td", "", "yoy")] }, "source")
          ] })
        ] }) : h("p", { role: "status", className: "text-sm text-[#68788C]", children: `Chưa có dữ liệu ${statement.label.toLowerCase()} cho mã ${stock.symbol}.` })
      }),
      h("div", { className: "text-xs text-[#68788C] space-y-4", children: [
        h("p", { children: "So cùng kỳ: năm với năm trước hoặc quý với cùng quý năm trước; không tính tăng trưởng % khi kỳ gốc ≤ 0. Tỷ lệ % so chênh lệch điểm phần trăm (đpt); hệ số so chênh lệch số lần." }),
        report.published_at_note ? h("p", { children: report.published_at_note }) : null,
        h("p", { children: "Snapshot chỉ lưu các khoản mục đã chuẩn hóa, chưa phải toàn bộ thuyết minh BCTC. Các khoản mục thiếu không được tự coi là 0. NIM và CIR giữ theo nguồn, không tự quy đổi kỳ." }),
        h("details", { children: [h("summary", { className: "cursor-pointer font-semibold text-[#1A56DB]", children: "Xem công thức các chỉ tiêu tính thêm (*)" }),
          h("ul", { children: formulas.map(([key, label]) => h("li", { children: `${label}: ${calculations[key][0]}` }, key)) })] })
      ] })
    ] });
  }

  window.StockAI = {
    toStock,
    pendingStock(symbol, legacy) {
      return { ...legacy, symbol, name: symbol, exchange: "—", industry: "—", backendAnalysis: null, financialReports: null };
    },
    FinancialReports,
    onError() {
      showStatus("Không tải được phân tích từ FastAPI. Các tab phân tích chưa có dữ liệu cho mã này; hãy kiểm tra backend và mã cổ phiếu. Các phần giao diện khác có thể vẫn hiển thị demo.", true);
    }
  };
})();
