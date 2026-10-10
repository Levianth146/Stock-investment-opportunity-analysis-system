# Spike notes (T004)

- cafef/robots: ok bytes=111 js_hints=0 url=https://cafef.vn/robots.txt
- cafef/search: ok bytes=82806 js_hints=0 url=https://cafef.vn/tim-kiem.chn?keywords=VCB
- cafef/article: no href found in search HTML
- vneconomy/robots: ok bytes=779 js_hints=0 url=https://vneconomy.vn/robots.txt
- vneconomy/search: ok bytes=125013 js_hints=0 url=https://vneconomy.vn/search.htm?q=VCB
- vneconomy/article: ok bytes=180749 url=https://premium.vneconomy.vn/nen-tang-ai-asko.html
- tinnhanhchungkhoan/robots: ok bytes=340 js_hints=0 url=https://www.tinnhanhchungkhoan.vn/robots.txt
- tinnhanhchungkhoan/search: FAIL HTTPError: HTTP Error 404: Not Found url=https://www.tinnhanhchungkhoan.vn/tim-kiem.htm?keywords=VCB

## Round 2

- cafef: OK 477858 links=76 final=https://cafef.vn/du-lieu/hose/vcb-ngan-hang-thuong-mai-co-phan-ngoai-thuong-viet-nam.chn
- cafef: saved listing -> listing.html from https://cafef.vn/du-lieu/hose/vcb-ngan-hang-thuong-mai-co-phan-ngoai-thuong-viet-nam.chn
- cafef: FAIL HTTPError: HTTP Error 404: Not Found :: https://cafef.vn/hose/vcb-vietcombank.chn
- cafef: OK 477858 links=76 final=https://cafef.vn/du-lieu/hose/vcb-ngan-hang-thuong-mai-co-phan-ngoai-thuong-viet-nam.chn
- cafef: saved listing -> listing.html from https://cafef.vn/du-lieu/hose/vcb-ngan-hang-thuong-mai-co-phan-ngoai-thuong-viet-nam.chn
- cafef: OK 114258 links=61 final=https://cafef.vn/tai-chinh-ngan-hang.chn
- cafef: OK 103512 links=58 final=https://cafef.vn/thi-truong-chung-khoan.chn
- cafef: saved listing -> listing.html from https://cafef.vn/thi-truong-chung-khoan.chn
- vneconomy: OK 42341 links=0 final=https://vneconomy.vn/chung-khoan.htm
- vneconomy: saved listing -> listing.html from https://vneconomy.vn/chung-khoan.htm
- vneconomy: OK 127288 links=83 final=https://vneconomy.vn/tim-kiem.htm?keyword=VCB
- vneconomy: saved listing -> listing.html from https://vneconomy.vn/tim-kiem.htm?keyword=VCB
- vneconomy: OK 24173 links=0 final=https://vneconomy.vn/tag/vcb
- vneconomy: saved listing -> listing.html from https://vneconomy.vn/tag/vcb
- tinnhanhchungkhoan: OK 116088 links=96 final=https://www.tinnhanhchungkhoan.vn/chung-khoan/
- tinnhanhchungkhoan: saved listing -> listing.html from https://www.tinnhanhchungkhoan.vn/chung-khoan/
- tinnhanhchungkhoan: OK 109820 links=89 final=https://www.tinnhanhchungkhoan.vn/thong-tin-doanh-nghiep/
- tinnhanhchungkhoan: OK 120337 links=105 final=https://www.tinnhanhchungkhoan.vn/ngan-hang/
- cafef/article: OK 103512 https://cafef.vn/thi-truong-chung-khoan.chn
- tnck/article: OK 20105 https://www.tinnhanhchungkhoan.vn/giao-dich-chung-khoan-khoi-ngoai-tuan-5-910-ban-rong-ky-luc-gan-14000-ty-dong-post399175.html

## Round 3

- cafef search/listing saved 477858 https://cafef.vn/du-lieu/hose/vcb-ngan-hang-thuong-mai-co-phan-ngoai-thuong-viet-nam.chn
- vneconomy search saved 127288 https://vneconomy.vn/tim-kiem.htm?keyword=VCB
- vneconomy article 42323 https://vneconomy.vn/nhip-cau-doanh-nghiep.htm
- tnck listing saved 120337 https://www.tinnhanhchungkhoan.vn/ngan-hang/
- tnck article 91666 https://www.tinnhanhchungkhoan.vn/mb-mo-rong-vai-tro-ket-noi-dong-von-post398205.html
- cafef: wrote undated stripped fixture
- vneconomy: wrote undated stripped fixture
- tinnhanhchungkhoan: wrote undated stripped fixture

## Kết luận phạm vi (sau spike)

- **CafeF**: `tim-kiem.chn` gần như shell (ít/không có link bài trong HTML tĩnh) → dùng trang mã
  `du-lieu/hose/<ticker>-....chn` làm listing/search theo mã (HTML tĩnh có link bài `.chn`).
  robots.txt đọc được; không bắt buộc JS cho listing mã + trang bài.
- **VnEconomy**: `tim-kiem.htm?keyword=` trả HTML có link bài; trang bài `.htm` tĩnh.
  robots.txt đọc được. (Bỏ bài premium nếu bắt login.)
- **TinNhanhChungKhoan**: URL `tim-kiem.htm` 404; dùng chuyên mục (vd `/ngan-hang/`) làm listing
  theo ngữ cảnh mã/ngành; trang bài `*-postNNNN.html` tĩnh. robots.txt đọc được.
- Không cổng nào bị loại vì bắt buộc JS render cho đường listing+article đã chọn ở trên.

## Round fix
- cafef article: https://cafef.vn/goi-dien-xac-nhan-chuyen-khoan-700-trieu-dong-cho-truong-hoc-nhung-truong-quyet-khong-nhan-nguoi-phu-nu-ha-noi-bao-cong-an-188250925172829926.chn
- ve search listing: chung-khoan.htm; article: None
- CafeF search shell `tim-kiem.chn` JS-heavy → dùng `vcb-tin-tuc.chn` làm listing theo mã.
- Không loại cổng vì JS bắt buộc trên đường listing+article đã chọn.

## Probe VnEconomy tim-kiem.htm?keyword= (re-check)

- status=200 bytes=127288 final=https://vneconomy.vn/tim-kiem.htm?keyword=VCB
- Lần parse đầu lấy nhầm trang mục ngắn (`kinh-te-so.htm`, …) → tưởng không có bài.
- Parse đúng: chỉ lấy slug `.htm` dài ≥40 ký tự, bỏ premium → có bài thật, ví dụ:
  - `/du-lich-va-hang-khong-chiem-vi-tri-cao-nhat-ve-tim-kiem-cua-nguoi-viet-trong-quy-2-2022.htm`
  - `/quet-sach-thanh-qua-3-phien-tang-vn-index-giam-manh-thu-thach-day-ngan-han.htm`
- Article mẫu: published_time=True (2022-08-08), lưu `vneconomy/article_dated.html`
- VERDICT: VnEconomy **IN SCOPE** — `tim-kiem.htm?keyword=` + slug dài; không JS-only.

## Probe CafeF listing HPG/FPT/VNM/MWG (không phải test CI)

- HPG: status=200 bytes=192073 article_links=20 url=https://cafef.vn/du-lieu/hose/hpg-tin-tuc.chn
- FPT: status=200 bytes=191594 article_links=20 url=https://cafef.vn/du-lieu/hose/fpt-tin-tuc.chn
- VNM: status=200 bytes=191917 article_links=20 url=https://cafef.vn/du-lieu/hose/vnm-tin-tuc.chn
- MWG: status=200 bytes=192233 article_links=20 url=https://cafef.vn/du-lieu/hose/mwg-tin-tuc.chn
- Ghi chú: trang tin-tuc lẫn tin chung → runtime dùng `tim-kiem.chn?keywords=` + lọc `\bTICKER\b`.

## Chẩn đoán HPG/FPT + quyết định active (2026-10-10)

- **VnEconomy**: HTML tĩnh `tim-kiem.htm?keyword=` trả cùng ~5 link cho mọi mã;
  kết quả tìm kiếm thật nạp bằng JS → không phục vụ theo mã.
- **TNCK**: chuyên mục `/ngan-hang/` không theo mã; probe 30/30 bài irrelevant sau lọc.
- **CafeF**: tìm theo mã ổn → `news_portals_active: [cafef]` mặc định.
- Parser VE/TNCK giữ trong code; **không** chạy mặc định.
- **Điều kiện thêm lại**: endpoint tìm kiếm theo mã hoặc RSS theo mã.
