import React, {useEffect, useRef, useState} from 'react';
import {Activity, ArrowRight, BarChart3, Coins, Download, FileText, Gauge, Layers3, RefreshCw, ShieldCheck, Sparkles, Target, TrendingUp} from 'lucide-react';
import {finite, numberText as num} from '../analysisData';
import {DcfPanel} from './DcfPanel';
import {alignedReturns, riskModel, valuationCSV, valuationModel} from '../valuationRiskData';

function ScenarioChart({data,model}:any) {
  const [selected,setSelected]=useState<string|null>(null);
  const price=finite(data?.current_price)&&data.current_price>0?data.current_price:null;
  const rows=[{key:'bear',label:'Thận trọng',color:'#FFB547'},{key:'base',label:'Cơ sở',color:'#00E5A0'},{key:'bull',label:'Tích cực',color:'#00B8FF'}];
  const values=[price,...rows.map(row=>model.target?.[row.key])].filter((v:any)=>finite(v)&&v>0);
  if(!model.target)return <div className="analysis-empty">Chưa có giá mục tiêu được công bố cho mã này.</div>;
  const lo=Math.min(...values)*.85,hi=Math.max(...values)*1.15,x=(v:number)=>90+(v-lo)/(hi-lo||1)*355;
  return <div className="scenario-chart"><h4>Ba kịch bản giá mục tiêu công bố</h4><svg viewBox="0 0 490 214" role="img" aria-label="Kịch bản giá mục tiêu thận trọng, cơ sở và tích cực" onPointerLeave={()=>setSelected(null)}>
    {[0,1,2,3,4].map(i=><g key={i}><line x1={90+i*355/4} x2={90+i*355/4} y1={25} y2={166} stroke="#365b87" opacity={.6}/><text x={90+i*355/4} y={190} textAnchor="middle" fontSize={11} fill="#b9cbe3">{num(lo+i*(hi-lo)/4,0)}</text></g>)}
    {price!==null&&<line x1={x(price)} x2={x(price)} y1={20} y2={170} stroke="#FF426B" strokeDasharray="4 4"/>}
    {rows.map((row,i)=>{const value=model.target[row.key],y=46+i*48;return <g key={row.key} tabIndex={0} onFocus={()=>setSelected(row.key)} onBlur={()=>setSelected(null)} onPointerEnter={()=>setSelected(row.key)} aria-label={`${row.label}: ${num(value,0)} VND`}>
      <rect x={3} y={y-20} width={480} height={44} rx={4} fill={selected===row.key?'#2563FF15':'transparent'}/><text x={3} y={y+4} fill="#cbdaf0" fontSize={13}>{row.label}</text><line x1={90} x2={445} y1={y} y2={y} stroke="#365b87"/>
      {finite(value)&&value>0?<><line x1={x(price??value)} x2={x(value)} y1={y} y2={y} stroke={row.color} strokeWidth={8} strokeLinecap="round" opacity={.7}/><circle cx={x(value)} cy={y} r={4} fill={row.color}/><text x={x(value)} y={y-12} fill={row.color} fontSize={13} fontWeight={800} textAnchor="middle">{num(value,0)}</text></>:<text x={260} y={y+4} fill="#9bafca" fontSize={12}>Chưa công bố</text>}
    </g>;})}<text x={275} y={211} fill="#9bafca" fontSize={11} textAnchor="middle">Giá (VND/cổ phiếu) · nét hồng: giá đóng cửa</text>
  </svg><output aria-live="polite">{selected?`${rows.find(row=>row.key===selected)?.label}: ${num(model.target[selected],0)} VND/cổ phiếu`:'Các kịch bản không phải khoảng tin cậy thống kê.'}</output></div>;
}

function ReturnComparison({prices,symbol,asof}:any) {
  const [range,setRange]=useState(252),[hover,setHover]=useState<{key:string;index:number}|null>(null);
  const rows=alignedReturns(prices,asof,range),key=`${symbol}/${asof}/${range}`;
  const chosen=hover?.key===key?rows[hover.index]:null;
  const values=rows.flatMap(row=>[row.stock,row.index]);
  const min=Math.min(0,...values),max=Math.max(0,...values),pad=(max-min)*.12||1;
  const lo=min-pad,hi=max+pad,x=(i:number)=>45+i/(rows.length-1||1)*400,y=(v:number)=>25+(hi-v)/(hi-lo)*155;
  const path=(field:'stock'|'index')=>rows.map((r,i)=>`${i?'L':'M'}${x(i)},${y(r[field])}`).join(' ');
  const choose=(index:number)=>setHover({key,index:Math.max(0,Math.min(rows.length-1,index))});
  const last=chosen||rows.at(-1);
  const pointer=(event:React.PointerEvent<SVGSVGElement>)=>{const matrix=event.currentTarget.getScreenCTM();if(!matrix)return;const point=event.currentTarget.createSVGPoint();point.x=event.clientX;point.y=event.clientY;const local=point.matrixTransform(matrix.inverse());choose(Math.round((local.x-45)/400*(rows.length-1)));};
  return <section className="return-comparison"><div className="analysis-subheading"><h3><TrendingUp size={15}/> Diễn biến giá cùng gốc</h3><div className="statement-tabs">{[[63,'3T'],[126,'6T'],[252,'1N']].map(([value,label])=><button key={value} className={range===value?'active':''} onClick={()=>{setRange(Number(value));setHover(null);}}>{label}</button>)}</div></div>
    <div className="annual-legend"><span><i/>{symbol} {num(last?.stock)}%</span><span><i style={{background:'#FF9B38'}}/>VN-Index {num(last?.index)}%</span></div>
    {rows.length<2?<div className="analysis-empty">Chưa có đủ giá cổ phiếu và chỉ số cùng ngày.</div>:<svg className="return-chart" viewBox="0 0 490 215" role="img" aria-label={`So sánh thay đổi giá ${symbol} và VN-Index`} tabIndex={0} onPointerMove={pointer} onPointerDown={pointer} onPointerLeave={()=>setHover(null)} onFocus={()=>choose(rows.length-1)} onBlur={()=>setHover(null)} onKeyDown={event=>{if(['ArrowLeft','ArrowRight','Home','End','Escape'].includes(event.key)){event.preventDefault();if(event.key==='Escape')setHover(null);else choose(event.key==='Home'?0:event.key==='End'?rows.length-1:(hover?.index??rows.length-1)+(event.key==='ArrowLeft'?-1:1));}}}>
      <rect width={490} height={215} fill="transparent"/>{[0,1,2,3,4].map(i=>{const value=hi-i*(hi-lo)/4;return <g key={i}><line x1={45} x2={445} y1={y(value)} y2={y(value)} stroke="#365b87" opacity={.55}/><text x={38} y={y(value)+3} textAnchor="end" fill="#b9cbe3" fontSize={11}>{num(value,0)}%</text></g>;})}
      {[0,1,2,3].map(i=>{const index=Math.round(i*(rows.length-1)/3);return <text key={i} x={x(index)} y={204} fill="#9bafca" fontSize={11} textAnchor={i===0?'start':i===3?'end':'middle'}>{rows[index].date}</text>;})}
      <path d={path('stock')} stroke="#00B8FF" strokeWidth={1.8} fill="none"/><path d={path('index')} stroke="#FF9B38" strokeWidth={1.5} fill="none"/>
      {chosen&&hover&&<g pointerEvents="none"><line x1={x(hover.index)} x2={x(hover.index)} y1={25} y2={180} stroke="#b9cbe3" strokeDasharray="4 4"/><circle cx={x(hover.index)} cy={y(chosen.stock)} r={3} fill="#00B8FF"/><circle cx={x(hover.index)} cy={y(chosen.index)} r={3} fill="#FF9B38"/></g>}
    </svg>}
    <output className="analysis-source-note return-tooltip" role="status">{chosen?`${chosen.date} · ${symbol}: ${num(chosen.stock)}% · VN-Index: ${num(chosen.index)}%`:`${rows.length} phiên khớp ngày; cùng gốc 0% tại ${rows[0]?.date||'—'}. Đây là thay đổi giá, không phải độ biến động.`}</output>
  </section>;
}

function RiskRadar({risk,symbol}:any) {
  const point=(i:number,r:number)=>{const angle=-Math.PI/2+i*2*Math.PI/5;return [145+Math.cos(angle)*r,132+Math.sin(angle)*r];};
  const all=risk.axes.every((axis:any)=>finite(axis.value));
  return <section className="risk-radar-panel"><div className="analysis-subheading"><h3><Layers3 size={15}/> Bản đồ rủi ro M6</h3></div><svg className="risk-radar" viewBox="0 0 290 260" role="img" aria-label={`Điểm thành phần rủi ro ${symbol}`}>
    {[.25,.5,.75,1].map(scale=><polygon key={scale} points={risk.axes.map((_:any,i:number)=>point(i,scale*72).join(',')).join(' ')} fill="none" stroke="#365b87"/>)}
    {risk.axes.map((axis:any,i:number)=>{const [x,y]=point(i,72),[tx,ty]=point(i,106);return <g key={axis.key}><line x1={145} y1={132} x2={x} y2={y} stroke="#365b87"/><text x={tx} y={ty} textAnchor="middle" fill="#b9cbe3" fontSize={12}>{axis.label}</text><text x={tx} y={ty+17} textAnchor="middle" fill={axis.color} fontSize={15} fontWeight={800}>{num(axis.value,1)}</text></g>;})}
    {all?<><polygon points={risk.axes.map((axis:any,i:number)=>point(i,Math.max(0,Math.min(100,axis.value))*.72).join(',')).join(' ')} fill="#00D9FF20" stroke="#00D9FF" strokeWidth={1.2}/>{risk.axes.map((axis:any,i:number)=>{const [cx,cy]=point(i,Math.max(0,Math.min(100,axis.value))*.72);return <circle key={axis.key} cx={cx} cy={cy} r={3} fill={axis.color}/>;})}</>:<text x={145} y={132} fill="#9bafca" fontSize={12} textAnchor="middle">Chưa đủ chỉ số thành phần</text>}
  </svg><p className="analysis-source-note">Điểm càng cao, rủi ro đo được càng lớn. Chưa có chuỗi điểm ngành để so sánh.</p></section>;
}

export function ValuationRiskPage({data,symbol,onDetail}:{data:any;symbol:string;onDetail:(key:string)=>void}) {
  const emptyTargetMessage='Chưa đủ dữ liệu hoặc chưa đạt tiêu chí chất lượng để công bố giá mục tiêu.';
  const targetMethodNote='Giá mục tiêu tổng hợp theo phương pháp và trọng số trong mục Phương pháp; giữ nguyên khi đổi tab tham chiếu.';
  const [method,setMethod]=useState('pe'),[retry,setRetry]=useState(0);
  const [extra,setExtra]=useState<any>({key:'',loading:false,peers:null,prices:null,errors:[]});
  const riskRef=useRef<HTMLElement>(null),valuationRef=useRef<HTMLElement>(null);
  const model=valuationModel(data),risk=riskModel(data);
  const key=`${symbol}/${data?.as_of}/${data?.profile}`;
  const current=extra.key===key?extra:{loading:!!data,peers:null,prices:null,errors:[]};
  useEffect(()=>{
    if(!data?.as_of||data?.ticker!==symbol)return;
    const controller=new AbortController(),asof=data.as_of;
    setExtra({key,loading:true,peers:null,prices:null,errors:[]});
    const read=async(path:string)=>{const response=await fetch(path,{signal:controller.signal});if(!response.ok)throw Error(`HTTP ${response.status}`);const result=await response.json();if(result.symbol!==symbol||result.asof!==asof)throw Error('Dữ liệu khác mã hoặc ngày snapshot');return result;};
    Promise.allSettled([read(`/api/tickers/${encodeURIComponent(symbol)}/peers`),read(`/api/tickers/${encodeURIComponent(symbol)}/prices?range=1y&include_index=true&profile=${encodeURIComponent(data.profile)}`)])
      .then(results=>{if(controller.signal.aborted)return;setExtra({key,loading:false,peers:results[0].status==='fulfilled'?results[0].value:null,prices:results[1].status==='fulfilled'?results[1].value:null,errors:results.flatMap((result,i)=>result.status==='rejected'?[`${i?'Chuỗi giá so sánh':'Nhóm tham chiếu'}: ${result.reason.message}`]:[])});});
    return ()=>controller.abort();
  },[symbol,data?.as_of,data?.profile,retry]);
  const target=model.target,reference=method==='pb'?model.pbReference:model.peReference;
  const cards=[
    {label:`P/E (${model.epsBasis})`,value:num(model.pe),note:`Tham chiếu ${model.scope}: ${num(model.medianPE)}`,tone:'blue',icon:BarChart3},
    {label:'P/B',value:num(model.pb),note:`Tham chiếu ${model.scope}: ${num(model.medianPB)}`,tone:'purple',icon:ShieldCheck},
    {label:`EPS (${model.epsBasis})`,value:`${num(model.eps,0)} ₫`,note:'Nguồn định giá M4',tone:'green',icon:Coins},
    {label:'BVPS',value:`${num(model.bvps,0)} ₫`,note:'Giá trị sổ sách / cổ phiếu',tone:'cyan',icon:Layers3},
    {label:`EV/EBITDA · ${model.financial.latest?.period||'năm'}`,value:num(model.evEbitda),note:model.financial.isBank?'Không áp dụng cho ngân hàng':'EV theo giá snapshot, EBITDA năm',tone:'purple',icon:Gauge},
    {label:'PEG · EPS năm',value:num(model.peg),note:'P/E / tăng trưởng EPS năm (%)',tone:'orange',icon:TrendingUp},
  ];
  const riskCards=[
    {label:'Biến động quy đổi năm',value:`${num(risk.volatility)}%`,note:`${num(risk.observations,0)} lợi suất khớp ngày`,tone:'pink',icon:Activity},
    {label:'Biến động VN-Index',value:`${num(risk.benchmarkVolatility)}%`,note:'Quy đổi năm · cùng cửa sổ M6',tone:'blue',icon:BarChart3},
    {label:'Beta',value:num(risk.beta),note:'Độ nhạy lợi suất với VN-Index',tone:'purple',icon:TrendingUp},
    {label:'Max Drawdown',value:finite(risk.drawdown)?`−${num(Math.abs(risk.drawdown))}%`:'—',note:'Mức giảm từ đỉnh lịch sử',tone:'orange',icon:Layers3},
    {label:'VaR 95% · 1 phiên',value:finite(risk.var95)?`−${num(Math.abs(risk.var95))}%`:'—',note:'Mức lỗ ước tính theo lịch sử',tone:'pink',icon:ShieldCheck},
    {label:`GTGD ước tính TB ${risk.liquidSessions} phiên`,value:finite(risk.liquid)?`${num(risk.liquid/1e9)} tỷ`:'—',note:'Giá đóng cửa × khối lượng',tone:'green',icon:Coins},
  ];
  const download=()=>{const url=URL.createObjectURL(new Blob([valuationCSV(data)],{type:'text/csv;charset=utf-8;'}));const link=document.createElement('a');link.href=url;link.download=`${symbol}_dinh_gia_${data?.as_of}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
  return <div className="valuation-risk-page">
    <nav className="analysis-jump-nav" aria-label="Mục định giá và rủi ro"><button onClick={()=>valuationRef.current?.scrollIntoView({behavior:'smooth',block:'start'})}>Định giá & Giá mục tiêu</button><button onClick={()=>riskRef.current?.scrollIntoView({behavior:'smooth',block:'start'})}>Rủi ro</button></nav>
    <section ref={valuationRef} className="analysis-module valuation-module" aria-label="Định giá và giá mục tiêu"><div className="analysis-module-heading"><Target size={28}/><h2>Định giá & Giá mục tiêu</h2><p>Đối chiếu định giá với nhóm tham chiếu và kịch bản từ pipeline</p><div><button className="btn report-action valuation-method-button" onClick={()=>onDetail('valuation')}><FileText size={15}/> Xem phương pháp định giá</button><button className="btn download-valuation" disabled={!data} onClick={download}><Download size={15}/> Tải CSV định giá</button></div></div>
      <div className="fundamental-kpis valuation-kpis">{cards.map(card=><article className={`fundamental-kpi ${card.tone}`} key={card.label}><span className="kpi-icon"><card.icon size={23}/></span><div><h3 title={card.label}>{card.label}</h3><strong>{card.value}</strong><p className="muted">{card.note}</p></div></article>)}</div>
      {model.fallback&&<p className="valuation-reference-note">Mẫu ngành nhỏ hoặc không đủ điều kiện; M4 đang dùng median thị trường và có thể bỏ chân P/B. Không coi đây là so sánh thuần cùng ngành.</p>}
      <div className="valuation-main-grid"><section className="valuation-method-panel"><div className="valuation-tabs" role="tablist" aria-label="Phương pháp định giá">{[['pe','P/E'],['pb','P/B'],['dcf','DCF'],['peers','So sánh tham chiếu']].map(([id,label])=><button key={id} role="tab" aria-selected={method===id} className={method===id?'active':''} onClick={()=>setMethod(id)}>{label}</button>)}</div>
        {method==='dcf'?<DcfPanel data={data}/>:method==='peers'?<div className="peer-comparison"><h3>Nhóm tham chiếu từ snapshot</h3><div className="peer-scroll"><table><thead><tr><th>Mã</th><th>P/E</th><th>P/B</th><th>ROE</th></tr></thead><tbody>{(current.peers?.items||[]).map((row:any)=><tr key={row.ticker} className={row.is_self?'own-peer':''}><th>{row.ticker}</th><td>{num(row.is_self?model.pe:row.pe)}</td><td>{num(row.is_self?model.pb:row.pb)}</td><td>{finite(row.roe)?`${num(row.roe*100)}%`:'—'}</td></tr>)}</tbody></table></div>{!current.peers&&<p className="analysis-empty">{current.loading?'Đang tải nhóm tham chiếu…':'Chưa tải được nhóm tham chiếu.'}</p>}<p className="analysis-source-note">Nhóm lấy từ snapshot, có thể gồm mã khác ngành khi mẫu ngành nhỏ. Median dùng định giá lấy đúng từ M4.</p></div>:<><div className="method-reference"><h3>Tham chiếu {method==='pe'?'P/E':'P/B'}</h3><strong>{num(reference,0)} <small>VND/cổ phiếu</small></strong><p>{method==='pe'?`EPS ${num(model.eps)} × P/E tham chiếu ${num(model.medianPE)}`:`BVPS ${num(model.bvps)} × P/B tham chiếu ${num(model.medianPB)}`}</p>{reference===null&&<small>{model.blocked?'Chưa công bố giá tham chiếu do quality gate.':'Chưa đủ số liệu hoặc chân định giá không được sử dụng.'}</small>}</div><ScenarioChart data={data} model={model}/></>}
      </section>
      <section className="published-target"><div className="target-primary"><Target size={34}/><div><h3>Giá mục tiêu công bố</h3><strong>{num(target?.base,0)} <small>₫</small></strong><span className={model.upside!==null&&model.upside<0?'negative':'positive'}>{num(model.upside)}% upside</span></div></div><div className="target-mini-grid"><div><span>Giá đóng cửa</span><strong>{num(data?.current_price,0)} ₫</strong></div><div><span>Tham chiếu</span><strong>{model.scope}</strong></div></div><div className={`target-conclusion ${target?'':'unavailable'}`}><BarChart3 size={27}/><div><span>{target?'So với giá đóng cửa':'Chưa công bố mục tiêu'}</span><strong>{target?model.upside!==null&&model.upside>=0?'Mục tiêu cao hơn giá':'Mục tiêu thấp hơn giá':'Chưa đủ điều kiện'}</strong><p>{target?'Kết quả từ mô hình định giá tương đối.':emptyTargetMessage}</p></div></div><p className="analysis-source-note">{targetMethodNote}</p></section>
      <aside className="valuation-commentary"><div className="analysis-subheading"><h3><Sparkles size={16}/> Nhận định định giá</h3></div><ul><li>{target?`Kịch bản cơ sở ${num(target.base,0)}₫, chênh lệch ${num(model.upside)}% so với giá đóng cửa ${num(data?.current_price,0)}₫.`:'Mã này chưa có giá mục tiêu công bố; không suy diễn khuyến nghị từ số liệu còn thiếu.'}</li><li>{model.pe!==null&&model.medianPE!==null?`P/E ${num(model.pe)} so với median ${model.scope} ${num(model.medianPE)}. Đây là so sánh tương đối, không phải đánh giá toàn bộ doanh nghiệp.`:'Chưa có đủ P/E hoặc median tham chiếu để so sánh.'}</li><li>{model.fallback?'Nguồn định giá đang dùng tham chiếu thị trường vì mẫu ngành chưa phù hợp.':'M4 dùng dữ liệu ngành khi đủ điều kiện theo cấu hình.'}</li><li>EV/EBITDA và PEG là chỉ số bổ sung theo BCTC năm, không được đưa vào giá mục tiêu của pipeline.</li></ul><p className="analysis-source-note">Diễn giải theo quy tắc từ dữ liệu hiện có.</p></aside></div>
    </section>
    <section ref={riskRef} className="analysis-module risk-module" aria-label="Phân tích rủi ro"><div className="analysis-module-heading"><ShieldCheck size={28}/><h2>Rủi ro</h2><p>Đo lường rủi ro giá và thị trường từ lịch sử · R cao = rủi ro cao</p><button className="text-btn risk-method-button" onClick={()=>onDetail('risk')}>Xem chỉ số & căn cứ <ArrowRight size={13}/></button></div>
      <div className="risk-summary-row"><div className="fundamental-kpis risk-kpis">{riskCards.map(card=><article className={`fundamental-kpi ${card.tone}`} key={card.label}><span className="kpi-icon"><card.icon size={20}/></span><div><h3 title={card.label}>{card.label}</h3><strong>{card.value}</strong><p className="muted">{card.note}</p></div></article>)}</div><section className="risk-score-gauge"><svg viewBox="0 0 100 100" aria-hidden="true"><circle cx={50} cy={50} r={36} fill="none" stroke="#FF426B22" strokeWidth={9}/>{risk.score!==null&&<circle cx={50} cy={50} r={36} fill="none" stroke="#FF426B" strokeWidth={9} strokeLinecap="round" strokeDasharray={`${Math.max(0,Math.min(100,risk.score))*2.262} 226.2`} transform="rotate(-90 50 50)"/>}<ShieldCheck x={35} y={35} width={30} height={30} color="#FF426B"/></svg><div><span>Điểm rủi ro M6</span><strong>{num(risk.score)}<small>/100</small></strong><p>R càng cao, rủi ro càng lớn</p></div></section></div>
      <div className="risk-main-grid"><ReturnComparison prices={current.prices} symbol={symbol} asof={data?.as_of||''}/><RiskRadar risk={risk} symbol={symbol}/><section className="risk-components"><div className="analysis-subheading"><h3><Gauge size={15}/> Chi tiết điểm rủi ro</h3></div><div className="risk-bars">{risk.axes.map((axis:any)=><div key={axis.key}><div><span style={{color:axis.color}}>{axis.label}</span><small>M6 · thang điểm 0–100</small></div><div className="risk-bar-track"><i style={{width:`${finite(axis.value)?Math.max(0,Math.min(100,axis.value)):0}%`,background:axis.color}}/></div><strong>{num(axis.value,1)}</strong></div>)}</div><p className="analysis-source-note">Năm thành phần thực tế của M6. Không tự gán điểm rủi ro cơ bản/tin tức/thanh khoản.</p></section><aside className="risk-commentary"><div className="analysis-subheading"><h3><ShieldCheck size={16}/> Nhận định rủi ro</h3></div><ul><li>{risk.beta!==null?`Beta ${num(risk.beta)} ước tính từ lợi suất cổ phiếu và VN-Index; không phải dự báo mức tăng/giảm tương lai.`:'Chưa đủ dữ liệu căn ngày để tính Beta.'}</li><li>{risk.drawdown!==null?`Mức giảm từ đỉnh lớn nhất trong cửa sổ M6: ${num(Math.abs(risk.drawdown))}%.`:'Chưa đủ chuỗi giá để tính mức giảm từ đỉnh.'}</li><li>{risk.var95!==null?`VaR 95% khoảng ${num(Math.abs(risk.var95))}% cho một phiên. CVaR 95%: ${num(risk.cvar95)}%. Có thể xảy ra mức lỗ lớn hơn.`:'Chưa đủ dữ liệu để ước tính VaR/CVaR.'}</li><li>GTGD ước tính dùng giá đóng cửa × khối lượng, không phải giá trị khớp lệnh chính xác.</li></ul></aside></div>
      {current.loading&&<p className="supplementary-status"><RefreshCw size={13} className="spin"/> Đang tải nhóm tham chiếu và giá VN-Index…</p>}{current.errors?.length>0&&<div className="supplementary-error" role="alert">{current.errors.join(' · ')}<button onClick={()=>setRetry(n=>n+1)}>Thử lại dữ liệu bổ sung</button></div>}
    </section>
  </div>;
}
