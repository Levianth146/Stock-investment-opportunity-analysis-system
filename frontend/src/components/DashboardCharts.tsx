import React, {useId, useMemo, useState} from 'react';
import {Maximize2, Minimize2} from 'lucide-react';
type Row={date:string;open?:number;high?:number;low?:number;close:number;volume?:number};
const num=(v:any)=>Number.isFinite(v)?v.toLocaleString('vi-VN',{maximumFractionDigits:2}):'—';
const ranges={'1m':21,'3m':63,'6m':126,'1y':252};
function average(rows:Row[],period:number){return rows.map((_,i)=>i+1<period?null:rows.slice(i-period+1,i+1).reduce((n,r)=>n+r.close,0)/period);}
function ema(values:number[],period:number){const a=2/(period+1);let prev=values[0]||0;return values.map(v=>(prev=v*a+prev*(1-a)));}
function rsi(rows:Row[]){let gain=0,loss=0;return rows.map((r,i)=>{if(!i)return null;const change=r.close-rows[i-1].close;if(i<=14){gain+=Math.max(0,change)/14;loss+=Math.max(0,-change)/14;}else{gain=(gain*13+Math.max(0,change))/14;loss=(loss*13+Math.max(0,-change))/14;}return i<14?null:loss===0?(gain===0?50:100):100-100/(1+gain/loss);});}
export function PriceChart({rows,symbol,advanced=false}:{rows:Row[];symbol:string;advanced?:boolean}){
  const id=useId().replace(/:/g,''),[range,setRange]=useState<keyof typeof ranges>('3m'),[kind,setKind]=useState('candles'),[overlay,setOverlay]=useState('MA'),[expanded,setExpanded]=useState(false);
  const [hover,setHover]=useState<{index:number;rows:Row[];range:string}|null>(null);
  const [movingAverages,setMovingAverages]=useState([20,50]),[bollinger,setBollinger]=useState(false),[volume,setVolume]=useState(true);
  const history=useMemo(()=>rows.filter(r=>r.date&&Number.isFinite(r.close)).sort((a,b)=>a.date.localeCompare(b.date)),[rows]);
  const offset=Math.max(0,history.length-ranges[range]),points=history.slice(offset);
  const selected=hover?.rows===rows&&hover.range===range?points[hover.index]:null;
  const ma20=useMemo(()=>average(history,20),[history]),ma50=useMemo(()=>average(history,50),[history]),ma200=useMemo(()=>average(history,200),[history]);
  const bands=useMemo(()=>history.map((_,i)=>{
    const mean=ma20[i];if(mean===null)return null;
    const deviation=Math.sqrt(history.slice(i-19,i+1).reduce((sum,row)=>sum+(row.close-mean)**2,0)/20);
    return {upper:mean+2*deviation,lower:mean-2*deviation};
  }),[history,ma20]);
  const showMA=(period:number)=>advanced?movingAverages.includes(period):overlay==='MA'&&period!==200;
  const indicator=useMemo(()=>{
    if(overlay==='RSI')return rsi(history);
    const closes=history.map(r=>r.close),fast=ema(closes,12),slow=ema(closes,26);
    return fast.map((v,i)=>i<25?null:v-slow[i]);
  },[history,overlay]);
  const hasOscillator=overlay==='RSI'||overlay==='MACD';
  const all=points.flatMap((r,i)=>[r.close,r.low,r.high,...(showMA(20)?[ma20[i+offset]]:[]),...(showMA(50)?[ma50[i+offset]]:[]),...(showMA(200)?[ma200[i+offset]]:[]),...(advanced&&bollinger?[bands[i+offset]?.upper,bands[i+offset]?.lower]:[])]).filter((n):n is number=>typeof n==='number'&&Number.isFinite(n));
  const min=all.length?Math.min(...all):0,max=all.length?Math.max(...all):1,pad=(max-min)*.12||max*.02||1;
  const lo=min-pad,hi=max+pad,w=900,left=18,right=815,top=22,priceBottom=hasOscillator?(volume?195:248):(volume?250:323),volumeTop=hasOscillator?208:270,volumeBottom=hasOscillator?248:323;
  const x=(i:number)=>left+(i+.5)/Math.max(1,points.length)*(right-left),y=(v:number)=>top+(hi-v)/(hi-lo)*(priceBottom-top);
  const maxVolume=Math.max(1,...points.map(r=>Number.isFinite(r.volume)?r.volume!:0));
  const line=(values:(number|null)[],scale:(n:number)=>number)=>{let result='',connected=false;values.forEach((v,i)=>{if(v===null||!Number.isFinite(v)){connected=false;return;}result+=`${connected?'L':'M'}${x(i)},${scale(v)} `;connected=true;});return result;};
  const choose=(i:number)=>setHover({index:Math.max(0,Math.min(points.length-1,i)),rows,range});
  const handlePointer=(e:React.PointerEvent<SVGSVGElement>)=>{const m=e.currentTarget.getScreenCTM();if(!m)return;const p=e.currentTarget.createSVGPoint();p.x=e.clientX;p.y=e.clientY;const local=p.matrixTransform(m.inverse());choose(Math.floor((local.x-left)/(right-left)*points.length));};
  const last=selected||points.at(-1),indicatorValues=indicator.slice(offset),validIndicators=indicatorValues.filter((v):v is number=>v!==null&&Number.isFinite(v));
  const indLo=overlay==='RSI'?0:Math.min(0,...validIndicators),indHi=overlay==='RSI'?100:Math.max(0,...validIndicators);
  const iy=(v:number)=>270+(indHi-v)/(indHi-indLo||1)*48;
  const dateLabel=(value:string)=>{const [year,month,day]=value.split('-');return `${day}/${month}/${year}`;};
  return <div className={`price-chart ${expanded?'expanded':''}`}>
    <div className="chart-toolbar"><div className="chart-ranges">{Object.keys(ranges).map(key=><button key={key} className={range===key?'active':''} onClick={()=>{setRange(key as keyof typeof ranges);setHover(null);}}>{key==='1y'?'1 năm':`${key[0]} tháng`}</button>)}</div><div className="chart-options"><button className={kind==='candles'?'active':''} onClick={()=>setKind(kind==='candles'?'line':'candles')}>{kind==='candles'?'Nến':'Đường'}</button>{advanced&&[20,50,200].map(period=><button key={period} aria-pressed={movingAverages.includes(period)} className={movingAverages.includes(period)?'active':''} onClick={()=>setMovingAverages(current=>current.includes(period)?current.filter(p=>p!==period):[...current,period])}>SMA{period}</button>)}{(advanced?['RSI','MACD']:['MA','RSI','MACD']).map(key=><button key={key} className={overlay===key?'active':''} onClick={()=>setOverlay(overlay===key?'':key)}>{key}</button>)}{advanced&&<><button aria-pressed={bollinger} className={bollinger?'active':''} onClick={()=>setBollinger(!bollinger)}>Bollinger</button><button aria-pressed={volume} className={volume?'active':''} onClick={()=>setVolume(!volume)}>Volume</button></>}<button aria-label={expanded?'Thu nhỏ biểu đồ':'Phóng to biểu đồ'} onClick={()=>setExpanded(!expanded)}>{expanded?<Minimize2 size={14}/>:<Maximize2 size={14}/>}</button></div></div>
    <div className="ohlc-bar"><b>{symbol}</b><span>{last?dateLabel(last.date):'Chưa có dữ liệu'}</span>{[['O',last?.open],['H',last?.high],['L',last?.low],['C',last?.close],['Vol',last?.volume]].map(([key,value])=><span key={String(key)}>{key} <strong>{num(value)}</strong></span>)}</div>
    {!points.length?<div className="chart-empty">Chưa có dữ liệu lịch sử giá.</div>:<svg className="market-chart" viewBox="0 0 900 356" role="img" aria-label={`Biểu đồ giá và khối lượng ${symbol}`} tabIndex={0} onPointerMove={handlePointer} onPointerDown={handlePointer} onPointerLeave={()=>setHover(null)} onBlur={()=>setHover(null)} onFocus={()=>choose(points.length-1)} onKeyDown={e=>{if(['ArrowLeft','ArrowRight','Home','End','Escape'].includes(e.key)){e.preventDefault();if(e.key==='Escape')setHover(null);else choose(e.key==='Home'?0:e.key==='End'?points.length-1:(hover?.index??points.length-1)+(e.key==='ArrowLeft'?-1:1));}}}>
      <desc>Trỏ chuột hoặc chạm để xem ngày, giá OHLC và khối lượng. Dùng phím mũi tên để chọn phiên.</desc><defs><linearGradient id={`${id}-area`} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#00D9FF" stopOpacity=".22"/><stop offset="1" stopColor="#00D9FF" stopOpacity="0"/></linearGradient><clipPath id={`${id}-clip`}><rect x={left} y={top} width={right-left} height={priceBottom-top}/></clipPath></defs>
      <rect width={w} height={356} fill="transparent"/>
      {[0,1,2,3,4].map(i=>{const py=top+i*(priceBottom-top)/4;return <g key={i}><line x1={left} x2={right} y1={py} y2={py} stroke="#365b87" opacity=".5" strokeDasharray="3 5"/><text x={830} y={py+4} fill="#b9cbe3" fontSize={12}>{num(hi-i*(hi-lo)/4)}</text></g>;})}
      {[0,1,2,3,4].map(i=>{const index=Math.round(i*(points.length-1)/4);return <g key={i}><line x1={x(index)} x2={x(index)} y1={top} y2={volumeBottom} stroke="#365b87" opacity=".3"/><text x={x(index)} y={344} fill="#b9cbe3" fontSize={12} textAnchor={i===0?'start':i===4?'end':'middle'}>{points[index].date.slice(5)}</text></g>;})}
      <g clipPath={`url(#${id}-clip)`}>{kind==='line'?<><path d={`${line(points.map(r=>r.close),y)}L${x(points.length-1)},${priceBottom} L${x(0)},${priceBottom} Z`} fill={`url(#${id}-area)`}/><path d={line(points.map(r=>r.close),y)} fill="none" stroke="#00D9FF" strokeWidth={2}/></>:points.map((r,i)=>{const up=r.close>=(r.open??r.close),color=up?'#00E5A0':'#FF426B',width=Math.max(1,Math.min(9,(right-left)/points.length*.65));return <g key={r.date}>{Number.isFinite(r.high)&&Number.isFinite(r.low)&&<line x1={x(i)} x2={x(i)} y1={y(r.high!)} y2={y(r.low!)} stroke={color}/>}<rect x={x(i)-width/2} y={Math.min(y(r.open??r.close),y(r.close))} width={width} height={Math.max(1,Math.abs(y(r.open??r.close)-y(r.close)))} fill={color}/></g>;})}
      {showMA(20)&&<path data-indicator="SMA20" d={line(ma20.slice(offset),y)} fill="none" stroke="#00B8FF" strokeWidth={1.3}/>}
      {showMA(50)&&<path data-indicator="SMA50" d={line(ma50.slice(offset),y)} fill="none" stroke="#FFB547" strokeWidth={1.3}/>}
      {showMA(200)&&<path data-indicator="SMA200" d={line(ma200.slice(offset),y)} fill="none" stroke="#A855F7" strokeWidth={1.3}/>}
      {advanced&&bollinger&&<g data-indicator="Bollinger"><path d={line(bands.slice(offset).map(b=>b?.upper??null),y)} fill="none" stroke="#7C8CF8" strokeWidth={1} strokeDasharray="3 3"/><path d={line(bands.slice(offset).map(b=>b?.lower??null),y)} fill="none" stroke="#7C8CF8" strokeWidth={1} strokeDasharray="3 3"/></g>}</g>
      {volume&&points.map((r,i)=>Number.isFinite(r.volume)?<rect data-volume="true" key={`v-${r.date}`} x={x(i)-Math.max(1,(right-left)/points.length*.65)/2} y={volumeBottom-(r.volume!/maxVolume)*(volumeBottom-volumeTop)} width={Math.max(1,(right-left)/points.length*.65)} height={Math.max(0,r.volume!/maxVolume*(volumeBottom-volumeTop))} fill={r.close>=(r.open??r.close)?'#00E5A0':'#FF426B'} opacity={.5}/>:null)}
      {volume&&<text x={left+4} y={volumeTop+10} fill="#9bafca" fontSize={11}>KHỐI LƯỢNG</text>}
      {hasOscillator&&<><text x={left+4} y={268} fill="#b9cbe3" fontSize={12}>{overlay}{overlay==='MACD'?' (12,26)':' (14)'}</text><line x1={left} x2={right} y1={iy(overlay==='RSI'?50:0)} y2={iy(overlay==='RSI'?50:0)} stroke="#365b87"/><path d={line(indicatorValues,iy)} fill="none" stroke="#A855F7" strokeWidth={1.5}/><text x={830} y={286} fill="#b9cbe3" fontSize={12}>{num(indHi)}</text><text x={830} y={318} fill="#b9cbe3" fontSize={12}>{num(indLo)}</text></>}
      {selected&&hover&&<g pointerEvents="none"><line x1={x(hover.index)} x2={x(hover.index)} y1={top} y2={volumeBottom} stroke="#b9cbe3" strokeDasharray="4 4"/><line x1={left} x2={right} y1={y(selected.close)} y2={y(selected.close)} stroke="#b9cbe3" opacity=".4" strokeDasharray="4 4"/><circle cx={x(hover.index)} cy={y(selected.close)} r={4} fill="#00D9FF" stroke="#11213a" strokeWidth={2}/><g role="status" aria-live="polite" transform={`translate(${Math.max(left,Math.min(right-202,x(hover.index)+12))},${Math.max(top,Math.min(priceBottom-76,y(selected.close)-80))})`}><rect width={202} height={74} rx={6} fill="#294d75" stroke="#2563FF"/><text x={12} y={19} fontSize={13} fill="#F5F8FF">{dateLabel(selected.date)} · {symbol}</text><text x={12} y={40} fontSize={16} fontWeight="800" fill="#00D9FF">{num(selected.close)} VND/cổ phiếu</text><text x={12} y={60} fontSize={12} fill="#b9cbe3">Khối lượng: {num(selected.volume)}</text></g></g>}
    </svg>}
    <div className="chart-legend"><span><i style={{background:'#00E5A0'}}/>Giá OHLC</span>{showMA(20)&&<span><i style={{background:'#00B8FF'}}/>SMA20</span>}{showMA(50)&&<span><i style={{background:'#FFB547'}}/>SMA50</span>}{showMA(200)&&<span><i style={{background:'#A855F7'}}/>SMA200</span>}{advanced&&bollinger&&<span>Bollinger (20, 2σ)</span>}<span className="chart-hint">{points.length} phiên · VND/cổ phiếu · Rê chuột để xem giá</span></div>
  </div>;
}
export function ScoreRadar({scores}:{scores:any}){
  const labels=['Cơ bản (F)','Kỹ thuật (T)','Định giá (V)','Tin tức (S)','Rủi ro (R)'],keys=['F','T','V','S','R'],colors=['#00E5A0','#A855F7','#00B8FF','#FF9B38','#FF426B'];
  const point=(i:number,r:number)=>{const angle=-Math.PI/2+i*2*Math.PI/5;return [150+Math.cos(angle)*r,145+Math.sin(angle)*r];};
  const polygon=(r:number)=>keys.map((_,i)=>point(i,r).join(',')).join(' ');
  const complete=keys.every(k=>Number.isFinite(scores?.[k]));
  return <svg className="score-radar" viewBox="0 0 300 285" role="img" aria-label="Radar điểm F T V S R"><defs><linearGradient id="radar-fill" x1="0" x2="1"><stop stopColor="#00D9FF" stopOpacity=".35"/><stop offset="1" stopColor="#8B2CF5" stopOpacity=".2"/></linearGradient></defs>{[.25,.5,.75,1].map(scale=><polygon key={scale} points={polygon(86*scale)} fill="none" stroke="#365b87"/>)}{keys.map((key,i)=>{const [x,y]=point(i,86),[tx,ty]=point(i,113);return <g key={key}><line x1={150} y1={145} x2={x} y2={y} stroke="#365b87"/><text x={tx} y={ty-5} textAnchor="middle" fontSize={12} fill="#b9cbe3">{labels[i]}</text><text x={tx} y={ty+14} textAnchor="middle" fontSize={17} fontWeight="800" fill={colors[i]}>{num(scores?.[key])}</text></g>;})}{complete?<><polygon points={keys.map((key,i)=>point(i,Math.max(0,Math.min(100,scores[key]))*.86).join(',')).join(' ')} fill="url(#radar-fill)" stroke="#00D9FF" strokeWidth={1.3}/>{keys.map((key,i)=>{const [cx,cy]=point(i,Math.max(0,Math.min(100,scores[key]))*.86);return <circle key={key} cx={cx} cy={cy} r={3} fill={colors[i]}/>;})}</>:<text x={150} y={145} fill="#b9cbe3" fontSize={13} textAnchor="middle">Chưa đủ điểm thành phần</text>}</svg>;
}
