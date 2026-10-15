import {Coins} from 'lucide-react';
import {useState} from 'react';
export function DividendsPanel({data,symbol}:any){
  const [kind,setKind]=useState('all');
  const source=data?.ticker===symbol?data.dividends:null;
  const events=(source?.events||[]).filter((e:any)=>kind==='all'||e.kind===kind);
  const n=(v:any)=>typeof v==='number'&&Number.isFinite(v)?v.toLocaleString('vi-VN',{maximumFractionDigits:2}):'—';
  return <section className="dividends-panel"><div className="analysis-subheading"><h3><Coins size={17}/> Lịch sử cổ tức & quyền · {symbol}</h3><select aria-label="Loại cổ tức" value={kind} onChange={e=>setKind(e.target.value)}><option value="all">Tất cả</option><option value="cash">Tiền mặt</option><option value="stock">Cổ phiếu / quyền</option></select></div><p className="analysis-source-note">Theo kho dữ liệu {source?.source||'chưa xác định'} · Ngày GDKHQ không sau snapshot {data?.as_of||'—'}. Chưa tính cổ tức vào biểu đồ lợi nhuận danh mục.</p><div className="statement-scroll"><table><thead><tr><th>Ngày GDKHQ</th><th>Loại</th><th>Nội dung</th><th>Tiền mặt / CP (VND)</th><th>Tỷ lệ (%)</th><th>Ngày thanh toán</th></tr></thead><tbody>{events.map((e:any,i:number)=><tr key={`${e.ex_date}/${i}`}><td>{e.ex_date}</td><td>{e.kind==='cash'?'Tiền mặt':e.kind==='stock'?'Cổ phiếu / quyền':e.kind||'—'}</td><td>{e.title||'—'}</td><td>{n(e.dps_vnd)}</td><td>{n(e.percent_of_par)}</td><td>{e.pay_date||'Chưa có'}</td></tr>)}</tbody></table></div>{!events.length&&<p className="analysis-empty">Chưa có sự kiện phù hợp trong dữ liệu đã thu thập.</p>}<p className="analysis-source-note">Tỷ lệ giữ nguyên đơn vị nguồn; lịch sử đã xảy ra không phải lịch sự kiện sắp tới. Kho dữ liệu có thể được cập nhật sau ngày snapshot.</p></section>;
}
