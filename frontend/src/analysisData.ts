// Presentation calculations from published snapshot reports. Missing values stay null.
export const finite=(v:any):v is number=>typeof v==='number'&&Number.isFinite(v);
export const numberText=(v:any,digits=2)=>finite(v)?v.toLocaleString('vi-VN',{maximumFractionDigits:digits}):'—';
export function metric(data:any,module:string,key:string){
  const result=data?.modules?.[module];
  return ['ok','partial'].includes(result?.status)&&finite(result.metrics?.[key]?.value)?result.metrics[key].value:null;
}
export function growth(current:any,previous:any){return finite(current)&&finite(previous)&&previous>0?(current/previous-1)*100:null;}
export function ratio(a:any,b:any){return finite(a)&&finite(b)&&b>0?a/b:null;}
export function monetaryUnit(unit:string){
  if(unit==='VND')return {divisor:1e9,label:'tỷ đồng'};
  if(['VND_billions','VND_billion'].includes(unit))return {divisor:1,label:'tỷ đồng'};
  if(['VND_millions','VND_million'].includes(unit))return {divisor:1000,label:'tỷ đồng'};
  return {divisor:1,label:unit||'đơn vị nguồn'};
}
export function financialModel(data:any){
  const reports=data?.financial_reports;
  const annual=(reports?.annual||[]).filter((r:any)=>/^\d{4}$/.test(r.period)&&(!r.published_at||!data.as_of||r.published_at.slice(0,10)<=data.as_of)).sort((a:any,b:any)=>Number(a.period)-Number(b.period));
  const latest=annual.at(-1),previous=annual.at(-2);
  const previousYear=previous&&Number(previous.period)===Number(latest.period)-1?previous:null;
  const items=latest?.items||{},prior=previousYear?.items||{};
  const isBank=!!reports?.is_bank;
  const revenueKey=isBank&&finite(items.operating_income)?'operating_income':isBank&&finite(items.net_interest_income)?'net_interest_income':'revenue';
  const revenueLabel=revenueKey==='operating_income'?'Thu nhập hoạt động':revenueKey==='net_interest_income'?'Thu nhập lãi thuần':'Doanh thu thuần';
  const grossMargin=ratio(items.gross_profit,items.revenue),previousMargin=ratio(prior.gross_profit,prior.revenue);
  const avgAssets=finite(items.total_assets)&&finite(prior.total_assets)?(items.total_assets+prior.total_assets)/2:null;
  return {annual,latest,previous:previousYear,items,prior,isBank,revenueKey,revenueLabel,unit:monetaryUnit(reports?.unit),
    revenueGrowth:growth(items[revenueKey],prior[revenueKey]),profitGrowth:growth(items.net_income,prior.net_income),
    roe:metric(data,'m2','roe'),roa:ratio(items.net_income,avgAssets),grossMargin,
    marginChange:grossMargin!==null&&previousMargin!==null?(grossMargin-previousMargin)*100:null,
    epsGrowth:growth(items.eps,prior.eps),cfoGrowth:growth(items.cfo,prior.cfo),
  };
}
export function statementFields(statement:string,revenueLabel='Doanh thu thuần',revenueKey='revenue'){
  if(statement==='balance')return [['total_assets','Tổng tài sản'],['total_equity','Vốn chủ sở hữu'],['total_liabilities','Tổng nợ phải trả'],['cash','Tiền và tương đương tiền']];
  if(statement==='cashflow')return [['cfo','Dòng tiền hoạt động kinh doanh'],['cfi','Dòng tiền đầu tư'],['cff','Dòng tiền tài chính'],['capex','Chi đầu tư tài sản cố định']];
  return [[revenueKey,revenueLabel],['net_income','Lợi nhuận sau thuế'],['gross_profit','Lợi nhuận gộp'],['ebit','Lợi nhuận trước lãi vay và thuế']];
}
export function exportStatements(data:any){
  const model=financialModel(data);
  const lines:any[][]=[['Mã',data?.ticker||''],['Snapshot',data?.as_of||''],['Đơn vị',model.unit.label],['Báo cáo','Chỉ tiêu',...model.annual.map((r:any)=>r.period)]];
  for(const [statement,title] of [['income','Kết quả kinh doanh'],['balance','Bảng cân đối'],['cashflow','Lưu chuyển tiền tệ']]){
    for(const [key,label] of statementFields(statement,model.revenueLabel,model.revenueKey))lines.push([title,label,...model.annual.map((r:any)=>finite(r.items?.[key])?r.items[key]/model.unit.divisor:'')]);
  }
  return '\uFEFF'+lines.map(row=>row.map(value=>`"${String(value).replace(/"/g,'""')}"`).join(',')).join('\r\n');
}
export function technicalModel(data:any){
  const close=metric(data,'m3','close'),ma20=metric(data,'m3','ma20'),ma50=metric(data,'m3','ma50');
  const macd=metric(data,'m3','macd'),signal=metric(data,'m3','macd_signal'),rsi=metric(data,'m3','rsi14');
  const rows=(data?.price_history||[]).filter((r:any)=>r.date&&(!data.as_of||r.date<=data.as_of)).slice(-20);
  const lows=rows.map((r:any)=>r.low).filter(finite),highs=rows.map((r:any)=>r.high).filter(finite);
  const trend=close!==null&&ma20!==null&&ma50!==null?(close>ma20&&ma20>ma50?'up':close<ma20&&ma20<ma50?'down':'mixed'):'missing';
  return {close,ma20,ma50,macd,signal,rsi,trend,macdDirection:macd!==null&&signal!==null?(macd>signal?'above':macd<signal?'below':'equal'):'missing',
    rsiLabel:rsi===null?'Chưa đủ dữ liệu':rsi<30?'Vùng quá bán':rsi>70?'Vùng quá mua':'Trung tính',
    low:lows.length?Math.min(...lows):null,high:highs.length?Math.max(...highs):null,rangeSessions:rows.length,
  };
}
