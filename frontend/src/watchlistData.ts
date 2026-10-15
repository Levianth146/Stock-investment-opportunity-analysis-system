import {numeric} from './opportunityData.ts';
export type Position={quantity:number|null;cost:number|null;above:number|null;below:number|null;note:string};
export const emptyPosition:Position={quantity:null,cost:null,above:null,below:null,note:''};
export function cleanPosition(raw:any):Position {
  const positive=(v:any)=>numeric(v)&&v>0?v:null;
  return {quantity:numeric(raw?.quantity)&&Number.isInteger(raw.quantity)&&raw.quantity>0?raw.quantity:null,cost:positive(raw?.cost),above:positive(raw?.above),below:positive(raw?.below),note:typeof raw?.note==='string'?raw.note.slice(0,1000):''};
}
export function watchRows(favorites:string[],catalog:any[],ranking:any[],positions:Record<string,Position>){
  const companies=new Map(catalog.map(r=>[r.symbol,r])),scores=new Map(ranking.filter(r=>r.ranked===true&&r.quality_gate?.scored!==false).map(r=>[r.ticker,r]));
  return [...new Set(favorites)].map(ticker=>{const c=companies.get(ticker),r=scores.get(ticker),position=cleanPosition(positions[ticker]);
    const price=numeric(c?.current_price)&&c.current_price>0?c.current_price:null,quantity=position.quantity,cost=position.cost;
    const value=quantity!==null&&price!==null?quantity*price:null,basis=quantity!==null&&cost!==null?quantity*cost:null,pnl=value!==null&&basis!==null?value-basis:null;
    return {ticker,name:c?.name||r?.name||ticker,sector:c?.sector||r?.sector||'Chưa có ngành',exchange:c?.exchange||r?.exchange||'—',price,date:c?.price_date,change:numeric(c?.price_change)?c.price_change:null,changePct:numeric(c?.price_change_percent)?c.price_change_percent:null,score:r?.score??null,risk:r?.scores?.R??null,rating:r?.rating||'Chưa xếp hạng',target:numeric(r?.reference_price)&&r.reference_price>0?r.reference_price:null,quality:c?.quality_tier||r?.quality_gate?.tier,position,value,basis,pnl,pnlPct:pnl!==null&&basis!==null&&basis>0?pnl/basis*100:null};
  });
}
export type WatchRow=ReturnType<typeof watchRows>[number];
export function holdingSummary(rows:WatchRow[]){
  const held=rows.filter(r=>r.position.quantity!==null),priced=held.filter(r=>r.value!==null),costed=held.filter(r=>r.basis!==null),sameDate=new Set(held.map(r=>r.date)).size===1;
  const value=held.length&&priced.length===held.length?priced.reduce((s,r)=>s+r.value!,0):null,basis=held.length&&costed.length===held.length?costed.reduce((s,r)=>s+r.basis!,0):null;
  const pnl=value!==null&&basis!==null?value-basis:null;
  const sessionChange=held.length&&sameDate&&held.every(r=>r.change!==null&&r.value!==null)?held.reduce((s,r)=>s+r.position.quantity!*r.change!,0):null;
  return {held:held.length,priced:priced.length,costed:costed.length,value,basis,pnl,pnlPct:pnl!==null&&basis!==null&&basis>0?pnl/basis*100:null,sessionChange,sameDate};
}
export function watchAlerts(rows:WatchRow[]){return rows.flatMap(r=>{if(r.price===null)return [];const events:{ticker:string;type:string;text:string;price:number;threshold:number}[]=[];
  if(r.position.above!==null&&r.price>=r.position.above)events.push({ticker:r.ticker,type:'above',text:'Giá đạt hoặc vượt ngưỡng trên',price:r.price,threshold:r.position.above});
  if(r.position.below!==null&&r.price<=r.position.below)events.push({ticker:r.ticker,type:'below',text:'Giá chạm hoặc dưới ngưỡng dưới',price:r.price,threshold:r.position.below});
  return events;
});}
export function portfolioHistory(rows:WatchRow[],cache:Record<string,any>,asof:string,limit=126){
  const held=rows.filter(r=>r.position.quantity!==null),missing=held.filter(r=>cache[r.ticker]?.asof!==asof||!Array.isArray(cache[r.ticker]?.ohlcv)).map(r=>r.ticker);
  if(!held.length||missing.length)return {rows:[],contributions:[],volatility:null,sharpe:null,drawdown:null,missing};
  const valid=(r:any)=>r&&typeof r.time==='string'&&r.time.slice(0,10)<=asof&&numeric(r.close)&&r.close>0;
  const maps=held.map(r=>new Map<string,number>(cache[r.ticker].ohlcv.filter(valid).map((p:any)=>[p.time.slice(0,10),p.close])));
  const days=[...maps[0].keys()].filter(day=>maps.every(m=>m.has(day))).sort().slice(-limit);
  if(days.length<2)return {rows:[],contributions:[],volatility:null,sharpe:null,drawdown:null,missing};
  const indexMap=new Map<string,number>((cache[held[0].ticker]?.index?.series||[]).filter(valid).map((p:any)=>[p.time.slice(0,10),p.close]));
  const firstValue=held.reduce((s,r,i)=>s+maps[i].get(days[0])!*r.position.quantity!,0),firstIndex=indexMap.get(days[0]);
  const series=days.map(day=>{const value=held.reduce((s,r,i)=>s+maps[i].get(day)!*r.position.quantity!,0),idx=indexMap.get(day);return {date:day,value,portfolio:(value/firstValue-1)*100,index:idx&&firstIndex?(idx/firstIndex-1)*100:null};});
  const returns=series.slice(1).map((r,i)=>r.value/series[i].value-1),avg=returns.reduce((s,v)=>s+v,0)/returns.length;
  const std=returns.length>=20?Math.sqrt(returns.reduce((s,v)=>s+(v-avg)**2,0)/(returns.length-1)):null;
  let peak=series[0].value,drawdown=0;series.forEach(r=>{peak=Math.max(peak,r.value);drawdown=Math.min(drawdown,(r.value/peak-1)*100);});
  const contributions=held.map((r,i)=>({ticker:r.ticker,value:(maps[i].get(days.at(-1)!)!-maps[i].get(days[0])!)*r.position.quantity!/firstValue*100})).sort((a,b)=>b.value-a.value);
  return {rows:series,contributions,volatility:std===null?null:std*Math.sqrt(252)*100,sharpe:std!==null&&std>0?avg/std*Math.sqrt(252):null,drawdown,missing};
}
export function watchlistCSV(rows:WatchRow[],asof:string){const quote=(v:any)=>'"'+String(v??'').replace(/"/g,'""')+'"';return '\ufeff'+[['Snapshot','Mã','Tên doanh nghiệp','Ngành','Ngày giá','Giá VND','Thay đổi phiên %','Giá vốn VND','Số lượng','Giá trị VND','Lãi/lỗ VND','Lãi/lỗ %','Mục tiêu VND','Khuyến nghị','Ngưỡng trên','Ngưỡng dưới','Ghi chú'],...rows.map(r=>[asof,r.ticker,r.name,r.sector,r.date,r.price,r.changePct,r.position.cost,r.position.quantity,r.value,r.pnl,r.pnlPct,r.target,r.rating,r.position.above,r.position.below,r.position.note])].map(row=>row.map(quote).join(',')).join('\r\n');}
