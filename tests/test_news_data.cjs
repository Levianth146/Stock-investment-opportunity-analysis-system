const {test}=require('node:test');
const assert=require('node:assert/strict');
const {filterArticles,distribution,timeline,aggregate,newsPriceCorrelation,windowStart}=require('../frontend/src/newsData.ts');
const make=(date,label='neutral',extra={})=>({id:date,title:'FPT doanh thu tăng',date,published_at:date,source:'A',label,polarity:label==='pos'?1:label==='neg'?-1:0,tickers:['FPT'],...extra});
test('calendar window includes snapshot day and rejects future news',()=>{
  assert.equal(windowStart('2026-10-08',7),'2026-10-02');
  assert.deepEqual(filterArticles([make('2026-10-01'),make('2026-10-02'),make('2026-10-08'),make('2026-10-09')],'2026-10-08',7).map(a=>a.date),['2026-10-02','2026-10-08']);
  assert.deepEqual(filterArticles([make('2026-10-08')],'invalid',7),[]);
  assert.equal(filterArticles([make('2001-01-01')],'2026-10-08',0).length,1);
});
test('source, topic, and text filters combine rather than replace each other',()=>{
  const rows=[make('2026-10-08'),make('2026-10-07','neg',{source:'B'}),make('2026-10-06','neutral',{title:'FPT ra mắt công nghệ AI'})];
  assert.equal(filterArticles(rows,'2026-10-08',7,'A','Kết quả kinh doanh','fpt').length,1);
  assert.equal(filterArticles(rows,'2026-10-08',7,'B','AI & Công nghệ').length,0);
});
test('balance and proportions preserve neutral and empty distinctions',()=>{
  assert.equal(distribution([]).balance,null);
  assert.equal(distribution([make('2026-10-08')]).balance,50);
  assert.equal(distribution([make('2026-10-08','pos'),make('2026-10-07','neutral')]).balance,75);
});
test('timeline uses observed dates without inventing daily observations',()=>{
  const rows=timeline([make('2026-10-08','neg'),make('2026-10-06','pos'),make('2026-10-08','pos')]);
  assert.deepEqual(rows.map(r=>r.date),['2026-10-06','2026-10-08']);
  assert.equal(rows[1].total,2);assert.equal(rows[1].polarity,0);
});
test('grouping counts each mentioned ticker once per article',()=>{
  assert.equal(aggregate([make('2026-10-08','pos',{tickers:['FPT','FPT']})],'ticker')[0].total,1);
  assert.equal(aggregate([make('2026-10-08')],'source')[0].name,'A');
});
test('correlation needs five common dates and nonconstant series',()=>{
  const rows=Array.from({length:6},(_,i)=>make(`2026-10-0${i+1}`,'pos',{polarity:i/10}));
  const prices=rows.map((r,i)=>({date:r.date,close:(i+1)*1000}));
  assert.equal(newsPriceCorrelation(rows,prices).value,1);
  assert.equal(newsPriceCorrelation(rows,prices.slice(0,4)).value,null);
  assert.equal(newsPriceCorrelation(rows,prices.map(r=>({...r,close:1000}))).value,null);
});
