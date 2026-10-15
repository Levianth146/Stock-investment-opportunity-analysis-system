# M9 PDF redesign - approved layout

## Non-negotiable data rule
M9 is presentation-only. Analytical values, claims and conclusions must come from snapshot M1 and outputs M2-M8. M9 does not call the network, does not create forecasts/DCF/consensus, and does not invent metrics to fill space.

## Dynamic cover
- Optional assets: `assets/branding/<TICKER>/logo.*` and `hero.*`.
- If assets are absent, cover falls back to a deterministic sector-based visual using ticker/company/sector from M1.
- Branding affects appearance only, never scores or conclusions.

## Final page structure for ranked securities
1. Dynamic cover
2. Investment overview - score, rating, current/base price, contributions, readable support/pressure factors
3. Fundamental performance - F, ROE, growth, annual and quarterly revenue/profit, M2 ratios
4. Financial structure & cash flow - balance sheet series, liquidity, CFO/CFI/CFF, historical table
5. Relative valuation - P/E, P/B, correct sector/market benchmark label, Bear/Base/Bull/current price scale, short assessment
6. Technical analysis - price + MA20/50/200, RSI, MACD, volume ratio, ATR, concise interpretation
7. Risk analysis - R, volatility, beta, max drawdown, drawdown path, up/down sessions, VaR/CVaR
8. News & sentiment - S/availability, story/source counts, title-level M5 scope, readable headline list
9. Verification & methodology - M8 issues, quality limitations, score interpretation, sources, academic disclaimer

## Presentation decisions
- Remove pipeline status chips and repetitive source/disclaimer footer from content pages.
- Use short consistent headings.
- Split technical and risk content instead of crowding one page.
- Do not dump raw M4 assumption strings into the valuation page.
- M4 fallback uses the correct label `Trung vị thị trường` instead of `Trung vị ngành`.
- M8 severity `fatal` counts as a serious warning.
- M5 partial is shown honestly; if M7 substitutes S=50, the report says so.
