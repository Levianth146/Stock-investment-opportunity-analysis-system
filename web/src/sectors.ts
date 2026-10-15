/** Ánh xạ ngành ICB L2 (tiếng Anh trong snapshot) → tiếng Việt hiển thị. */

const EN_TO_VI: Record<string, string> = {
  Banks: "Ngân hàng",
  "Real Estate": "Bất động sản",
  "Food & Beverage": "Thực phẩm và đồ uống",
  Utilities: "Điện, nước & xăng dầu khí đốt",
  "Basic Resources": "Tài nguyên cơ bản",
  Chemicals: "Hóa chất",
  Technology: "Công nghệ thông tin",
  Retail: "Bán lẻ",
  "Travel & Leisure": "Du lịch và giải trí",
  "Oil & Gas": "Dầu khí",
  Insurance: "Bảo hiểm",
  "Financial Services": "Dịch vụ tài chính",
  "Industrial Goods & Services": "Hàng & dịch vụ công nghiệp",
  "Personal & Household Goods": "Hàng cá nhân & gia dụng",
  Media: "Truyền thông",
  Telecommunications: "Viễn thông",
  "Construction & Materials": "Xây dựng và vật liệu",
  "Health Care": "Y tế",
  "Automobiles & Parts": "Ô tô và phụ tùng",
  // Parent / fallback thường gặp
  Financials: "Tài chính",
  Industrials: "Công nghiệp",
  "Consumer Goods": "Hàng tiêu dùng",
  "Consumer Services": "Dịch vụ tiêu dùng",
  "Basic Materials": "Nguyên vật liệu",
  Steel: "Thép",
};

/** Trả tên ngành tiếng Việt; không biết thì giữ nguyên chuỗi gốc. */
export function sectorVi(raw: string | null | undefined): string {
  if (raw == null || raw === "") return "—";
  return EN_TO_VI[raw] ?? raw;
}
