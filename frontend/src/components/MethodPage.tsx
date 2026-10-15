import {useEffect, useState} from 'react';
import {Gauge} from 'lucide-react';

interface Scoring {
  profiles?: Record<string, {weights: Record<string, number>; lambda_R: number}>;
  risk_reference?: number;
  ratings?: Array<{min: number; label: string}>;
  risk_gate?: {R_threshold: number; max_rating: string};
  data_gate?: {limited_max_rating?: string; implausible_upside_pct?: number; implausible_max_rating?: string};
}

const PILLARS: Array<[string, string, string]> = [
  ['F', 'Cơ bản (M2)', 'ROE, tăng trưởng doanh thu và lợi nhuận, biên lợi nhuận, đòn bẩy, dòng tiền từ báo cáo tài chính.'],
  ['T', 'Kỹ thuật (M3)', 'Xu hướng (MA20/50/200), động lượng (RSI, MACD), khối lượng, biến động (ATR) trên giá đóng cửa.'],
  ['V', 'Định giá (M4)', 'P/E và P/B so với trung vị ngành; giá tham chiếu = bội số trung vị ngành × EPS hoặc BVPS.'],
  ['S', 'Tin tức (M5)', 'Sắc thái tin tức gần đây theo tiêu đề; thiếu tin thì dùng điểm trung tính 50.'],
  ['R', 'Rủi ro (M6)', 'Biến động, sụt giảm tối đa, VaR/CVaR, beta so với VN-Index. Điểm càng cao càng rủi ro.'],
];
const NAMES: Record<string, string> = {long_term: 'Dài hạn', swing: 'Lướt sóng'};

/** Phương pháp chấm điểm — cấu hình đọc từ /api/meta (config/scoring.yaml). */
export function MethodPage() {
  const [sc, setSc] = useState<Scoring | null>(null);
  const [meta, setMeta] = useState<{asof?: string; formula?: string} | null>(null);
  const [err, setErr] = useState('');
  useEffect(() => {
    let on = true;
    fetch('/api/meta').then(r => {if (!r.ok) throw Error(`HTTP ${r.status}`); return r.json();})
      .then(b => {if (on) {setSc(b.scoring || null); setMeta({asof: b.asof, formula: b.formula});}})
      .catch(() => {if (on) setErr('Không tải được cấu hình chấm điểm.');});
    return () => {on = false;};
  }, []);
  const rref = sc?.risk_reference ?? 50;
  const profiles = Object.entries(sc?.profiles || {});
  return <div className="method-page">
    <section className="panel"><div className="panel-heading"><h2><Gauge size={16}/> Phương pháp chấm điểm</h2></div>
      <p className="subtle">Mỗi mã được chấm trên 5 trụ cột rồi gộp thành điểm 0–100. Trọng số là giá trị minh họa, chưa được hiệu chỉnh hay kiểm định lại bằng dữ liệu lịch sử.</p>
      <h3>Công thức</h3>
      <pre className="method-formula">{`Điểm = 50 + Σ wₖ·(Xₖ − 50) − λ_R·(R − ${rref})\nvới X ∈ {F, T, V, S}, giới hạn trong [0, 100]`}</pre>
      <p className="subtle">Mức 50 là trung tính: trụ cột trên 50 cộng điểm, dưới 50 trừ điểm. Rủi ro R chỉ làm giảm điểm khi cao hơn mức tham chiếu {rref}.</p>
      <h3>Năm trụ cột</h3>
      <dl className="method-pillars">{PILLARS.map(([k, t, d]) => <div key={k}><dt><strong>{k}</strong> · {t}</dt><dd className="subtle">{d}</dd></div>)}</dl>
      <h3>Trọng số theo hồ sơ</h3>
      {err && <p role="alert" className="negative">{err}</p>}
      {profiles.length>0&&<div className="method-table-wrap"><table className="method-table"><thead><tr><th>Hồ sơ</th>{['F','T','V','S'].map(k=><th key={k}>w{k}</th>)}<th>λ_R</th></tr></thead><tbody>{profiles.map(([k,p])=><tr key={k}><td>{NAMES[k]||k}</td>{['F','T','V','S'].map(w=><td key={w}>{Math.round((p.weights?.[w]??0)*100)}%</td>)}<td>{p.lambda_R}</td></tr>)}</tbody></table></div>}
      <h3>Ngưỡng khuyến nghị</h3>
      <ul className="method-list">{(sc?.ratings||[]).map(r=><li key={r.label}>≥ {r.min} — {r.label}</li>)}</ul>
      <h3>Chốt chặn</h3>
      <ul className="method-list">
        {sc?.risk_gate&&<li>Rủi ro R ≥ {sc.risk_gate.R_threshold}: khuyến nghị tối đa “{sc.risk_gate.max_rating}”.</li>}
        {sc?.data_gate?.limited_max_rating&&<li>Mã thanh khoản thấp (dữ liệu hạn chế): tối đa “{sc.data_gate.limited_max_rating}”.</li>}
        {sc?.data_gate?.implausible_upside_pct!=null&&<li>Giá tham chiếu cao hơn giá thị trường hơn {sc.data_gate.implausible_upside_pct}%: nghi lệch dữ liệu hoặc bẫy giá trị, tối đa “{sc.data_gate.implausible_max_rating}”.</li>}
      </ul>
      <h3>Giá trong phiên và điểm</h3>
      <p className="subtle">Điểm và khuyến nghị tính trên dữ liệu cuối ngày (EOD) nên không đổi theo từng lệnh khớp. Giá, % thay đổi và chỉ số thị trường cập nhật trực tiếp trong phiên; sau giờ đóng cửa hiển thị giá phiên gần nhất (tạm tính) cho đến khi dữ liệu cuối ngày về.</p>
      <h3>Giới hạn</h3>
      <ul className="method-list"><li>Giá tham chiếu là bội số trung vị ngành, không phải dự báo hay giá mục tiêu chắc chắn.</li><li>Mã thiếu báo cáo năm hoặc thanh khoản thấp có điểm kém tin cậy hơn.</li><li>Điểm xếp hạng mang tính hỗ trợ phân tích, không phải lời khuyên đầu tư.</li></ul>
      {meta?.asof&&<p className="subtle">Dữ liệu tính đến {meta.asof}{meta.formula?` · công thức ${meta.formula}`:''}</p>}
    </section>
  </div>;
}
