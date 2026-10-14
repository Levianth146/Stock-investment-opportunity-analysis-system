// Run: node --test --test-isolation=none tests/test_financial_reports.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const jsx = require('../frontend/node_modules/react/jsx-runtime');
const { renderToStaticMarkup } = require('../frontend/node_modules/react-dom/server');

function setup(financialReports) {
  const context = { window: {} };
  vm.runInNewContext(fs.readFileSync('frontend/dist/api-client.js', 'utf8'), context);
  const states = [];
  let cursor = 0;
  const props = {
    react: { useState: initial => {
      const index = cursor++;
      if (states[index] === undefined) states[index] = initial;
      return [states[index], value => { states[index] = value; }];
    } }, jsx,
    stock: { symbol: 'TEST', financialReports }
  };
  const render = () => { cursor = 0; return context.window.StockAI.FinancialReports(props); };
  const html = () => renderToStaticMarkup(render());
  function find(tree, predicate) {
    if (!tree || typeof tree !== 'object') return undefined;
    if (predicate(tree)) return tree;
    const children = Array.isArray(tree.props?.children) ? tree.props.children : [tree.props?.children];
    for (const child of children.flat()) {
      const found = find(child, predicate);
      if (found) return found;
    }
  }
  function select(tab) {
    find(render(), node => node.props?.role === 'tab' && node.key === tab).props.onClick();
  }
  function control(label, value) {
    find(render(), node => node.type === 'select' && node.props['aria-label'] === label).props.onChange({ target: { value } });
  }
  return { html, select, control };
}

test('clicking each report tab renders its own snapshot values and rows', () => {
  const ui = setup({ unit: 'VND', annual: [{ period: '2025', items: {
    revenue: 70e9, total_assets: 88e9, total_equity: 44e9,
    cfo: 10e9, cfi: -12e9, cff: 0, eps: 5216
  } }] });
  assert.match(ui.html(), /Doanh thu thuần/);
  assert.match(ui.html(), /5\.216/); // EPS must not be divided by 1e9.
  assert.doesNotMatch(ui.html(), /Dự phóng|kiểm toán bởi/);
  ui.select('balance');
  assert.match(ui.html(), /Tổng tài sản/);
  assert.match(ui.html(), />88<\/td>/);
  assert.doesNotMatch(ui.html(), /Doanh thu thuần/);
  ui.select('cashflow');
  assert.match(ui.html(), /Lưu chuyển tiền thuần từ hoạt động kinh doanh/);
  assert.match(ui.html(), />-12<\/td>/);
  assert.match(ui.html(), />0<\/td>/);
  assert.match(ui.html(), />—<\/td>/);
  assert.doesNotMatch(ui.html(), /Tổng tài sản|Doanh thu thuần/);
  ui.select('income');
  assert.match(ui.html(), /Doanh thu thuần/);
});

test('derived line items, margins and same-year comparisons use the correct inputs', () => {
  const ui = setup({ unit: 'VND', annual: [
    { period: '2024', items: { revenue: 50e9, gross_profit: 10e9, net_income: 5e9 } },
    { period: '2025', items: { revenue: 70e9, gross_profit: 21e9, net_income: 7e9,
      total_assets: 88e9, current_assets: 50e9, current_liabilities: 20e9,
      short_term_debt: 10e9, long_term_debt: 3e9, cash: 4e9, cfo: 10e9, capex: -3e9 } }
  ] });
  assert.match(ui.html(), /Giá vốn hàng bán \*/);
  assert.match(ui.html(), />49<\/td>/);
  assert.match(ui.html(), />30%<\/td>/);
  assert.match(ui.html(), />\+40%<\/td>/);
  assert.match(ui.html(), />\+10 đpt<\/td>/);
  ui.select('balance');
  assert.match(ui.html(), />38<\/td>/); // Noncurrent assets.
  assert.match(ui.html(), />9<\/td>/); // Net debt.
  assert.match(ui.html(), />2,5 lần<\/td>/);
  ui.select('cashflow');
  assert.match(ui.html(), />7<\/td>/); // CFO - abs(CAPEX).
  assert.match(ui.html(), />30%<\/td>/);
});

test('quarterly mode compares with the same quarter, preserves metadata and changes units', () => {
  const ui = setup({ unit: 'VND', annual: [], quarterly: [
    { period: '2025Q2', items: { revenue: 10e9 } },
    { period: '2026Q1', items: { revenue: 19e9 } },
    { period: '2026Q2', published_at: '2026-08-14', source_id: 'quarter-source',
      published_at_estimated: true, items: { revenue: 20e9, eps: 1500 } }
  ] });
  ui.control('Kỳ báo cáo', 'quarterly');
  assert.match(ui.html(), /2026Q2 \/ 2025Q2/);
  assert.match(ui.html(), />\+100%<\/td>/);
  assert.match(ui.html(), /2026-08-14 \*/);
  assert.match(ui.html(), /quarter-source/);
  ui.control('Đơn vị', 'million');
  assert.match(ui.html(), /Triệu đồng/);
  assert.match(ui.html(), />20\.000<\/td>/);
  assert.match(ui.html(), />1\.500<\/td>/); // EPS unchanged.
});

test('bank reports display bank KPIs and correct percentage units', () => {
  const ui = setup({ unit: 'VND', is_bank: true, annual: [{ period: '2025', items: {
    net_interest_income: 20e9, nim: 0.0288, cir: 0.3204,
    customer_loans: 100e9, customer_deposits: 125e9
  } }] });
  assert.match(ui.html(), /Thu nhập lãi thuần/);
  assert.match(ui.html(), />2,88%<\/td>/);
  assert.match(ui.html(), />32,04%<\/td>/);
  assert.doesNotMatch(ui.html(), /Giá vốn hàng bán/);
  ui.select('balance');
  assert.match(ui.html(), /Cho vay khách hàng/);
  assert.match(ui.html(), />80%<\/td>/);
});

test('missing inputs never become zero and nonpositive growth bases have no percentage', () => {
  const ui = setup({ unit: 'VND', annual: [
    { period: '2024', items: { net_income: -1e9, revenue: 0 } },
    { period: '2025', items: { net_income: 1e9, revenue: 2e9 } }
  ] });
  assert.doesNotMatch(ui.html(), /NaN|Infinity|\+200%/);
  assert.match(ui.html(), /Giá vốn hàng bán \*/);
  assert.match(ui.html(), />—<\/td>/);
  ui.control('Kỳ báo cáo', 'quarterly');
  assert.match(ui.html(), /Chưa có dữ liệu/);
});

test('missing reports show an empty state for each tab, without demo data', () => {
  const ui = setup(undefined);
  for (const tab of ['income', 'balance', 'cashflow']) {
    ui.select(tab);
    assert.match(ui.html(), /Chưa có dữ liệu/);
    assert.doesNotMatch(ui.html(), /<table/);
  }
});

test('one available report never substitutes for a missing report', () => {
  const ui = setup({ unit: 'VND', annual: [{ period: '2025', items: { revenue: 1e9 } }] });
  ui.select('balance');
  assert.match(ui.html(), /Chưa có dữ liệu/);
  ui.select('cashflow');
  assert.match(ui.html(), /Chưa có dữ liệu/);
});
