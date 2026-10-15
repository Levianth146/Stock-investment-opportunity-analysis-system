const {test}=require('node:test');const assert=require('node:assert/strict');
const {defaults,joinOpportunities,filterOpportunities,sortOpportunities,mean,riskBand,countsBy,sectorLeaders,opportunityCSV}=require('../frontend/src/opportunityData.ts');
const row=(ticker,extra={})=>({ticker,name:ticker,sector:'Banks',exchange:'HOSE',score:70,rating:'Mua',scores:{F:70,T:60,V:75,R:30},price:10000,reference_price:12000,upside_pct:20,market_cap:2e12,signals:{},ranked:true,quality_gate:{tier:'full',scored:true},change:0,volume:100000,...extra});
test('joins complete rankings with catalog, normalizes exchanges and excludes gated stocks',()=>{
  const result=joinOpportunities([row('ABC'),row('BAD',{ranked:false}),row('NO',{quality_gate:{scored:false}})], [{symbol:'ABC',name:'Công ty Á Châu',exchange:'HSX',current_price:11000,price_change_percent:0,volume:0,price_date:'2026-10-08'}]);
  assert.equal(result.length,1);assert.equal(result[0].exchange,'HOSE');assert.equal(result[0].price,11000);assert.equal(result[0].change,0);assert.equal(result[0].volume,0);
});
test('all defaults retain negative/missing upside and all scored rows',()=>{
  const rows=[row('A',{upside_pct:-20}),row('B',{upside_pct:null}),row('C',{scores:{R:null}})];
  assert.equal(filterOpportunities(rows,defaults).length,3);assert.equal(mean([null,0,50,NaN]),25);assert.equal(mean([null]),null);
});
test('exchange, sector, score and accent-insensitive search combine',()=>{
  const rows=[row('ABC',{name:'Ngân hàng Á Châu'}),row('DEF',{exchange:'HNX'}),row('GHI',{score:40})];
  assert.equal(filterOpportunities(rows,{...defaults,exchange:'HOSE',score:65,query:'a chau'}).length,1);
  assert.equal(filterOpportunities(rows,{...defaults,sector:'Technology'}).length,0);
});
test('capital bands have explicit boundaries and omit missing capital when restricted',()=>{
  const rows=[row('SMALL',{market_cap:2e12-1}),row('MID',{market_cap:2e12}),row('BIG',{market_cap:1e13}),row('NONE',{market_cap:null})];
  for(const [cap,ticker] of [['small','SMALL'],['mid','MID'],['large','BIG']])assert.deepEqual(filterOpportunities(rows,{...defaults,cap}).map(r=>r.ticker),[ticker]);
});
test('risk, quality, strategy, upside and volume do not turn missing inputs into zero',()=>{
  assert.equal(riskBand(null),'unknown');assert.equal(riskBand(0),'low');assert.equal(riskBand(33),'medium');assert.equal(riskBand(67),'high');
  const rows=[row('A'),row('B',{scores:{R:null},volume:null,upside_pct:null,quality_gate:{tier:'limited'}})];
  for(const extra of [{risk:'low'},{fullOnly:true},{strategy:'quality'},{minVolume:'0'},{upside:'0'},{ratings:['Mua']}]){const found=filterOpportunities(rows,{...defaults,...extra});assert(found.some(r=>r.ticker==='A'));if(!extra.ratings)assert(!found.some(r=>r.ticker==='B'));}
});
test('sort is stable by ticker on ties, risk asc, missing values last',()=>{
  const rows=[row('B',{upside_pct:null}),row('A'),row('C',{upside_pct:50,scores:{R:0}})];
  assert.deepEqual(sortOpportunities(rows,'upside').map(r=>r.ticker),['C','A','B']);
  assert.equal(sortOpportunities(rows,'risk')[0].ticker,'C');
});
test('group stats and top three per sector are derived from filtered stocks',()=>{
  const rows=[row('A'),row('B'),row('C'),row('D'),row('E',{sector:'Technology'})];
  assert.equal(countsBy(rows,'sector')[0].count,4);assert.equal(sectorLeaders(rows).length,4);
});
test('CSV preserves source values and explicitly uses target difference rather than expected return',()=>{
  const csv=opportunityCSV([row('ABC',{name:'Tên "ABC"'})],'2026-10-08');
  assert(csv.startsWith('\ufeff'));assert(csv.includes('Tên ""ABC""'));assert(csv.includes('"12000","20","30"'));assert(!csv.includes('12 tháng'));
});
