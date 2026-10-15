import React from 'react';
import {CircleHelp} from 'lucide-react';

export function factorScore(data:any,key:string,module:string) {
  if (!data) return null;
  if (data.quality_gate?.scored !== false) return data.scores?.[key] ?? null;
  const result=data.modules?.[module];
  // An overall quality gate does not discard a separately computed module score.
  // Never substitute neutral scores for modules that failed or have no score.
  return ['ok','partial'].includes(result?.status) && Number.isFinite(result.score) ? result.score : null;
}

export function factorLabel(data:any,key:string,module:string) {
  if (!data) return 'Đang tải dữ liệu';
  if (factorScore(data,key,module) !== null) return data.quality_gate?.scored===false ? 'Điểm riêng · Chưa xếp hạng' : key==='R'?'Điểm rủi ro':'Điểm thành phần';
  return ({F:'Chưa có điểm cơ bản',T:'Chưa đủ lịch sử giá',V:'Chưa đủ dữ liệu định giá',S:'Chưa đủ tin tức',R:'Chưa đủ dữ liệu rủi ro'} as any)[key];
}

const reasons:Record<string,string>={
  illiquid:'Thanh khoản không đạt ngưỡng xếp hạng',
  low_liquidity:'Thanh khoản thấp',
  prices_lt_750:'Lịch sử giá chưa đủ 750 phiên theo tiêu chí chất lượng hiện tại',
  annual_lt_3:'Chưa đủ 3 báo cáo tài chính năm',
  annual_lt_5:'Chưa đủ 5 báo cáo tài chính năm',
  news_few:'Số tin tức thu thập còn ít',
};

export function CatalogAvailability({item}:{item:any}) {
  if (item.quality_tier!=='insufficient') return null;
  return <small className="catalog-warning">Chưa xếp hạng{item.collection_incomplete?' · Thu thập chưa đầy đủ':''}</small>;
}

export function DataAvailability({data}:{data:any}) {
  if (!data) return null;
  const details=data.data_availability || {};
  const prices=details.price_sessions ?? data.price_history?.length ?? 0;
  const annual=details.annual_reports ?? data.financial_reports?.annual?.length ?? 0;
  const quarterly=details.quarterly_reports ?? data.financial_reports?.quarterly?.length ?? 0;
  const news=details.news_articles ?? data.news?.length ?? 0;
  const unranked=data.quality_gate?.scored===false;
  const olderPrice=data.price_date && data.price_date!==data.as_of;
  if (!unranked && annual+quarterly>0 && prices>0 && news>0 && !olderPrice) return null;
  const why=(data.quality_gate?.reasons || []).map((reason:string)=>reasons[reason] || 'Chưa đạt một tiêu chí chất lượng dữ liệu');
  return <section className="data-availability" aria-label="Tình trạng dữ liệu cổ phiếu" role="status">
    <CircleHelp size={20}/>
    <div>
      <h2>{data.ticker} · {unranked?'Chưa đủ điều kiện xếp hạng':'Dữ liệu có phần chưa đầy đủ'}</h2>
      {why.length>0 && <p>{why.join('. ')}. {unranked?'Điểm tổng hợp và giá mục tiêu chưa được công bố.':''}</p>}
      {details.collection_incomplete && <p>Lần thu thập trước dừng sớm sau bước kiểm tra giá/thanh khoản; báo cáo tài chính và tin tức chưa được tải đầy đủ.</p>}
      {!prices && <p>Snapshot hiện tại chưa có lịch sử giá để hiển thị biểu đồ.</p>}
      {olderPrice && <p>Giá gần nhất có trong dữ liệu: {data.price_date}; ngày snapshot: {data.as_of}.</p>}
      <div className="availability-pills">
        <span className={prices?'available':'missing'}>Giá: {prices?`${prices.toLocaleString('vi-VN')} phiên`:'chưa có'}</span>
        <span className={annual+quarterly?'available':'missing'}>BCTC: {annual+quarterly?`${annual} năm · ${quarterly} quý`:'chưa có'}</span>
        <span className={news?'available':'missing'}>Tin tức: {news?`${news} bài nguồn`:'chưa có'}</span>
      </div>
      {unranked && <p className="subtle">Biểu đồ và điểm riêng của các mô-đun vẫn hiển thị nếu có dữ liệu; chúng không tạo thành khuyến nghị đầu tư cho mã này.</p>}
    </div>
  </section>;
}
