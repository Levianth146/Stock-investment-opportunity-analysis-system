# Fixtures HTML cổng tin (003)

**Bắt buộc**: mọi file HTML dưới đây MUST là bản lưu từ trang thật (spike T004),
không tự viết markup giả.

Cấu trúc gợi ý:

```text
tests/fixtures/news_portals/
  cafef/
    search_VCB.html
    article_dated.html
    article_asof_date_only.html   # nếu có; hoặc annotate
    article_undated_meta_stripped.html  # HTML thật, meta ngày đã gỡ để test drop
  vneconomy/
    ...
  tinnhanhchungkhoan/
    ...
  SPIKE_NOTES.md                  # robots.txt / JS-out / URL đã thử
```

Cổng bắt buộc render JS → ghi trong `SPIKE_NOTES.md` và loại khỏi phạm vi phiên bản này.
