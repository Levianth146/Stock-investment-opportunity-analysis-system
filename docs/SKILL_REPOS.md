# Skill, thư viện và quy ước thiết kế cho StockAI (web React + FastAPI, PDF ReportLab)

Bản 3, cập nhật 14/10/2026. **Trạng thái thực tế của dự án (đối chiếu với code):**
- Web là **React + Vite + TypeScript** (thư mục `web/`), FastAPI chỉ phục vụ JSON API và file build `web/dist`. **Không dùng** Jinja2, Tailwind, Alpine/htmx, Streamlit, WeasyPrint.
- PDF do **ReportLab** dựng (`src/stockai/m9_report/`), không dùng chung HTML/CSS với web. Điểm chung duy nhất là bảng token màu.
- Biểu đồ: `lightweight-charts` 4.x (nến, khối lượng, chỉ báo) và SVG tự vẽ (thước điểm, radar). `recharts` có trong `package.json` nhưng không dùng, nên gỡ.
- Phông: IBM Plex Sans + Source Serif 4 qua `@fontsource` (đã dùng).
- **Chưa cài skill nào** trong mục 1 vào repo. Hướng thiết kế đã được chép thành luật ở `.cursor/rules/design.mdc` (Cursor đọc file này khi sửa `web/**`). Không nên cài thêm skill của bên thứ ba (impeccable, ui-ux-pro-max, fastapi-templates) khi chưa đọc `SKILL.md` và giấy phép của chúng.
- Các mục dưới đây từ bản 2 được giữ làm danh mục tham khảo; những dòng nói về Jinja2, Tailwind, WeasyPrint, Playwright PDF **không còn áp dụng**.

Cách đọc cột "Xác minh":
- **Đã xem** = tôi mở trang mô tả ngày 13/10/2026 và thấy lệnh cài đặt như ghi.
- **Từ bản cũ** = lấy từ file SKILL_REPOS bản 1, tôi chưa mở lại.
- **Kiến thức riêng** = tôi biết từ trước, chưa mở trang trong phiên này.

Skill có thể chạy code. Đọc `SKILL.md` và license trước khi cài. Nhiều trang tổng hợp không ghi license, nên mở repo gốc để xem.

## 1. Skill cho AI agent

| Repo / skill | Dùng cho | Lệnh cài | Xác minh |
|---|---|---|---|
| [anthropics/skills](https://github.com/anthropics/skills): `frontend-design` | Chốt hướng thẩm mỹ, tránh giao diện "AI slop" | `npx skills add https://github.com/anthropics/skills --skill frontend-design` | Từ bản cũ (skill có sẵn trong Claude) |
| [anthropics/skills](https://github.com/anthropics/skills): `pdf` | Đọc PDF nguồn, kiểm tra PDF xuất ra (trích văn bản, xem từng trang) | `npx skills add https://github.com/anthropics/skills --skill pdf` | Từ bản cũ |
| [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Đặt bối cảnh thiết kế trước khi viết code; có các lệnh `critique`, `audit`, `polish`, `typeset`, `normalize`, `quieter`, `harden`. Hợp để **rà lại** giao diện đã dựng | `npx -y skills add pbakaus/impeccable --skill impeccable --agent claude-code` | Đã xem (trang không ghi license) |
| [nextlevelbuilder/ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | Gợi ý bảng màu, cặp font, quy tắc UX theo loại sản phẩm | `npx skills add https://github.com/nextlevelbuilder/ui-ux-pro-max-skill --skill ui-ux-pro-max` | Từ bản cũ |
| [wshobson/agents](https://github.com/wshobson/agents): `fastapi-templates` | Cấu trúc dự án FastAPI, async, dependency injection, xử lý lỗi | `npx -y skills add wshobson/agents --skill fastapi-templates --agent claude-code` | Đã xem (không ghi license; trang không nhắc phần test) |
| `vercel-design-guidelines` (bản gốc trong [vercel-labs/agent-skills](https://github.com/vercel-labs/agent-skills), tên skill `web-design-guidelines`) | Chạy rà soát giao diện theo checklist (truy cập, UX, hiệu năng) | Xem README của repo gốc | Chỉ thấy bản sao qua mcp.directory; **chưa mở repo gốc** |
| [inbharatai/claude-skills](https://github.com/inbharatai/claude-skills) | Có `pdf`; `dashboard-builder` viết cho Streamlit, ít giá trị sau khi bỏ Streamlit | `git clone`, chép thư mục skill cần dùng | Từ bản cũ |

Danh mục tìm thêm: [travisvn/awesome-claude-skills](https://github.com/travisvn/awesome-claude-skills), [skillcreatorai/Awesome-Agent-Skills](https://github.com/skillcreatorai/Awesome-Agent-Skills).

**Bỏ khỏi danh sách:** `streamlit-facade` và mọi thứ gắn với Streamlit (không còn dùng).

**Dùng với Cursor:** các skill ở trên cài vào `.claude/skills`. Cursor chắc chắn đọc `.cursor/rules/*.mdc` và `AGENTS.md`, còn việc nó có đọc `.claude/skills` hay không phụ thuộc phiên bản. Cách chắc ăn: chép **mục 4 (design brief)** vào `.cursor/rules/design.mdc` với `alwaysApply: true`, và nhờ agent đọc thẳng file `SKILL.md` của skill khi làm giao diện.

**Lưu ý chung:** `frontend-design` và `impeccable` khuyến khích phong cách táo bạo. Với báo cáo đầu tư, ghi rõ trong prompt: *tài chính, chuyên nghiệp, tiết chế, giao diện sáng, mật độ thông tin cao kiểu FireAnt, không trang trí*.

## 2. Thư viện

### Backend
| Thư viện | Vai trò | Ghi chú |
|---|---|---|
| `fastapi`, `uvicorn[standard]` | API và trang | Demo đã dùng, chạy tốt |
| `jinja2` | Template HTML cho trang và PDF | Định dạng số trong Python, không để template tự làm |
| `pydantic` | Mô hình dữ liệu response | Đi kèm FastAPI, dùng để khóa schema API |
| `pandas`, `numpy` | Tính chỉ số | Đã có trong repo |
| [vnstock](https://github.com/thinh-vu/vnstock) | Nguồn dữ liệu của M1 | Giấy phép tuỳ chỉnh, phi thương mại, cần trích dẫn tác giả. **Web không gọi vnstock trực tiếp**, chỉ đọc snapshot và `_result.json` |
| `slowapi` hoặc middleware tự viết | Giới hạn tần suất, nhất là `/report/*.pdf` | Cần khi đưa lên mạng |
| `pytest`, `httpx` | Test API (`TestClient`) | |

### Frontend
| Thư viện | Vai trò | Ghi chú |
|---|---|---|
| Tailwind CSS | Tiện ích CSS | **CDN `cdn.tailwindcss.com` chỉ để dev.** Khi đưa lên mạng dùng [Tailwind standalone CLI](https://tailwindcss.com/blog/standalone-cli) (không cần Node) để build một file CSS |
| [lightweight-charts](https://github.com/tradingview/lightweight-charts) | Biểu đồ nến, khối lượng, đường chỉ báo | **Phiên bản 5** có nhiều pane (giá và RSI/MACD cùng một biểu đồ), bundle nhỏ hơn (khoảng 35 kB), đổi API thêm series thành `addSeries(CandlestickSeries, ...)`. Demo đang ghim 4.2.0 (`addCandlestickSeries`). Đã xem bài giới thiệu v5; **phần breaking change xem trong migration guide chính thức** |
| Apache ECharts (tuỳ chọn) | Biểu đồ radar cho 5 điểm F/T/V/S/R, treemap theo ngành | Chỉ thêm nếu cần; radar đơn giản có thể tự vẽ bằng SVG |
| Alpine.js hoặc htmx (tuỳ chọn) | Tab, lọc, sắp xếp bảng không cần framework | Tải bản đã ghim phiên bản, tự host |
| Lucide (SVG) | Icon | Không dùng emoji làm icon |
| IBM Plex Sans, Source Serif 4 | Font | Giấy phép OFL. **Tự host** (tải file, subset có tiếng Việt), không gọi Google Fonts khi chạy thật |

Attribution: giữ dòng ghi nguồn TradingView Lightweight Charts theo yêu cầu của thư viện (đang có trong demo).

### PDF
| Phương án | Ưu | Nhược | Khuyến nghị |
|---|---|---|---|
| **WeasyPrint** | CSS in ấn tốt (`@page`, số trang, flex/grid cơ bản), nhẹ | Windows cần cài GTK/Pango | Dùng nếu cả nhóm cài được; tôi đã chạy bản 70.0 trên Linux ổn |
| **Playwright + Chromium** (`page.pdf()`) | Cùng engine với trình duyệt, CSS đầy đủ, **dùng chung đúng HTML/CSS với web**, cài trên Windows dễ | Nặng (~150 MB), chậm hơn (1–2 giây/file) | **Chọn nếu WeasyPrint vướng trên Windows** |
| xhtml2pdf | Cài dễ | CSS rất hạn chế, khó đạt giao diện chuyên nghiệp | Không dùng cho bản cuối |
| ReportLab | Ổn định, không phụ thuộc hệ thống | Vẽ tay từng phần, tốn công | Chỉ làm dự phòng |

Biểu đồ cho PDF: vẽ SVG ở phía server bằng cùng bảng màu (demo đã có `price_svg_uri`), hoặc `matplotlib` với style riêng. **Dùng cùng quy ước số với văn bản** (demo hiện lẫn "153.5" trong biểu đồ và "152,96" trong chữ).

## 3. Tham khảo cảm hứng và mã nguồn (đọc để hiểu, không sao chép)

Giao diện:
- **FireAnt**: bố cục dày thông tin. Dải chỉ số thị trường (VN-Index, VN30, HNX, UPCOM) ở đầu trang, bảng giá theo watchlist, trang mã có giá lớn kèm biến động, các tab (tổng quan, giao dịch, hồ sơ, tài chính, tin tức), biểu đồ nến lớn, cột phụ chỉ số cơ bản.
- **Simply Wall St**: hình "snowflake" 5 trục. Tương ứng trực tiếp với 5 điểm F/T/V/S/R của chúng ta; kèm danh sách kiểm tra đạt/không đạt bằng ngôn ngữ thường.
- **Finviz**: bảng sàng lọc và heatmap theo ngành, mật độ cao, ít trang trí.
- **Seeking Alpha**: khối xếp hạng kèm điểm theo nhóm yếu tố, bài phân tích dạng văn.

Mã nguồn:
- [Tumiqa/vn-annual-report-miner](https://github.com/Tumiqa/vn-annual-report-miner): công thức tỷ số.
- [Rarebuffalo/equityforge](https://github.com/Rarebuffalo/equityforge): Jinja2 + WeasyPrint dựng báo cáo kiểu CTCK.
- [natedoggzCD/OptionsToolkit](https://github.com/natedoggzCD/OptionsToolkit): tách `pdf_export.py`.
- [AI4Finance-Foundation/FinRobot](https://github.com/AI4Finance-Foundation/FinRobot): dựng PDF bằng ReportLab.
- Tài liệu lightweight-charts: ví dụ nhiều pane, markers, price scale.

Repo của nhóm khác cùng đề: chỉ xem cấu trúc, không copy code hay layout, vì dễ bị coi là đạo bài. Không chụp hay sao chép giao diện FireAnt: lấy bố cục và nguyên tắc, tự vẽ giao diện và biểu tượng.

## 4. Design brief để dán cho agent (bản web, nền sáng, kiểu FireAnt)

**Chủ đề:** nền tảng phân tích cổ phiếu HOSE/HNX, độc giả là nhà đầu tư và giảng viên chấm bài. Nền sáng, dày thông tin, tiết chế. Học bố cục của FireAnt, không bắt chước nhận diện của họ.

**Màu (token CSS `:root`):**

| Token | Mã | Dùng cho | Tương phản trên trắng |
|---|---|---|---|
| `--paper` | `#FFFFFF` | Nền | |
| `--wash` | `#F3F5F8` | Nền phụ, hàng tiêu đề bảng | |
| `--ink` | `#121C2D` | Chữ chính | 17,1 |
| `--muted` | `#5B6675` | Chữ phụ | 5,8 |
| `--primary` | `#1B4B7A` | Màu chính, liên kết | 9,0 |
| `--accent` | `#0E7C86` | Nhấn (teal) | 5,0 |
| `--rule` | `#D5DAE1` | Đường kẻ | |
| `--up` | `#1E7B34` | Giá tăng | 5,3 |
| `--down` | `#C0392B` | Giá giảm | 5,4 |
| `--ref` | `#946200` | Giá tham chiếu (vàng đất) | 5,2 |
| `--ceiling` | `#7A3FA0` | Giá trần (tím) | 6,9 |
| `--floor` | `#0A7287` | Giá sàn (xanh lơ) | 5,6 |

Quy ước màu thị trường VN: xanh = tăng, đỏ = giảm, vàng = tham chiếu, tím = trần, xanh lơ = sàn. Chỉ dùng cho biến động giá và chênh lệch so với tham chiếu, **không dùng để trang trí**. Luôn đi kèm dấu `+/−` hoặc mũi tên, không dựa vào màu một mình.

**Font:** Source Serif 4 cho tiêu đề lớn, IBM Plex Sans cho nội dung và bảng; số dùng `font-variant-numeric: tabular-nums`. Phải hiển thị đúng dấu tiếng Việt; thử chuỗi "Nguyễn thương mại lượng điều tra được".

**Bố cục:** dải chỉ số thị trường ở đầu; thanh tìm mã có gợi ý; trang mã gồm khối giá lớn, tab, biểu đồ chiếm 2/3 chiều rộng, cột phụ chỉ số cơ bản. Bảng cỡ chữ 13 px, hàng cao 32–36 px, tiêu đề cố định khi cuộn, căn phải cho số.

**Tránh:** gradient, glassmorphism, emoji làm icon, thẻ bo góc đổ bóng lặp lại, lưới 3 thẻ "tính năng", nhãn viết hoa toàn bộ, đánh số 01/02/03 khi nội dung không phải trình tự, hero lớn khi người dùng đến để tra số, huy hiệu "AI-powered", hiệu ứng chuyển động trang trí, font mặc định kiểu Inter, bảng màu tím-xanh dương mặc định.

**Nội dung:**
- Mỗi nhận định gắn một con số, một nguồn và ngày dữ liệu.
- Mỗi biểu đồ có tiêu đề nêu kết luận, dòng nguồn, đơn vị trục.
- Một quy ước số duy nhất (dấu chấm ngăn nghìn, dấu phẩy thập phân), định dạng bằng hàm Python dùng chung cho web, API hiển thị và PDF.
- Mã không xếp hạng (insufficient) hiện lý do cụ thể (ví dụ "thanh khoản dưới 1 tỷ đồng/phiên"), không để trống và không điền số giả.
- Trạng thái chờ, lỗi, rỗng đều được thiết kế, không để bảng trắng.
- Giá hiển thị theo nghìn đồng như FireAnt (130,5), nhưng dữ liệu nội bộ giữ VND; chuyển đổi ở một chỗ duy nhất.

## 5. Dựng PDF từ cùng bộ token

Cấu trúc gợi ý:

```
src/stockai/web/
  static/css/tokens.css      # token màu, font, cỡ chữ: dùng chung cho web và PDF
  static/fonts/              # IBMPlexSans-*.woff2 / .ttf, SourceSerif4-*.ttf (có subset tiếng Việt)
  templates/stock.html
  templates/report/report.html
  templates/report/report.css
```

Quy tắc:
- `report.css` nạp `tokens.css`, khai báo `@font-face` trỏ file font cục bộ, và `@page { size: A4; margin: 16mm }` kèm số trang ở chân trang.
- Các mục dùng `break-inside: avoid`; bảng dài lặp tiêu đề (`thead { display: table-header-group }`).
- `context` cho template do Python dựng sẵn chuỗi đã định dạng (rating, điểm, giá mục tiêu, chỉ số, nguồn). Mã không xếp hạng phải có nhánh riêng: ghi lý do, không in "NaN" hay "None".
- Ảnh biểu đồ truyền vào dạng data URI hoặc đường dẫn file.

```python
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML          # hoặc playwright: page.set_content(html); page.pdf(...)

env = Environment(loader=FileSystemLoader("templates/report"), autoescape=True)
html = env.get_template("report.html").render(**context)
HTML(string=html, base_url="templates/report").write_pdf("FPT_report.pdf")
```

## 6. Kiểm tra trước khi nộp

- Mỗi con số có nguồn và ngày dữ liệu. Đối chiếu ngẫu nhiên 5 chỉ số (P/E, ROE, tăng trưởng doanh thu...) giữa **web, PDF và snapshot JSON**: ba nơi phải trùng.
- Thử chuỗi dấu phức tạp trên web và trong PDF; chạy `pdffonts` để chắc font nhúng đúng là IBM Plex/Source Serif, **không phải DejaVu** (dấu hiệu rơi về font mặc định).
- Chụp màn hình bằng Playwright ở 1440, 1024 và 390 px; xem thêm ở thang xám để chắc biểu đồ và bảng vẫn đọc được.
- Kiểm tra tương phản và nhãn truy cập (Lighthouse hoặc axe).
- Giá mục tiêu và khuyến nghị xuất phát từ mô hình định giá có giả định ghi rõ, không điền cho đẹp.
- Trước khi đưa lên mạng: không có khóa API hay token trong mã, trong repo hay trong response; `/report/*.pdf` có giới hạn tần suất; chạy bằng dữ liệu snapshot chứ không gọi nguồn ngoài theo mỗi lượt xem.
