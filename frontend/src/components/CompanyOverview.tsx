import {DividendsPanel} from './DividendsPanel';
import React, {useEffect, useRef, useState} from 'react';
import {ArrowRight, Building2, CalendarDays, ExternalLink, Globe2, Layers3, X} from 'lucide-react';

const readableDate=(value:string|null)=>value?value.slice(0,10).split('-').reverse().join('/'):'Chưa có dữ liệu';
const exchangeName=(value:string)=>value==='HSX'?'HOSE':value||'Chưa có dữ liệu';

function CompanyIllustration({symbol}:{symbol:string}) {
  return <div className="company-illustration" aria-hidden="true"><svg viewBox="0 0 230 145">
    <defs><linearGradient id="building-front" x1="0" x2="1"><stop stopColor="#294d75"/><stop offset="1" stopColor="#153461"/></linearGradient><linearGradient id="building-side"><stop stopColor="#2563FF" stopOpacity=".4"/><stop offset="1" stopColor="#8B2CF5" stopOpacity=".4"/></linearGradient></defs>
    <path d="M0 127L230 100V145H0Z" fill="#152a46"/>
    <path d="M70 29L142 11L142 123L70 136Z" fill="url(#building-front)" stroke="#488CDE" strokeWidth=".6"/>
    <path d="M142 11L184 35V131L142 123Z" fill="url(#building-side)" stroke="#8058E6" strokeWidth=".6"/>
    <path d="M24 77L70 61V136L24 127Z" fill="#1d385a" stroke="#2563FF" strokeWidth=".5"/>
    {[0,1,2,3,4].map(i=><g key={i}><path d={`M${80+i*12} ${27-i*3}V${133-i*2}`} stroke="#00D9FF" opacity={.35}/><path d={`M146 ${32+i*17}L181 ${51+i*15}`} stroke="#A855F7" opacity={.6}/></g>)}
    {[0,1,2,3,4,5].map(i=><path key={i} d={`M73 ${43+i*14}L140 ${26+i*15}`} stroke="#4289D4" opacity={.5}/>)}
    <rect x="82" y="74" width="51" height="25" rx="3" fill="#2563FF" opacity={.85}/><text x="107" y="91" fill="white" fontSize="17" fontFamily="Inter,sans-serif" fontWeight="900" textAnchor="middle">{symbol}</text>
    <path d="M0 139L225 117M13 145L230 126" stroke="#00D9FF" opacity={.25}/>
    <circle cx="35" cy="42" r="2" fill="#00D9FF"/><circle cx="201" cy="69" r="1.5" fill="#A855F7"/>
  </svg><span>Hình minh họa</span></div>;
}

export function CompanyOverview({data,symbol,loading}:{data:any;symbol:string;loading:boolean}) {
  const [open,setOpen]=useState(false);
  const closeRef=useRef<HTMLButtonElement>(null),triggerRef=useRef<HTMLButtonElement>(null);
  const profile=data?.ticker===symbol?data?.company_profile:null;
  const company=data?.ticker===symbol?data?.company:null;
  const name=profile?.name||company?.name||symbol;
  const description=profile?.description;
  const sector=profile?.industry||profile?.sector||company?.sector||'Chưa có dữ liệu';
  const exchange=exchangeName(profile?.exchange||company?.exchange);
  const website=/^https?:\/\//i.test(profile?.website||'')?profile.website:null;
  const facts=[{label:'Thành lập',value:profile?.founded_year||'Chưa có dữ liệu',icon:CalendarDays,color:'purple'},
    {label:'Ngành',value:sector,icon:Building2,color:'blue'},
    {label:'Sàn giao dịch',value:exchange,icon:Globe2,color:'green'},
    {label:'Ngày niêm yết',value:readableDate(profile?.listing_date),icon:Layers3,color:'orange'}];
  useEffect(()=>{setOpen(false);},[symbol]);
  useEffect(()=>{
    if(!open)return;
    const previous=document.activeElement as HTMLElement;
    closeRef.current?.focus();
    const key=(event:KeyboardEvent)=>{
      if(event.key==='Escape')setOpen(false);
      if(event.key==='Tab') {
        const elements=Array.from(document.querySelectorAll<HTMLElement>('.company-detail-dialog button,.company-detail-dialog a[href]'));
        const first=elements[0],last=elements.at(-1);
        if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}
        else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}
      }
    };
    window.addEventListener('keydown',key);
    return ()=>{window.removeEventListener('keydown',key);previous?.isConnected&&previous.focus();};
  },[open]);
  return <>
    <section className="company-overview" aria-label={`Tổng quan doanh nghiệp ${symbol}`}>
      <CompanyIllustration symbol={symbol}/>
      <div className="company-overview-content"><div className="company-overview-heading"><h2><Building2 size={16}/> Tổng quan doanh nghiệp</h2><button ref={triggerRef} disabled={!data||loading} onClick={()=>setOpen(true)}>Xem chi tiết doanh nghiệp <ArrowRight size={13}/></button></div>
        <p className="company-description">{loading?'Đang tải thông tin doanh nghiệp…':description||`${name}${company?.sector?` hoạt động trong ngành ${company.sector}`:''}${company?.exchange?`, giao dịch trên sàn ${exchangeName(company.exchange)}`:''}. Chưa có bài giới thiệu chi tiết trong dữ liệu đã thu thập.`}</p>
        <div className="company-facts">{facts.map(f=><div key={f.label} className={`company-fact ${f.color}`}><f.icon size={20}/><div><span>{f.label}</span><strong title={String(f.value)}>{loading?'Đang tải…':f.value}</strong></div></div>)}</div>
      </div>
    </section>
    {open&&<div className="modal-backdrop" onClick={()=>setOpen(false)}><section className="company-detail-dialog" role="dialog" aria-modal="true" aria-labelledby="company-detail-title" onClick={event=>event.stopPropagation()}><div className="panel-heading"><h2 id="company-detail-title"><Building2 size={18}/>{name} · {symbol}</h2><button ref={closeRef} className="icon-btn" aria-label="Đóng chi tiết doanh nghiệp" onClick={()=>setOpen(false)}><X size={19}/></button></div><div className="company-detail-body"><h3>Giới thiệu doanh nghiệp</h3><p>{description||'Chưa có bài giới thiệu chi tiết trong dữ liệu đã thu thập.'}</p><dl>{facts.map(f=><div key={f.label}><dt>{f.label}</dt><dd>{f.value}</dd></div>)}<div><dt>Cổ phiếu lưu hành</dt><dd>{Number.isFinite(company?.shares_outstanding)?company.shares_outstanding.toLocaleString('vi-VN'):'Chưa có dữ liệu'}</dd></div>{profile?.address&&<div><dt>Địa chỉ</dt><dd>{profile.address}</dd></div>}{website&&<div><dt>Website</dt><dd><a href={website} target="_blank" rel="noreferrer">{website}<ExternalLink size={13}/></a></dd></div>}</dl><DividendsPanel data={data} symbol={symbol}/><p className="subtle">{profile?.source_note||'Thông tin theo dữ liệu doanh nghiệp hiện có. Các trường chưa thu thập được để trống.'}</p></div></section></div>}
  </>;
}
