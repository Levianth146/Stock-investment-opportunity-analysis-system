const {test,before}=require('node:test');
const assert=require('node:assert/strict');
let helpers;
before(async()=>{helpers=await import('../frontend/src/valuationRiskData.ts');});
function data(){return {ticker:'AAA',as_of:'2026-10-08',current_price:10000,company:{shares_outstanding:10e6},quality_gate:{scored:true},target:{base:12000,bear:10000,bull:14000,method:'relative_multiples_pe_pb'},
  financial_reports:{unit:'VND',annual:[{period:'2024',items:{eps:1000}},{period:'2025',items:{eps:2000,ebitda:10e9,short_term_debt:15e9,long_term_debt:5e9,cash:5e9}}]},
  modules:{m4:{status:'ok',flags:[],target:{base:999999},metrics:{pe:{value:10},pb:{value:2},eps_used:{value:5000,note:'ttm_ni'},book_per_share:{value:20000},sector_median_pe:{value:12},sector_median_pb:{value:2.2}}},m6:{status:'partial',score:0,metrics:{beta:{value:0},historical_var_95:{value:0},volatility_risk_subscore:{value:0}}}},
  price_history:[{date:'2026-10-07',close:100,volume:0},{date:'2026-10-08',close:100,volume:10}]};}

test('published target is kept separate from PE/PB references and EV/PEG supplementary ratios',()=>{
  const result=helpers.valuationModel(data());
  assert.equal(result.target.base,12000);assert.equal(result.peReference,60000);assert.equal(result.pbReference,44000);
  assert.ok(Math.abs(result.upside-20)<1e-9);assert.equal(result.evEbitda,11.5);assert.equal(result.peg,.1);assert.equal(result.epsBasis,'TTM');
});
test('quality gate suppresses published/reference targets even if raw M4 still has one',()=>{
  const input=data();input.quality_gate.scored=false;
  const result=helpers.valuationModel(input);
  assert.equal(result.target,null);assert.equal(result.peReference,null);assert.equal(result.pbReference,null);assert.equal(result.upside,null);
  assert.equal(result.pe,10);
  const csv=helpers.valuationCSV(input);assert.doesNotMatch(csv,/999999|12000/);
});
test('a module target is never promoted when M7 has no published target',()=>{
  const input=data();input.target=null;
  assert.equal(helpers.valuationModel(input).target,null);
});
test('market fallback is labeled correctly and a dropped PB leg cannot supply a reference target',()=>{
  const input=data();input.modules.m4.flags=['m4_sector_fallback','m4_pb_leg_dropped'];
  const result=helpers.valuationModel(input);assert.equal(result.scope,'thị trường');assert.equal(result.pbReference,null);
});
test('EV/EBITDA requires an interpretable currency unit and complete balance inputs; not used for banks',()=>{
  const input=data();input.financial_reports.unit='unknown';assert.equal(helpers.valuationModel(input).evEbitda,null);
  input.financial_reports.unit='VND';delete input.financial_reports.annual[1].items.cash;assert.equal(helpers.valuationModel(input).evEbitda,null);
  input.financial_reports.is_bank=true;input.financial_reports.annual[1].items.cash=0;assert.equal(helpers.valuationModel(input).evEbitda,null);
});
test('PEG has no value for flat or negative EPS growth',()=>{
  const input=data();input.financial_reports.annual[1].items.eps=1000;assert.equal(helpers.valuationModel(input).peg,null);
  input.financial_reports.annual[1].items.eps=-2000;assert.equal(helpers.valuationModel(input).peg,null);
});
test('risk preserves legitimate zeros and does not equate missing volume with zero turnover',()=>{
  const input=data();let risk=helpers.riskModel(input);
  assert.equal(risk.score,0);assert.equal(risk.beta,0);assert.equal(risk.var95,0);assert.equal(risk.axes[0].value,0);
  assert.equal(risk.axes[1].value,null);assert.equal(risk.liquid,500);
  delete input.price_history[1].volume;risk=helpers.riskModel(input);assert.equal(risk.liquid,null);
});
test('comparison returns use common dates and one shared base, exclude missing/future values',()=>{
  const prices={ohlcv:[{time:'2026-10-01',close:10},{time:'2026-10-03',close:20},{time:'2026-10-06',close:15},{time:'2026-10-09',close:999}],index:{series:[{time:'2026-10-01',close:100},{time:'2026-10-06',close:200},{time:'2026-10-09',close:1}]}};
  const rows=helpers.alignedReturns(prices,'2026-10-08');
  assert.deepEqual(rows.map(row=>row.date),['2026-10-01','2026-10-06']);assert.equal(rows[0].stock,0);assert.equal(rows[0].index,0);assert.equal(rows[1].stock,50);assert.equal(rows[1].index,100);
  assert.deepEqual(helpers.alignedReturns({ohlcv:[],index:null},'2026-10-08'),[]);
});
