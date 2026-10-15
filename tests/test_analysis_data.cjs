// Node 24+ supports importing the erasable TypeScript presentation helpers directly.
const {test,before}=require('node:test');
const assert=require('node:assert/strict');
let model;
before(async()=>{model=await import('../frontend/src/analysisData.ts');});
const data=()=>({ticker:'AAA',as_of:'2026-10-08',financial_reports:{unit:'VND',annual:[
  {period:'2024',published_at:'2025-03-31',items:{revenue:100e9,net_income:10e9,gross_profit:30e9,total_assets:80e9,cfo:12e9,eps:1000}},
  {period:'2025',published_at:'2026-03-31',items:{revenue:120e9,net_income:12e9,gross_profit:42e9,total_assets:120e9,cfo:-3e9,eps:1250}},
  {period:'2026',published_at:'2027-03-31',items:{revenue:999e9,net_income:999e9}},
]},modules:{m2:{status:'ok',metrics:{roe:{value:.2,unit:'ratio'}}}}});

test('annual cards use published years, correct units and average assets, without inventing TTM',()=>{
  const result=model.financialModel(data());
  assert.deepEqual(result.annual.map(r=>r.period),['2024','2025']);
  assert.equal(result.latest.items.revenue/result.unit.divisor,120);
  assert.equal(result.unit.label,'tỷ đồng');
  assert.ok(Math.abs(result.revenueGrowth-20)<1e-9);
  assert.equal(result.epsGrowth,25);
  assert.equal(result.roa,.12);
  assert.equal(result.roe,.2);
  assert.ok(Math.abs(result.marginChange-5)<1e-9);
});
test('missing and nonpositive comparison bases never turn into zero or fabricated growth',()=>{
  const input=data();input.financial_reports.annual[0].items.revenue=0;
  input.financial_reports.annual[0].items.eps=-10;
  delete input.financial_reports.annual[1].items.net_income;
  const result=model.financialModel(input);
  assert.equal(result.revenueGrowth,null);
  assert.equal(result.epsGrowth,null);
  assert.equal(result.roa,null);
  assert.equal(model.growth(10,-5),null);
  assert.equal(model.growth(0,10),-100);
});
test('a gap between reporting years is not described as year-over-year growth',()=>{
  const input=data();input.financial_reports.annual[0].period='2023';
  const result=model.financialModel(input);
  assert.equal(result.previous,null);assert.equal(result.revenueGrowth,null);assert.equal(result.roa,null);
});
test('empty financials stay empty; bank income has its own label',()=>{
  const empty=model.financialModel({financial_reports:{annual:[],unit:'VND'}});
  assert.equal(empty.annual.length,0);assert.equal(empty.grossMargin,null);
  const input=data();input.financial_reports.is_bank=true;
  input.financial_reports.annual[1].items.operating_income=50e9;
  const bank=model.financialModel(input);
  assert.equal(bank.revenueKey,'operating_income');assert.equal(bank.revenueLabel,'Thu nhập hoạt động');
});
test('CSV has the same annual source values as the UI and omits future reports',()=>{
  const csv=model.exportStatements(data());
  assert.ok(csv.startsWith('\uFEFF'));
  assert.match(csv,/"2024","2025"/);
  assert.match(csv,/"Doanh thu thuần","100","120"/);
  assert.doesNotMatch(csv,/"2026"|999|TTM/);
  assert.match(csv,/"Lưu chuyển tiền tệ"/);
});
test('technical signals retain zero RSI and ignore failed modules and future price ranges',()=>{
  const input={as_of:'2026-10-08',modules:{m3:{status:'partial',metrics:{close:{value:10},ma20:{value:12},ma50:{value:15},rsi14:{value:0},macd:{value:-2},macd_signal:{value:-1}}}},price_history:[
    {date:'2026-10-07',low:8,high:13},{date:'2026-10-08',low:9,high:12},{date:'2026-10-09',low:1,high:999},
  ]};
  const tech=model.technicalModel(input);
  assert.equal(tech.rsi,0);assert.equal(tech.rsiLabel,'Vùng quá bán');
  assert.equal(tech.trend,'down');assert.equal(tech.macdDirection,'below');
  assert.equal(tech.low,8);assert.equal(tech.high,13);assert.equal(tech.rangeSessions,2);
  input.modules.m3.status='error';assert.equal(model.technicalModel(input).close,null);
});
