export type Article={id:string;title:string;summary?:string;source:string;url?:string;published_at:string;date:string;label:'pos'|'neg'|'neutral';polarity:number;matches?:string[];tickers:string[]};
export const sentimentNames={pos:'Tích cực',neutral:'Trung tính',neg:'Tiêu cực'};
export const topicRules:[string,RegExp][]=[['Kết quả kinh doanh',/lợi nhuận|doanh thu|kqkd|báo lãi|lãi ròng/i],['AI & Công nghệ',/\bai\b|công nghệ|nvidia|cloud|chuyển đổi số/i],['Cổ tức & Cổ đông',/cổ tức|cổ đông|phát hành/i],['Giao dịch',/cổ phiếu|mua ròng|bán ròng|giao dịch/i],['Đầu tư & Hợp tác',/đầu tư|hợp tác|hợp đồng|dự án/i],['Vĩ mô',/thuế|lãi suất|tỷ giá|xuất khẩu/i]];
export function topics(a:Article){return topicRules.filter(([,rule])=>rule.test(a.title)).map(([name])=>name);}
export function windowStart(asof:string,days:number){const t=Date.parse(asof+'T00:00:00Z');return Number.isFinite(t)?days===0?'0001-01-01':new Date(t-(days-1)*86400000).toISOString().slice(0,10):'';}
export function filterArticles(items:Article[],asof:string,days:number,source='all',topic='all',query=''){
  const start=windowStart(asof,days),q=query.trim().toLocaleLowerCase('vi');
  if(!start)return [];
  return items.filter(a=>a.date>=start&&a.date<=asof&&(source==='all'||a.source===source)&&(topic==='all'||topics(a).includes(topic))&&(!q||(a.title+' '+(a.summary||'')).toLocaleLowerCase('vi').includes(q)));
}
export function distribution(items:Article[]){
  const counts={pos:0,neutral:0,neg:0};items.forEach(a=>counts[a.label]++);
  return {counts,total:items.length,balance:items.length?50+50*(counts.pos-counts.neg)/items.length:null};
}
export function timeline(items:Article[]){
  const dates=[...new Set(items.map(a=>a.date))].sort();
  return dates.map(date=>{const rows=items.filter(a=>a.date===date);const d=distribution(rows);return {date,...d,polarity:rows.reduce((s,a)=>s+a.polarity,0)/rows.length};});
}
export function aggregate(items:Article[],kind:'source'|'topic'|'ticker'){
  const groups=new Map<string,Article[]>();
  items.forEach(a=>{const keys=kind==='source'?[a.source]:kind==='topic'?topics(a):a.tickers;new Set(keys).forEach(key=>groups.set(key,[...(groups.get(key)||[]),a]));});
  return [...groups].map(([name,rows])=>({name,...distribution(rows)})).sort((a,b)=>b.total-a.total||a.name.localeCompare(b.name));
}
export function newsPriceCorrelation(items:Article[],prices:any[]){
  const close=new Map(prices.filter(r=>Number.isFinite(r.close)&&r.close>0).map(r=>[String(r.date).slice(0,10),r.close]));
  const pairs=timeline(items).filter(r=>close.has(r.date)).map(r=>[r.polarity,close.get(r.date)!] as number[]);
  if(pairs.length<5)return {value:null,count:pairs.length};
  const means=[0,1].map(i=>pairs.reduce((s,p)=>s+p[i],0)/pairs.length);
  const cov=pairs.reduce((s,p)=>s+(p[0]-means[0])*(p[1]-means[1]),0);
  const ss=[0,1].map(i=>pairs.reduce((s,p)=>s+(p[i]-means[i])**2,0));
  return {value:ss[0]>0&&ss[1]>0?Math.max(-1,Math.min(1,cov/Math.sqrt(ss[0]*ss[1]))):null,count:pairs.length};
}
