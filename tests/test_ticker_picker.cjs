// Run: node --test --test-isolation=none tests/test_ticker_picker.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const jsx = require('../frontend/node_modules/react/jsx-runtime');
const { renderToStaticMarkup } = require('../frontend/node_modules/react-dom/server');
const tick = () => new Promise(resolve => setImmediate(resolve));
function load(fetch) {
  const context = { fetch, window: { StockAI: {}, addEventListener() {}, removeEventListener() {} } };
  vm.runInNewContext(fs.readFileSync('frontend/dist/assets/ticker-picker.js', 'utf8'), context);
  return context.window.StockAI;
}
function find(tree, predicate) {
  if (!tree || typeof tree !== 'object') return;
  if (predicate(tree)) return tree;
  for (const child of [tree.props?.children].flat(2)) {
    const result = find(child, predicate);
    if (result) return result;
  }
}
function harness(api) {
  const states = [], effects = [], selected = [];
  let cursor = 0, effectCursor = 0, closed = 0;
  const props = { jsx, isOpen: true, onClose: () => { closed++; }, onSelectStock: ticker => selected.push(ticker), react: {
    useState(initial) {
      const index = cursor++;
      if (!(index in states)) states[index] = initial;
      return [states[index], value => { states[index] = typeof value === 'function' ? value(states[index]) : value; }];
    },
    useEffect(callback, deps) {
      const index = effectCursor++, old = effects[index];
      if (old && old.deps.every((value, position) => value === deps[position])) return;
      old?.cleanup?.(); effects[index] = { deps, cleanup: callback() };
    }
  } };
  const render = () => { cursor = 0; effectCursor = 0; return api.TickerPicker(props); };
  return { render, props, selected, closed: () => closed };
}

test('picker loads and renders every snapshot ticker, including stocks outside the demo list', async () => {
  let calls = 0;
  const items = Array.from({ length: 707 }, (_, i) => ({ symbol: `T${String(i).padStart(3, '0')}`, name: `Company ${i}`, exchange: 'HNX', current_price: i * 1000, snapshot_status: 'ok' }));
  const api = load(async url => { calls++; assert.equal(url, '/api/tickers'); return { ok: true, json: async () => ({ items, total: 707, asof: '2026-10-08' }) }; });
  const ui = harness(api);
  ui.render(); await tick();
  const tree = ui.render(), html = renderToStaticMarkup(tree);
  assert.match(html, /707 kết quả \/ 707 mã/);
  assert.match(html, /T706/);
  assert.match(html, /706\.000/);
  const stock = find(tree, node => node.type === 'button' && node.key === 'T706');
  stock.props.onClick();
  assert.deepEqual(ui.selected, ['T706']);
  assert.equal(ui.closed(), 1);
  await api.loadTickerCatalog();
  assert.equal(calls, 1); // Cached independently of full analysis requests.
});

test('search supports names without accents, exact tickers and exchange filters', () => {
  const api = load();
  const items = [{ symbol: 'HPG', name: 'Hòa Phát', exchange: 'HSX' },
    { symbol: 'H', name: 'Công ty HPG', exchange: 'HNX' }, { symbol: 'CEO', name: 'Đầu tư CEO', exchange: 'HNX' }];
  assert.equal(api.filterTickers(items, 'hoa phat')[0].symbol, 'HPG');
  assert.equal(api.filterTickers(items, 'dau tu')[0].symbol, 'CEO');
  assert.equal(api.filterTickers(items, 'hpg')[0].symbol, 'HPG');
  assert.deepEqual(Array.from(api.filterTickers(items, '', 'HNX'), item => item.symbol), ['CEO', 'H']);
});

test('catalog errors can be retried and never fall back to ten demo stocks', async () => {
  let calls = 0;
  const api = load(async () => ++calls === 1 ? { ok: false } : { ok: true, json: async () => ({ items: [{ symbol: 'NEW', name: 'New company' }], total: 1 }) });
  const ui = harness(api);
  ui.render(); await tick();
  let tree = ui.render();
  assert.match(renderToStaticMarkup(tree), /Không tải được danh sách/);
  assert.doesNotMatch(renderToStaticMarkup(tree), /FPT|HPG|VNM/);
  find(tree, node => node.type === 'button' && node.props.children === 'Thử tải lại').props.onClick();
  ui.render(); await tick(); tree = ui.render();
  assert.match(renderToStaticMarkup(tree), /New company/);
  assert.equal(calls, 2);
});

test('picker input filters the catalog and Enter selects the matching symbol', async () => {
  const api = load(async () => ({ ok: true, json: async () => ({ items: [
    { symbol: 'AAA', name: 'An Phát' }, { symbol: 'CEO', name: 'Đầu tư CEO' }
  ] }) }));
  const ui = harness(api);
  ui.render(); await tick();
  find(ui.render(), node => node.type === 'input').props.onChange({ target: { value: 'dau tu' } });
  const tree = ui.render();
  assert.match(renderToStaticMarkup(tree), /1 kết quả \/ 2 mã/);
  assert.doesNotMatch(renderToStaticMarkup(tree), /An Phát/);
  find(tree, node => node.type === 'input').props.onKeyDown({ key: 'Enter' });
  assert.deepEqual(ui.selected, ['CEO']);
});
