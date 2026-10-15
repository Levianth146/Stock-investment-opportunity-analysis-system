# Dynamic report cover assets

M9 looks for optional company-specific cover assets in:

`assets/branding/<TICKER>/logo.png` and `assets/branding/<TICKER>/hero.jpg`

PNG/JPG/JPEG/WEBP are accepted. If no company asset exists, M9 renders a deterministic sector-based cover from the M1 company metadata (ticker, company name, sector), so PDF generation never depends on network access.

These assets affect presentation only; all analytical numbers and conclusions continue to come from M1-M8.
