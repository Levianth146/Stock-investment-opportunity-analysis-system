const {test}=require('node:test');const assert=require('node:assert/strict');
const {cleanPosition,watchRows,holdingSummary,watchAlerts,portfolioHistory,watchlistCSV}=require('../frontend/src/watchlistData.ts');
const catalog=[{symbol:'FPT',name:'FPT',sector:'Technology',current_price:120,price_change:10,price_change_percent:9.09,price_date:'2026-10-08'},{symbol:'ABR',current_price:80,price_change:-5,price_date:'2026-10-08',quality_tier:'insufficient'}];
test('watchlist includes unranked and unknown stocks without demo data or raw target',()=>{
  const rows=watchRows(['FPT','ABR','ZZZ','FPT'],catalog,[{ticker:'ABR',ranked:false,reference_price:999}],{});
  assert.equal(rows.length,3);assert.equal(rows[1].price,80);assert.equal(rows[1].target,null);assert.equal(rows[1].rating,'Chưa xếp hạng');assert.equal(rows[2].price,null);assert.equal(rows[2].name,'ZZZ');
});
test('holdings only use valid entered quantities/cost, missing never becomes zero',()=>{
  assert.equal(cleanPosition({quantity:-1,cost:0}).quantity,null);assert.equal(cleanPosition({quantity:1.5}).quantity,null);
  const rows=watchRows(['FPT','ABR'],catalog,[],{FPT:{quantity:10,cost:100}}),summary=holdingSummary(rows);
  assert.equal(summary.held,1);assert.equal(summary.value,1200);assert.equal(summary.pnl,200);assert.equal(summary.pnlPct,20);assert.equal(summary.sessionChange,100);
  assert.equal(rows[1].value,null);assert.equal(holdingSummary(watchRows(['FPT'],catalog,[],{})).value,null);
});
test('partial prices/costs do not masquerade as complete portfolio totals',()=>{
  const rows=watchRows(['FPT','ZZZ'],catalog,[],{FPT:{quantity:10,cost:100},ZZZ:{quantity:10}}),s=holdingSummary(rows);
  assert.equal(s.value,null);assert.equal(s.pnl,null);assert.equal(s.basis,null);
  const stale=watchRows(['FPT','ABR'],catalog.map(r=>r.symbol==='ABR'?{...r,price_date:'2026-10-07'}:r),[],{FPT:{quantity:10},ABR:{quantity:10}});
  assert.equal(holdingSummary(stale).sessionChange,null);
});
test('alerts compare actual snapshot price against user thresholds only',()=>{
  const rows=watchRows(['FPT','ABR','ZZZ'],catalog,[],{FPT:{above:120},ABR:{below:90},ZZZ:{above:1}});
  assert.deepEqual(watchAlerts(rows).map(r=>r.type),['above','below']);
});
test('history uses shared dates and fixed quantities, contributions sum to portfolio change',()=>{
  const rows=watchRows(['FPT','ABR'],catalog,[],{FPT:{quantity:2},ABR:{quantity:1}});
  const cache={FPT:{asof:'2026-10-08',ohlcv:[{time:'2026-10-01',close:100},{time:'2026-10-02',close:110},{time:'2026-10-03',close:120},{time:'2026-10-09',close:999}],index:{series:[{time:'2026-10-01',close:1000},{time:'2026-10-03',close:1100}]}},ABR:{asof:'2026-10-08',ohlcv:[{time:'2026-10-01',close:100},{time:'2026-10-03',close:90}]}};
  const h=portfolioHistory(rows,cache,'2026-10-08');assert.equal(h.rows.length,2);assert.equal(h.rows[0].portfolio,0);assert(Math.abs(h.rows.at(-1).portfolio-10)<1e-10);assert(Math.abs(h.rows.at(-1).index-10)<1e-10);assert(Math.abs(h.contributions.reduce((s,r)=>s+r.value,0)-10)<1e-10);assert.equal(h.volatility,null);assert.equal(h.sharpe,null);
  assert.deepEqual(portfolioHistory(rows,{FPT:cache.FPT},'2026-10-08').missing,['ABR']);
  assert.equal(portfolioHistory(rows,cache,'2026-10-09').rows.length,0);
});
test('volatility and Sharpe require enough daily observations, constant series has no Sharpe',()=>{
  const rows=watchRows(['FPT'],catalog,[],{FPT:{quantity:1}});
  const data={asof:'2026-10-08',ohlcv:Array.from({length:22},(_,i)=>({time:`2026-09-${String(i+1).padStart(2,'0')}`,close:100}))};
  const h=portfolioHistory(rows,{FPT:data},'2026-10-08');assert.equal(h.volatility,0);assert.equal(h.sharpe,null);assert.equal(h.drawdown,0);
});
test('CSV preserves user holdings, alerts, missing data and quoted notes',()=>{
  const csv=watchlistCSV(watchRows(['FPT','ABR'],catalog,[],{FPT:{quantity:10,cost:100,above:130,note:'Ghi chú "mới"'}}),'2026-10-08');
  assert(csv.startsWith('\ufeff'));assert(csv.includes('Ghi chú ""mới""'));assert(csv.includes('"100","10","1200","200"'));assert(csv.includes('Chưa xếp hạng'));
});
