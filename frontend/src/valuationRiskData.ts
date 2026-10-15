import {financialModel, finite, metric, ratio} from './analysisData.ts';

export function valuationModel(data:any) {
  const financial=financialModel(data),items=financial.items;
  const pe=metric(data,'m4','pe'),pb=metric(data,'m4','pb'),eps=metric(data,'m4','eps_used'),bvps=metric(data,'m4','book_per_share');
  const medianPE=metric(data,'m4','sector_median_pe'),medianPB=metric(data,'m4','sector_median_pb');
  const source=data?.modules?.m4;
  const fallback=source?.flags?.includes('m4_sector_fallback')||false;
  const blocked=data?.quality_gate?.scored===false;
  // Only the published M7 result may supply scenarios, never raw module targets.
  const target=!blocked&&finite(data?.target?.base)&&data.target.base>0?data.target:null;
  const shares=data?.company?.shares_outstanding,price=data?.current_price;
  const marketCap=finite(shares)&&shares>0&&finite(price)&&price>0?shares*price:null;
  const unit=data?.financial_reports?.unit;
  const multiplier=unit==='VND'?1:['VND_billions','VND_billion'].includes(unit)?1e9:['VND_millions','VND_million'].includes(unit)?1e6:null;
  const debt=finite(items.total_debt)?items.total_debt:finite(items.short_term_debt)&&finite(items.long_term_debt)?items.short_term_debt+items.long_term_debt:null;
  const ebitda=finite(items.ebitda)?items.ebitda:finite(items.ebit)&&finite(items.depreciation)?items.ebit+items.depreciation:null;
  const ev=!financial.isBank&&marketCap!==null&&multiplier!==null&&debt!==null&&finite(items.cash)?marketCap+(debt-items.cash)*multiplier:null;
  return {pe,pb,eps,bvps,medianPE,medianPB,fallback,scope:fallback?'thị trường':'ngành',blocked,target,financial,
    peReference:!blocked&&eps!==null&&eps>0&&medianPE!==null&&medianPE>0?eps*medianPE:null,
    pbReference:!blocked&&!source?.flags?.includes('m4_pb_leg_dropped')&&bvps!==null&&bvps>0&&medianPB!==null&&medianPB>0?bvps*medianPB:null,
    upside:target&&finite(price)&&price>0?(target.base/price-1)*100:null,
    evEbitda:ev!==null&&multiplier!==null&&ebitda!==null?ratio(ev,ebitda*multiplier):null,
    peg:pe!==null&&pe>0&&financial.epsGrowth!==null&&financial.epsGrowth>0?pe/financial.epsGrowth:null,
    epsBasis:data?.modules?.m4?.metrics?.eps_used?.note?.startsWith('ttm')?'TTM':'theo nguồn M4',
  };
}

export const riskAxes=[
  {key:'volatility_risk_subscore',label:'Biến động',color:'#00B8FF'},
  {key:'drawdown_risk_subscore',label:'Drawdown',color:'#FFB547'},
  {key:'var_risk_subscore',label:'VaR 95%',color:'#00E5A0'},
  {key:'tail_risk_subscore',label:'CVaR 95%',color:'#A855F7'},
  {key:'beta_risk_subscore',label:'Beta',color:'#FF426B'},
];

export function riskModel(data:any) {
  const module=data?.modules?.m6;
  const rows=(data?.price_history||[]).filter((r:any)=>r.date&&(!data?.as_of||r.date<=data.as_of)&&finite(r.close)&&r.close>0).slice(-20);
  const liquid=rows.length>0&&rows.every((r:any)=>finite(r.volume)&&r.volume>=0)?rows.reduce((sum:number,r:any)=>sum+r.close*r.volume,0)/rows.length:null;
  return {
    score:['ok','partial'].includes(module?.status)&&finite(module.score)?module.score:null,
    volatility:metric(data,'m6','annualized_volatility'),benchmarkVolatility:metric(data,'m6','benchmark_volatility'),
    beta:metric(data,'m6','beta'),drawdown:metric(data,'m6','max_drawdown'),var95:metric(data,'m6','historical_var_95'),cvar95:metric(data,'m6','historical_cvar_95'),
    observations:metric(data,'m6','aligned_observations'),liquid,liquidSessions:rows.length,
    axes:riskAxes.map(axis=>({...axis,value:metric(data,'m6',axis.key)})),
  };
}

export function alignedReturns(prices:any,asof:string,limit=252) {
  const valid=(r:any)=>r&&typeof r.time==='string'&&r.time<=asof&&finite(r.close)&&r.close>0;
  const stock=new Map<string,number>((prices?.ohlcv||[]).filter(valid).map((r:any)=>[r.time,r.close]));
  const index=new Map<string,number>((prices?.index?.series||[]).filter(valid).map((r:any)=>[r.time,r.close]));
  const days=Array.from(stock.keys()).filter(day=>index.has(day)).sort().slice(-limit);
  if(days.length<2)return [];
  const firstStock=stock.get(days[0])!,firstIndex=index.get(days[0])!;
  return days.map(day=>({date:day,stock:(stock.get(day)!/firstStock-1)*100,index:(index.get(day)!/firstIndex-1)*100}));
}

export function valuationCSV(data:any) {
  const value=valuationModel(data),risk=riskModel(data);
  const fields:any[][]=[['Mã',data?.ticker],['Snapshot',data?.as_of],['Phương pháp công bố',value.target?.method||'Chưa công bố'],['Giá đóng cửa (VND)',data?.current_price],['P/E',value.pe],['P/B',value.pb],['EPS (VND)',value.eps],['BVPS (VND)',value.bvps],['Nguồn tham chiếu',value.scope],['P/E tham chiếu',value.medianPE],['P/B tham chiếu',value.medianPB],['Kịch bản thận trọng (VND)',value.target?.bear],['Kịch bản cơ sở (VND)',value.target?.base],['Kịch bản tích cực (VND)',value.target?.bull],['Upside (%)',value.upside],['EV/EBITDA báo cáo năm',value.evEbitda],['PEG theo tăng trưởng EPS năm',value.peg],['Điểm rủi ro M6',risk.score],['Biến động quy đổi năm (%)',risk.volatility],['Beta',risk.beta],['Drawdown - mức giảm (%)',risk.drawdown],['VaR 95% - mức lỗ ước tính (%)',risk.var95]];
  return '\uFEFF'+fields.map(row=>row.map(cell=>`"${String(cell??'').replace(/"/g,'""')}"`).join(',')).join('\r\n');
}
