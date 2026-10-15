export type Opportunity={ticker:string;name:string;sector:string;exchange:string;score:number;rating:string;scores:Record<string,number|null>;price:number|null;reference_price:number|null;upside_pct:number|null;market_cap:number|null;signals:Record<string,any>;ranked:boolean;quality_gate?:any;change:number|null;price_date?:string;volume:number|null;price_trend?:{date:string;close:number}[]};
export const numeric=(v:any):v is number=>typeof v==='number'&&Number.isFinite(v);
export const normalize=(s:any)=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/đ/g,'d').replace(/Đ/g,'D').toLowerCase();
export function riskBand(v:any){return !numeric(v)?'unknown':v<33?'low':v<67?'medium':'high';}
export const riskNames={low:'Thấp',medium:'Trung bình',high:'Cao',unknown:'Chưa có'};
export const defaults={exchange:'all',sector:'all',cap:'all',score:0,risk:'all',upside:'',query:'',ratings:[] as string[],fullOnly:false,minVolume:'',strategy:'all'};
export type Filters=typeof defaults;
export function joinOpportunities(rows:any[],catalog:any[]):Opportunity[]{
  const companies=new Map(catalog.map(c=>[c.symbol,c]));
  return rows.filter(r=>r.ranked===true&&numeric(r.score)&&r.quality_gate?.scored!==false).map(r=>{const c=companies.get(r.ticker);return {...r,name:c?.name||r.name||r.ticker,sector:c?.sector||r.sector||'Chưa có ngành',exchange:normalizeExchange(c?.exchange||r.exchange),price:numeric(c?.current_price)?c.current_price:numeric(r.price)?r.price:null,change:numeric(c?.price_change_percent)?c.price_change_percent:null,price_date:c?.price_date,volume:numeric(c?.volume)?c.volume:null};});
}
export function normalizeExchange(s:any){const text=String(s||'').toUpperCase();return text==='HSX'?'HOSE':text==='UPCOM'?'UPCoM':text;}
export function filterOpportunities(rows:Opportunity[],f:Filters){return rows.filter(r=>{
  if(f.exchange!=='all'&&r.exchange!==f.exchange||f.sector!=='all'&&r.sector!==f.sector)return false;
  if(r.score<f.score||f.risk!=='all'&&riskBand(r.scores?.R)!==f.risk)return false;
  if(f.upside!==''&&(!numeric(r.upside_pct)||r.upside_pct<Number(f.upside)))return false;
  if(f.minVolume!==''&&(!numeric(r.volume)||r.volume<Number(f.minVolume)))return false;
  if(f.ratings.length&&!f.ratings.includes(r.rating)||f.fullOnly&&r.quality_gate?.tier!=='full')return false;
  if(f.cap!=='all'){if(!numeric(r.market_cap))return false;if(f.cap==='small'&&r.market_cap>=2e12||f.cap==='mid'&&(r.market_cap<2e12||r.market_cap>=1e13)||f.cap==='large'&&r.market_cap<1e13)return false;}
  const moduleKey={quality:'F',momentum:'T',value:'V'}[f.strategy];if(moduleKey&&(!numeric(r.scores?.[moduleKey])||r.scores[moduleKey]!<65))return false;
  return !f.query||normalize(`${r.ticker} ${r.name} ${r.sector}`).includes(normalize(f.query).trim());
});}
export function sortOpportunities(rows:Opportunity[],key:string){return [...rows].sort((a,b)=>{
  const value=(r:Opportunity)=>key==='risk'?r.scores?.R:key==='upside'?r.upside_pct:key==='cap'?r.market_cap:r.score;
  const x=value(a),y=value(b);return !numeric(x)?!numeric(y)?a.ticker.localeCompare(b.ticker):1:!numeric(y)?-1:(key==='risk'?x-y:y-x)||a.ticker.localeCompare(b.ticker);
});}
export function mean(values:any[]){const actual=values.filter(numeric);return actual.length?actual.reduce((s,v)=>s+v,0)/actual.length:null;}
export function countsBy(rows:Opportunity[],field:'sector'|'rating'){const groups=new Map<string,number>();rows.forEach(r=>groups.set(r[field],(groups.get(r[field])||0)+1));return [...groups].map(([name,count])=>({name,count})).sort((a,b)=>b.count-a.count||a.name.localeCompare(b.name));}
export function sectorLeaders(rows:Opportunity[]){const counts=new Map<string,number>();return sortOpportunities(rows,'score').filter(r=>{const n=counts.get(r.sector)||0;counts.set(r.sector,n+1);return n<3;});}
export function opportunityCSV(rows:Opportunity[],asof:string){const quote=(v:any)=>'"'+String(v??'').replace(/"/g,'""')+'"';const lines=[['Snapshot','Mã','Tên doanh nghiệp','Sàn','Ngành','Điểm','Khuyến nghị','Giá đóng cửa VND','Ngày giá','Thay đổi phiên %','Giá mục tiêu cơ sở VND','Chênh lệch mục tiêu %','Điểm rủi ro','Vốn hóa VND','Chất lượng dữ liệu'],...rows.map(r=>[asof,r.ticker,r.name,r.exchange,r.sector,r.score,r.rating,r.price,r.price_date,r.change,r.reference_price,r.upside_pct,r.scores?.R,r.market_cap,r.quality_gate?.tier])];return '\ufeff'+lines.map(row=>row.map(quote).join(',')).join('\r\n');}
