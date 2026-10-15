import React, {useEffect, useRef, useState} from 'react';
import * as jsx from 'react/jsx-runtime';
import {Activity, ArrowDownRight, ArrowRight, ArrowUpRight, BarChart3, Coins, Download, FileText, Layers3, ShieldCheck, Sparkles, TrendingUp, Wallet, X} from 'lucide-react';
import {exportStatements, financialModel, finite, metric, numberText as num, statementFields, technicalModel} from '../analysisData';
import {DividendsPanel} from './DividendsPanel';
import {PriceChart} from './DashboardCharts';
import {ValuationRiskPage} from './ValuationRiskPage';

export function AnalysisSnapshotMetrics({data,valuation=false}:{data:any;valuation?:boolean}) {
  const shares=data?.company?.shares_outstanding;
  const cap=finite(shares)&&shares>0&&finite(data?.current_price)?shares*data.current_price/1e9:null;
  const ttm=data?.modules?.m4?.metrics?.eps_used?.note?.startsWith('ttm');
  if(valuation)return <div className="analysis-valuation-metrics valuation-metrics-page-two">
    <div><span>P/E {ttm?'(TTM)':''}</span><strong>{num(metric(data,'m4','pe'))}</strong></div>
    <div><span>P/B</span><strong>{num(metric(data,'m4','pb'))}</strong></div>
    <div><span>EPS {ttm?'(TTM)':''}</span><strong>{num(metric(data,'m4','eps_used'),0)} <small>₫</small></strong></div>
    <div><span>ROE (năm)</span><strong>{num(metric(data,'m2','roe')!==null?metric(data,'m2','roe')!*(data?.modules?.m2?.metrics?.roe?.unit==='%'?1:100):null)}<small>%</small></strong></div>
  </div>;
  return <div className="analysis-valuation-metrics">
    <div><span>Vốn hóa</span><strong>{num(cap,0)} <small>tỷ</small></strong></div>
    <div><span>P/E {ttm?'(TTM)':''}</span><strong>{num(metric(data,'m4','pe'))}</strong></div>
    <div><span>EPS {ttm?'(TTM)':'định giá'}</span><strong>{num(metric(data,'m4','eps_used'),0)} <small>₫</small></strong></div>
  </div>;
}

function AnnualChart({model}:any) {
  const [selected,setSelected]=useState<string|null>(null);
  const rows=model.annual.slice(-5),divisor=model.unit.divisor;
  const values=rows.flatMap((r:any)=>[r.items?.[model.revenueKey],r.items?.net_income]).filter(finite).map((v:number)=>v/divisor);
  const low=Math.min(0,...values),high=Math.max(0,...values),span=high-low||1;
  const y=(value:number)=>32+(high-value)/span*148;
  const width=420,x=(i:number)=>60+(i+.5)*(width-80)/Math.max(1,rows.length);
  const hovered=rows.find((r:any)=>r.period===selected);
  return <div className="annual-chart-block"><div className="analysis-subheading"><h3>{model.revenueLabel} & Lợi nhuận sau thuế</h3></div>
    <div className="annual-legend"><span><i/>{model.revenueLabel}</span><span><i/>Lợi nhuận sau thuế</span><small>({model.unit.label})</small></div>
    {!rows.length?<div className="analysis-empty">Chưa có báo cáo năm để vẽ biểu đồ.</div>:<svg className="annual-chart" viewBox="0 0 420 215" role="img" aria-label="Biểu đồ doanh thu và lợi nhuận theo năm">
      {[0,1,2,3,4].map(i=>{const value=high-i*span/4;return <g key={i}><line x1={52} x2={410} y1={y(value)} y2={y(value)} stroke="#365b87" opacity={.55}/><text x={46} y={y(value)+3} textAnchor="end" fontSize={11} fill="#b9cbe3">{num(value,0)}</text></g>;})}
      <line x1={52} x2={410} y1={y(0)} y2={y(0)} stroke="#385984"/>
      {rows.map((r:any,i:number)=><g key={r.period} tabIndex={0} role="button" aria-label={`${r.period}: ${model.revenueLabel} ${num(finite(r.items?.[model.revenueKey])?r.items[model.revenueKey]/divisor:null)}; lợi nhuận ${num(finite(r.items?.net_income)?r.items.net_income/divisor:null)} ${model.unit.label}`} onPointerEnter={()=>setSelected(r.period)} onPointerLeave={()=>setSelected(null)} onFocus={()=>setSelected(r.period)} onBlur={()=>setSelected(null)}>
        <rect x={x(i)-32} y={25} width={64} height={161} fill={selected===r.period?'#2563FF11':'transparent'}/>
        {[model.revenueKey,'net_income'].map((key:string,k:number)=>{const value=r.items?.[key];if(!finite(value))return null;const scaled=value/divisor;return <g key={key}><rect x={x(i)+(k?2:-21)} y={Math.min(y(scaled),y(0))} width={19} height={Math.max(1,Math.abs(y(scaled)-y(0)))} rx={2} fill={k?'#00E5A0':'#00B8FF'}/><text x={x(i)+(k?11.5:-11.5)} y={scaled>=0?y(scaled)-5:y(scaled)+12} fill={k?'#00E5A0':'#b6e5ff'} fontSize={10} textAnchor="middle">{num(scaled,0)}</text></g>;})}
        <text x={x(i)} y={202} textAnchor="middle" fill="#b9cbe3" fontSize={12}>{r.period}</text>
      </g>)}
    </svg>}
    <output className="annual-chart-tooltip" aria-live="polite">{hovered?`${hovered.period} · ${model.revenueLabel}: ${num(finite(hovered.items?.[model.revenueKey])?hovered.items[model.revenueKey]/divisor:null)} · LNST: ${num(finite(hovered.items?.net_income)?hovered.items.net_income/divisor:null)} ${model.unit.label}`:'Chạm hoặc trỏ vào cột để xem số liệu theo năm'}</output>
  </div>;
}

function Insight({title,children,tone='cyan',icon:Icon=TrendingUp}:any) {return <article className={`analysis-insight ${tone}`}><span><Icon size={19}/></span><div><h4>{title}</h4><p>{children}</p></div></article>;}

export function AnalysisPage({data,symbol,activeTab,onNavigate,onPageChange}:{data:any;symbol:string;activeTab:string;onNavigate:(id:string)=>void;onPageChange?:(page:number)=>void}) {
  const isSecond=(tab:string)=>tab==='valuation'||tab==='risk';
  const [page,setPage]=useState(isSecond(activeTab)?2:1);
  const [statement,setStatement]=useState('income'),[detail,setDetail]=useState<string|null>(activeTab==='technical'||isSecond(activeTab)?null:activeTab);
  const technicalRef=useRef<HTMLElement>(null),fundamentalRef=useRef<HTMLElement>(null),closeRef=useRef<HTMLButtonElement>(null);
  const model=financialModel(data),tech=technicalModel(data);
  const money=(v:any)=>finite(v)?num(v/model.unit.divisor,0):'—';
  const percentage=(v:any)=>finite(v)?`${num(v)}%`:'—';
  const basis=model.latest?`Năm ${model.latest.period}`:'Chưa có BCTC';
  const fields=statementFields(statement,model.revenueLabel,model.revenueKey),columns=model.annual.slice(-4);
  const ratioUnit=data?.modules?.m2?.metrics?.roe?.unit;
  const roe=model.roe!==null?model.roe*(ratioUnit==='%'?1:100):null;
  const cards=[
    {label:model.revenueLabel,value:money(model.items[model.revenueKey]),unit:model.unit.label,delta:model.revenueGrowth,icon:BarChart3,tone:'blue'},
    {label:'Lợi nhuận sau thuế',value:money(model.items.net_income),unit:model.unit.label,delta:model.profitGrowth,icon:TrendingUp,tone:'green'},
    {label:'ROE',value:percentage(roe),unit:'Theo báo cáo năm',delta:null,icon:Coins,tone:'orange'},
    {label:'ROA',value:percentage(model.roa!==null?model.roa*100:null),unit:'Tài sản bình quân',delta:null,icon:ShieldCheck,tone:'purple'},
    {label:model.isBank?'Biên lãi ròng (NIM)':'Biên lợi nhuận gộp',value:percentage(model.isBank?(finite(model.items.nim)?model.items.nim*100:null):model.grossMargin!==null?model.grossMargin*100:null),unit:basis,delta:model.isBank?null:model.marginChange,points:true,icon:Layers3,tone:'pink'},
    {label:'Tăng trưởng EPS',value:percentage(model.epsGrowth),unit:'So với năm trước',delta:null,icon:Activity,tone:'cyan'},
  ];
  const Legacy=({financials:window.StockAI.FinancialReports,technical:window.StockAI.TechnicalAnalysis,valuation:window.StockAI.ValuationAnalysis,news:window.StockAI.NewsAnalysis,risk:window.StockAI.RiskAnalysis,bullbear:window.StockAI.BullBearAnalysis} as any)[detail||''];
  const stock={symbol,backendAnalysis:data,financialReports:data?.financial_reports};
  const close=()=>{setDetail(null);onNavigate('technical');};
  useEffect(()=>{
    if(isSecond(activeTab)){setPage(2);setDetail(null);}
    else if(activeTab!=='technical'){setPage(1);setDetail(activeTab);}
  },[activeTab]);
  useEffect(()=>{onPageChange?.(page);},[page]);
  useEffect(()=>{
    if(!detail)return;
    const previous=document.activeElement as HTMLElement;
    closeRef.current?.focus();
    const key=(event:KeyboardEvent)=>{
      if(event.key==='Escape')close();
      if(event.key==='Tab'){
        const controls=Array.from(document.querySelectorAll<HTMLElement>('.analysis-detail-dialog button:not([disabled]),.analysis-detail-dialog a[href],.analysis-detail-dialog select,.analysis-detail-dialog input,.analysis-detail-dialog [tabindex="0"]'));
        const first=controls[0],last=controls.at(-1);
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
      }
    };
    window.addEventListener('keydown',key);
    return ()=>{window.removeEventListener('keydown',key);if(previous?.isConnected)previous.focus();};
  },[detail]);
  function download(){
    const blob=new Blob([exportStatements(data)],{type:'text/csv;charset=utf-8;'}),url=URL.createObjectURL(blob);
    const link=document.createElement('a');link.href=url;link.download=`${symbol}_BCTC_${data?.as_of||'snapshot'}.csv`;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  const trendText=tech.trend==='up'?'Giá trên SMA20 > SMA50':tech.trend==='down'?'Giá dưới SMA20 < SMA50':tech.trend==='mixed'?'Các đường giá đan xen':'Chưa đủ dữ liệu';
  return <div className="stock-analysis-page">
    <nav className="analysis-page-switch" aria-label="Trang phân tích"><button className={page===1?'active':''} aria-pressed={page===1} onClick={()=>{setPage(1);setDetail(null);}}>01 <span>Cơ bản & Kỹ thuật</span></button><button className={page===2?'active':''} aria-pressed={page===2} onClick={()=>{setPage(2);setDetail(null);}}>02 <span>Định giá & Rủi ro</span><ArrowRight size={14}/></button><small>Phân tích cổ phiếu · {page}/2</small></nav>
    {page===1&&<nav className="analysis-jump-nav" aria-label="Các mục phân tích">
      <button onClick={()=>fundamentalRef.current?.scrollIntoView({behavior:'smooth',block:'start'})}>Phân tích cơ bản</button>
      <button onClick={()=>technicalRef.current?.scrollIntoView({behavior:'smooth',block:'start'})}>Phân tích kỹ thuật</button>
      {[['dividends','Cổ tức'],['valuation','Định giá'],['news','Tin tức'],['risk','Rủi ro'],['bullbear','Bull & Bear']].map(([id,label])=><button key={id} onClick={()=>{if(isSecond(id)){setPage(2);onNavigate(id);}else setDetail(id);}}>{label}<ArrowRight size={11}/></button>)}
    </nav>}
    {page===1&&<>
    <section className="analysis-module fundamental-module" ref={fundamentalRef} aria-label="Phân tích cơ bản">
      <div className="analysis-module-heading"><BarChart3 size={26}/><h2>Phân tích cơ bản</h2><p>Chất lượng doanh nghiệp & hiệu quả kinh doanh · {basis}</p><div><button className="btn report-action" disabled={!data} onClick={()=>setDetail('financials')}><FileText size={15}/> Xem báo cáo tài chính</button><button className="btn download-data" disabled={!model.annual.length} onClick={download}><Download size={15}/> Tải dữ liệu</button></div></div>
      <div className="fundamental-kpis">{cards.map(card=><article key={card.label} className={`fundamental-kpi ${card.tone}`}><span className="kpi-icon"><card.icon size={23}/></span><div><h3>{card.label} <small>{card.label==='Tăng trưởng EPS'?'':basis}</small></h3><strong>{card.value}{card.value!=='—'&&['tỷ đồng','VND'].includes(card.unit)&&<small> {card.unit==='tỷ đồng'?'tỷ':'₫'}</small>}</strong><p className={finite(card.delta)?card.delta>=0?'positive':'negative':'muted'}>{finite(card.delta)?<>{card.delta>=0?<ArrowUpRight size={12}/>:<ArrowDownRight size={12}/>} {num(card.delta)}{card.points?' đpt':'%'} so năm trước</>:card.unit}</p></div></article>)}</div>
      <div className="fundamental-grid">
        <div className="statement-preview"><div className="analysis-subheading"><h3><FileText size={15}/> Báo cáo tài chính</h3><div className="statement-tabs">{[['income','KQKD'],['balance','Bảng cân đối'],['cashflow','Lưu chuyển tiền tệ']].map(([id,label])=><button key={id} className={statement===id?'active':''} onClick={()=>setStatement(id)}>{label}</button>)}</div></div><div className="statement-scroll"><table><thead><tr><th>Chỉ tiêu ({model.unit.label})</th>{columns.map((r:any)=><th key={r.period}>{r.period}</th>)}</tr></thead><tbody>{fields.map(([key,label])=><tr key={key}><th>{label}</th>{columns.map((r:any)=><td key={r.period}>{money(r.items?.[key])}</td>)}</tr>)}</tbody></table>{!columns.length&&<p className="analysis-empty">Chưa thu thập báo cáo tài chính cho mã {symbol}.</p>}</div><p className="analysis-source-note">Báo cáo năm đã công bố trước {data?.as_of||'ngày snapshot'}. Dấu —: chưa có dữ liệu.</p></div>
        <AnnualChart model={model}/>
        <aside className="fundamental-insights"><div className="analysis-subheading"><h3><Sparkles size={15}/> Nhận định từ dữ liệu</h3></div>
          {model.latest?<>
            <Insight title={finite(model.revenueGrowth)?`${model.revenueLabel} ${model.revenueGrowth>=0?'tăng':'giảm'} ${num(Math.abs(model.revenueGrowth))}%`:'Doanh thu năm gần nhất'} tone={model.revenueGrowth!==null&&model.revenueGrowth<0?'pink':'green'}>{basis}: {money(model.items[model.revenueKey])} {model.unit.label}.{model.previous?` So với ${model.previous.period}.`:' Chưa đủ dữ liệu so sánh năm trước.'}</Insight>
            <Insight title={model.isBank?'Cơ cấu thu nhập ngân hàng':'Biên lợi nhuận gộp'} tone="purple" icon={Layers3}>{model.isBank?'Chỉ tiêu ngân hàng được trình bày theo số liệu nguồn; không thay bằng biên gộp của doanh nghiệp sản xuất.':model.grossMargin!==null?`${basis}: ${num(model.grossMargin*100)}%. ${finite(model.marginChange)?`${model.marginChange>=0?'Tăng':'Giảm'} ${num(Math.abs(model.marginChange))} điểm phần trăm so năm trước.`:''}`:'Chưa có đủ doanh thu và lợi nhuận gộp để tính biên.'}</Insight>
            <Insight title={finite(model.items.cfo)?`Dòng tiền hoạt động ${model.items.cfo>=0?'dương':'âm'}`:'Dòng tiền hoạt động'} tone={finite(model.items.cfo)&&model.items.cfo<0?'pink':'cyan'} icon={Wallet}>Dòng tiền HĐKD {basis.toLowerCase()}: {money(model.items.cfo)} {model.unit.label}. {finite(model.cfoGrowth)?`Thay đổi ${num(model.cfoGrowth)}% so năm trước.`:'Chưa đủ cơ sở tính tăng trưởng dòng tiền.'}</Insight>
          </>:<p className="analysis-empty">Cần báo cáo tài chính để đưa ra nhận định cơ bản.</p>}
          <p className="analysis-source-note">Diễn giải theo quy tắc từ số liệu nguồn.</p>
        </aside>
      </div>
    </section>
    <section className="analysis-module technical-module" ref={technicalRef} aria-label="Phân tích kỹ thuật">
      <div className="analysis-module-heading"><TrendingUp size={27}/><h2>Phân tích kỹ thuật</h2><p>Theo dõi biến động giá, xu hướng và tín hiệu kỹ thuật</p><span className="analysis-snapshot-tag"><Activity size={13}/> Phiên cuối {data?.price_date||'—'}</span></div>
      <div className="technical-grid"><div className="technical-chart-container"><PriceChart rows={data?.price_history||[]} symbol={symbol} advanced/><p className="analysis-source-note">SMA/Bollinger/RSI/MACD trên biểu đồ tính từ tối đa 252 phiên có sẵn; số chỉ báo bên phải lấy từ toàn bộ lịch sử của backend.</p></div>
        <aside className="technical-insights"><div className="analysis-subheading"><h3><Activity size={15}/> Tín hiệu kỹ thuật</h3><button className="text-btn" onClick={()=>setDetail('technical')}>Xem chi tiết <ArrowRight size={13}/></button></div><div className="technical-signals">
          <article className={`signal-tile ${tech.macdDirection==='above'?'green':tech.macdDirection==='below'?'pink':'cyan'}`}><span>MACD (12,26,9)</span><strong>{num(tech.macd)}</strong><small>{tech.macdDirection==='above'?'Trên đường tín hiệu':tech.macdDirection==='below'?'Dưới đường tín hiệu':tech.macdDirection==='equal'?'Bằng đường tín hiệu':'Chưa đủ dữ liệu'}</small></article>
          <article className="signal-tile purple"><span>RSI (14)</span><strong>{num(tech.rsi)}</strong><small>{tech.rsiLabel}</small></article>
          <article className={`signal-tile ${tech.trend==='down'?'pink':tech.trend==='up'?'green':'cyan'}`}><span>Xu hướng SMA</span><strong>{tech.trend==='up'?'Hướng lên':tech.trend==='down'?'Hướng xuống':tech.trend==='mixed'?'Đan xen':'—'}</strong><small>{trendText}</small></article>
        </div><div className="price-levels"><article><ShieldCheck size={21}/><div><span>Đáy {tech.rangeSessions} phiên gần nhất</span><strong>{num(tech.low,0)} <small>₫</small></strong></div></article><article><Layers3 size={21}/><div><span>Đỉnh {tech.rangeSessions} phiên gần nhất</span><strong>{num(tech.high,0)} <small>₫</small></strong></div></article></div>
          <div className="technical-commentary"><h3><Sparkles size={16}/> Nhận định kỹ thuật</h3><p>{tech.trend==='up'?`Giá đóng cửa ${num(tech.close,0)}₫ đang trên SMA20 và SMA50.`:tech.trend==='down'?`Giá đóng cửa ${num(tech.close,0)}₫ đang dưới SMA20 và SMA50.`:tech.trend==='mixed'?'Quan hệ giá và các đường trung bình chưa tạo thứ tự xu hướng rõ ràng.':'Chưa có đủ dữ liệu để xác định xu hướng SMA.'}</p><p>{tech.rsi!==null?`RSI ở mức ${num(tech.rsi)} · ${tech.rsiLabel.toLowerCase()}.`:'Chưa đủ dữ liệu RSI.'} {tech.macdDirection==='above'?'MACD đang trên đường tín hiệu.':tech.macdDirection==='below'?'MACD đang dưới đường tín hiệu.':''}</p><p className="analysis-source-note">Tín hiệu theo quy tắc, không phải dự báo AI hoặc khuyến nghị mua/bán. Đỉnh/đáy là vùng giá đã quan sát.</p></div>
        </aside>
      </div>
    </section>
    </>}
    {page===2&&<ValuationRiskPage data={data} symbol={symbol} onDetail={setDetail}/>}
    {detail&&(Legacy||detail==='dividends')&&<div className="modal-backdrop" onClick={close}><section className="analysis-detail-dialog" role="dialog" aria-modal="true" aria-label="Chi tiết phân tích cổ phiếu" onClick={e=>e.stopPropagation()}><div className="panel-heading"><h2><FileText size={16}/> {symbol} · Chi tiết phân tích</h2><button ref={closeRef} className="icon-btn" aria-label="Đóng chi tiết phân tích" onClick={close}><X size={19}/></button></div><div className="legacy-panel">{detail==='dividends'?<DividendsPanel data={data} symbol={symbol}/>:<Legacy react={React} jsx={jsx} stock={stock}/>}</div></section></div>}
  </div>;
}
