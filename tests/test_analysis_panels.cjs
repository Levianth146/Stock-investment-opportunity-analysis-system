// Run: node --test --test-isolation=none tests/test_analysis_panels.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const jsx = require('../frontend/node_modules/react/jsx-runtime');
const { renderToStaticMarkup } = require('../frontend/node_modules/react-dom/server');

function adapter() {
  const context = { window: {}, document: { getElementById: () => ({ style: {} }) } };
  for (const path of ['frontend/dist/api-client.js', 'frontend/dist/assets/analysis-panels.js']) {
    vm.runInNewContext(fs.readFileSync(path, 'utf8'), context);
  }
  return context.window.StockAI;
}
const metric = (value, unit = 'VND/share') => ({ value, unit });
function data(ticker, multiplier = 1) {
  return {
    ticker, as_of: '2026-10-08', price_date: '2026-10-08', profile: 'long_term',
    current_price: 10000 * multiplier, target: { base: 12000 * multiplier, bull: 15000 * multiplier,
      bear: 8000 * multiplier, method: 'relative_multiples_pe_pb', assumptions: [`Assumption ${ticker}`] },
    score: 50 * multiplier, scores: { F: 30 * multiplier, T: 25 * multiplier, V: 30 * multiplier, S: 20 * multiplier, R: 20 * multiplier },
    company: { name: `Company ${ticker}`, sector: `Sector ${ticker}`, exchange: 'HSX' },
    price_change: 0, price_change_percent: 0, volume: 100000 * multiplier,
    bull: [{ text: `Bull ${ticker}`, refs: ['m4.pe', 'n1'] }], bear: [{ text: `Bear ${ticker}`, refs: ['m6.beta'] }],
    debate_source: 'template', news_ref_map: { n1: `news-${ticker}` },
    news: [{ id: `news-${ticker}`, title: `Headline ${ticker}`, source: `Source ${ticker}`, summary: `Summary ${ticker}`,
      published_at: '2026-10-07', url: `https://example.com/${ticker}`, label: 'pos' }], flags: [`flag_${ticker}`],
    modules: {
      m2: { status: 'ok', score: 30 * multiplier, metrics: { roe: metric(10 * multiplier, '%') } },
      m5: { status: 'ok', score: 20 * multiplier, metrics: { news_relevant_count: metric(5 * multiplier, 'articles'),
        news_positive_count: metric(multiplier, 'articles') }, evidence: [], flags: [] },
      m3: { status: 'ok', score: 25 * multiplier, metrics: { close: metric(10000 * multiplier),
        ma20: metric(9000 * multiplier), rsi14: metric(20 * multiplier, 'points') }, evidence: [], flags: [] },
      m4: { status: 'partial', score: 30 * multiplier, metrics: { pe: metric(8 * multiplier, 'x'),
        pb: metric(null, 'x') }, flags: [`valuation_${ticker}`], evidence: [] },
      m6: { status: 'ok', score: 20 * multiplier, metrics: { beta: metric(0.5 * multiplier, 'times'),
        max_drawdown: metric(10 * multiplier, '%'), historical_var_95: metric(2 * multiplier, '%') }, flags: [], evidence: [] }
    },
    validation: { status: 'warn', checked: 30 * multiplier, issues: [{ severity: 'warn', message: `Issue ${ticker}`, where: 'financials' }] },
    quality_gate: { scored: true },
    price_history: [{ date: '2026-10-07', close: 9500 * multiplier }, { date: '2026-10-08', close: 10000 * multiplier }]
  };
}
function render(api, component, stock) {
  return renderToStaticMarkup(api[component]({ jsx, react: { useState: value => [value, () => {}] }, stock }));
}

test('all three tabs render backend values for the selected ticker through the real adapter', () => {
  const api = adapter();
  const a = api.toStock(data('AAA'), { factors: {} });
  const b = api.toStock(data('BBB', 2), { factors: {} });
  const ta = render(api, 'TechnicalAnalysis', a), tb = render(api, 'TechnicalAnalysis', b);
  assert.match(ta, /AAA/); assert.match(tb, /BBB/);
  assert.match(ta, />9\.000<\/td>/); assert.match(tb, />18\.000<\/td>/);
  assert.match(ta, />10\.000<\/text>/); assert.match(tb, />20\.000<\/text>/);
  const va = render(api, 'ValuationAnalysis', a), vb = render(api, 'ValuationAnalysis', b);
  assert.match(va, />12\.000<\/td>/); assert.match(vb, />24\.000<\/td>/);
  assert.match(va, /Assumption AAA/); assert.match(vb, /Assumption BBB/);
  assert.match(va, /valuation_AAA/); assert.doesNotMatch(vb, /valuation_AAA/);
  const ra = render(api, 'RiskAnalysis', a), rb = render(api, 'RiskAnalysis', b);
  assert.match(ra, />0,5<\/td>/); assert.match(rb, />1<\/td>/);
  assert.match(ra, /Issue AAA/); assert.match(rb, /Issue BBB/);
  assert.doesNotMatch(rb, /Issue AAA/);
});

test('missing and stale analysis never uses demo or another ticker data', () => {
  const api = adapter();
  for (const stock of [{ symbol: 'BBB', backendAnalysis: data('AAA') }, { symbol: 'BBB', sma20: 123456, targetPrice: 999999, audit: { auditor: 'Demo Auditor' } }]) {
    for (const component of ['TechnicalAnalysis', 'ValuationAnalysis', 'RiskAnalysis', 'OverviewAnalysis', 'NewsAnalysis', 'BullBearAnalysis']) {
      const html = render(api, component, stock);
      assert.match(html, /Chưa tải được/);
      assert.doesNotMatch(html, /Assumption AAA|Issue AAA|Demo Auditor|123\.456|999\.999/);
      assert.doesNotMatch(html, /Headline AAA|Bull AAA|Bear AAA/);
    }
  }
});

test('valuation never republishes a target suppressed by the quality gate', () => {
  const api = adapter(), input = data('AAA');
  input.modules.m4.target = input.target;
  input.target = null;
  input.quality_gate = { scored: false, reasons: ['insufficient_data'] };
  const html = render(api, 'ValuationAnalysis', api.toStock(input, { factors: {}, targetPrice: 999999 }));
  assert.match(html, /Chưa có giá mục tiêu được công bố/);
  assert.match(html, /insufficient_data/);
  assert.doesNotMatch(html, /12\.000|999\.999/);
});

test('missing metrics, zero values and non-live prices are explicit', () => {
  const api = adapter(), input = data('AAA');
  input.modules.m6.metrics.beta.value = 0;
  input.modules.m6.metrics.historical_var_95.value = null;
  const stock = api.toStock(input, { factors: {} });
  const html = render(api, 'RiskAnalysis', stock);
  assert.match(html, />0<\/td>/); assert.match(html, />—<\/td>/);
  assert.match(html, /không xác nhận BCTC đã được kiểm toán độc lập/);
  assert.doesNotMatch(html, /NaN|Infinity/);
  assert.match(render(api, 'TechnicalAnalysis', stock), /Giá theo snapshot/);
  assert.match(render(api, 'ValuationAnalysis', stock), /Giá đóng cửa/);
});

test('technical chart range changes the actual series', () => {
  const api = adapter(), input = data('AAA');
  input.price_history = Array.from({ length: 150 }, (_, i) => ({ date: `day-${i}`, close: 10000 + i * i }));
  let range = '3m';
  const props = { jsx, react: { useState: () => [range, value => { range = value; }] }, stock: api.toStock(input, { factors: {} }) };
  const tree = api.TechnicalAnalysis(props);
  const buttons = tree.props.children[1].props.children[1].props.children;
  assert.match(renderToStaticMarkup(tree), /63 phiên hiển thị/);
  buttons.find(button => button.key === '6m').props.onClick();
  assert.match(renderToStaticMarkup(api.TechnicalAnalysis(props)), /126 phiên hiển thị/);
});

test('price chart selects actual sessions with scaled pointer coordinates and keyboard, and clears stale tooltips', () => {
  const api = adapter(), input = data('AAA');
  let state = [], cursor = 0;
  const props = { jsx, compact: true, stock: api.toStock(input, { factors: {} }), react: {
    useState(initial) {
      const index = cursor++;
      if (state[index] === undefined) state[index] = initial;
      return [state[index], value => { state[index] = value; }];
    }
  } };
  const renderChart = () => { cursor = 0; return api.TechnicalAnalysis(props); };
  const svgOf = tree => tree.props.children.find(child => child?.type === 'svg');
  const pointer = x => ({ clientX: x, clientY: 80, currentTarget: {
    getScreenCTM: () => ({ inverse: () => ({}) }),
    createSVGPoint: () => ({ matrixTransform() { return { x: (this.x - 100) / 2 }; } })
  } });
  let tree = renderChart();
  svgOf(tree).props.onPointerMove(pointer(200));
  tree = renderChart();
  assert.match(renderToStaticMarkup(tree), /9\.500 VND\/cổ phiếu/);
  assert.match(renderToStaticMarkup(tree), /role="status"/);
  svgOf(tree).props.onPointerMove(pointer(5000));
  tree = renderChart();
  assert.match(renderToStaticMarkup(tree), /10\.000 VND\/cổ phiếu/);
  svgOf(tree).props.onKeyDown({ key: 'ArrowLeft', preventDefault() {} });
  assert.match(renderToStaticMarkup(renderChart()), /9\.500 VND\/cổ phiếu/);
  svgOf(tree).props.onPointerLeave();
  assert.doesNotMatch(renderToStaticMarkup(renderChart()), /role="status"/);
  svgOf(tree).props.onFocus();
  tree = renderChart();
  assert.match(renderToStaticMarkup(tree), /10\.000 VND\/cổ phiếu/);
  tree.props.children[1].props.children.find(button => button.key === '6m').props.onClick();
  assert.doesNotMatch(renderToStaticMarkup(renderChart()), /role="status"/);
  props.stock = api.toStock(data('BBB', 2), { factors: {} });
  assert.doesNotMatch(renderToStaticMarkup(renderChart()), /role="status"/);
});

test('out-of-order analyze responses cannot overwrite the latest ticker', async () => {
  // Exercise the actual request handler mounted in the supplied bundle.
  const bundle = fs.readFileSync('frontend/dist/assets/index-CI87uAUB.js', 'utf8');
  const begin = bundle.indexOf('Se=async e=>') + 3;
  const end = bundle.indexOf(';(0,_.useEffect)', begin);
  const pending = {}, updates = [], loading = [], api = adapter();
  const request = vm.runInNewContext('(' + bundle.slice(begin, end) + ')', {
    requestRef: { current: 0 },
    fetch: (_url, options) => new Promise(resolve => { pending[JSON.parse(options.body).ticker] = resolve; }),
    l: value => loading.push(value), s: value => updates.push(value),
    window: { StockAI: api }, y: { AAA: { factors: {} }, BBB: { factors: {} }, FPT: { factors: {} } },
    console: { log() {}, error() {} }
  });
  const a = request('AAA'), b = request('BBB');
  pending.BBB({ ok: true, json: async () => data('BBB', 2) });
  await b;
  pending.AAA({ ok: true, json: async () => data('AAA') });
  await a;
  assert.deepEqual(updates.map(stock => stock.symbol), ['BBB']);
  assert.equal(updates[0].backendAnalysis.ticker, 'BBB');
  assert.deepEqual(loading, [true, true, false]);
});

test('overview, news and bull/bear use selected ticker data without fabricated claims', () => {
  const api = adapter();
  for (const [ticker, multiplier] of [['AAA', 1], ['BBB', 2]]) {
    const stock = api.toStock(data(ticker, multiplier), { factors: {} });
    const overview = render(api, 'OverviewAnalysis', stock);
    assert.match(overview, new RegExp(`Tổng quan \\(${ticker}\\)`));
    assert.match(overview, new RegExp(`>${multiplier === 1 ? '10\\.000' : '20\\.000'}<\\/td>`));
    assert.match(overview, new RegExp(`Bull ${ticker}`));
    assert.match(render(api, 'StockSummaryHeader', stock), new RegExp(`Company ${ticker}`));
    const news = render(api, 'NewsAnalysis', stock);
    assert.match(news, new RegExp(`Headline ${ticker}`));
    assert.match(news, new RegExp(`Summary ${ticker}`));
    assert.match(news, new RegExp(`https://example.com/${ticker}`));
    assert.match(news, new RegExp(`Điểm sentiment: ${20 * multiplier} / 100`));
    const debate = render(api, 'BullBearAnalysis', stock);
    assert.match(debate, new RegExp(`Bull ${ticker}`));
    assert.match(debate, new RegExp(`Bear ${ticker}`));
    assert.match(debate, new RegExp(`n1: Headline ${ticker}`));
    assert.match(debate, /Luận điểm theo quy tắc/);
    for (const html of [overview, news, debate]) {
      assert.doesNotMatch(html, /45 đầu báo|18 công ty|6,2%|6\.2%|Bầu Bull|84%|AI Factory|Cực kỳ Lạc quan/);
      assert.doesNotMatch(html, new RegExp(`Headline ${ticker === 'AAA' ? 'BBB' : 'AAA'}`));
    }
  }
});

test('news filtering preserves actual classifications and rejects unsafe article URLs', () => {
  const api = adapter(), input = data('AAA');
  input.news.push({ id: 'negative', title: 'Negative headline', label: 'neg', url: 'javascript:alert(1)' });
  let filter = 'all';
  const props = { jsx, react: { useState: () => [filter, value => { filter = value; }] }, stock: api.toStock(input, { factors: {} }) };
  const tree = api.NewsAnalysis(props);
  assert.match(renderToStaticMarkup(tree), /Negative headline/);
  assert.doesNotMatch(renderToStaticMarkup(tree), /javascript:|href="javascript/);
  const select = tree.props.children[1].props.children[2].props.children[1];
  select.props.onChange({ target: { value: 'neg' } });
  const html = renderToStaticMarkup(api.NewsAnalysis(props));
  assert.match(html, /Negative headline/);
  assert.doesNotMatch(html, /Headline AAA/);
});

test('overview links navigate to the matching analysis tab', () => {
  const api = adapter(), selected = [];
  const tree = api.OverviewAnalysis({ jsx, react: { useState: value => [value, () => {}] },
    stock: api.toStock(data('AAA'), { factors: {} }), onNavigateTab: value => selected.push(value) });
  const factorRows = tree.props.children[2].props.children[1].props.children.props.children[1].props.children;
  factorRows[3].props.children[3].props.children.props.onClick();
  tree.props.children[3].props.children[3].props.onClick();
  assert.deepEqual(selected, ['news', 'bullbear']);
});

test('unknown tickers never inherit the demo company identity while loading or missing metadata', () => {
  const api = adapter();
  const legacy = { name: 'FPT Corp', symbol: 'FPT', exchange: 'HSX', industry: 'Technology', factors: {} };
  const pending = api.pendingStock('NEW', legacy);
  assert.equal(pending.symbol, 'NEW');
  assert.equal(pending.name, 'NEW');
  assert.equal(pending.backendAnalysis, null);
  const input = data('NEW'); input.company = {};
  const stock = api.toStock(input, legacy);
  assert.equal(stock.name, 'NEW');
  assert.equal(stock.exchange, '—');
  assert.equal(stock.industry, '—');
});
