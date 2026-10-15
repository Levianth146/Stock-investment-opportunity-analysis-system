import {Target} from 'lucide-react';
import {finite, numberText as num} from '../analysisData';

const pctText = (v: any, d = 1) => (finite(v) ? `${num(v * 100, d)}%` : '—');
const bn = (v: any) => (finite(v) ? num(v / 1e9, 0) : '—');

/** Kết quả DCF (FCFF) do M4 tính; giao diện chỉ hiển thị, không tự tính lại. */
export function DcfPanel({data}: {data: any}) {
  const dcf = data?.modules?.m4?.dcf;
  if (!dcf) {
    return <div className="dcf-state"><Target size={33}/><h3>Chưa có kết quả DCF</h3>
      <p>Dữ liệu phân tích này chưa chứa khối DCF. Chạy lại phân tích sau khi M4 bật enable_dcf để có kết quả.</p></div>;
  }
  if (dcf.status !== 'ok') {
    return <div className="dcf-state"><Target size={33}/>
      <h3>{dcf.status === 'not_applicable' ? 'DCF không áp dụng cho mã này' : 'Chưa tính được DCF'}</h3>
      <p>{dcf.reason || 'Không đủ dữ liệu để dự phóng dòng tiền.'}</p></div>;
  }
  const up = dcf.upside_pct;
  const s = dcf.sensitivity;
  return <div className="dcf-panel">
    <div className="dcf-kpis">
      <article><span>Giá trị DCF</span><strong>{num(dcf.per_share, 0)} <small>₫/cp</small></strong>
        <em className={finite(up) && up >= 0 ? 'positive' : 'negative'}>{finite(up) ? `${up >= 0 ? '+' : ''}${num(up, 1)}% so với giá` : ''}</em></article>
      <article><span>Thận trọng / Tích cực</span><strong>{num(dcf.bear, 0)} – {num(dcf.bull, 0)}</strong><em>WACC ±1 điểm %, tăng trưởng điều chỉnh</em></article>
      <article><span>WACC</span><strong>{pctText(dcf.wacc)}</strong><em>Vốn chủ {pctText(dcf.cost_of_equity)} · Nợ {pctText(dcf.cost_of_debt)}</em></article>
      <article><span>Tăng trưởng dài hạn</span><strong>{pctText(dcf.terminal_growth)}</strong><em>Giá trị cuối kỳ {pctText(dcf.tv_share, 0)} tổng giá trị</em></article>
    </div>
    {!dcf.usable_for_target && <p className="dcf-warning" role="status">{dcf.reason || 'Kết quả DCF lệch xa giá thị trường nên không đưa vào giá mục tiêu.'}</p>}
    {dcf.usable_for_target && <p className="analysis-source-note">DCF được trộn vào giá mục tiêu cơ sở theo tỷ trọng đã cấu hình; điểm V không đổi.</p>}
    <h4>Dự phóng FCFF (tỷ đồng)</h4>
    <div className="peer-scroll"><table className="dcf-table"><thead><tr><th>Năm</th><th>Tăng trưởng</th><th>FCFF</th><th>Hiện giá</th></tr></thead>
      <tbody>{(dcf.projection || []).map((r: any) => <tr key={r.year}><th>{r.year}</th><td>{pctText(r.growth)}</td><td>{bn(r.fcff)}</td><td>{bn(r.pv)}</td></tr>)}
        <tr className="dcf-total"><th>Cuối kỳ</th><td/><td/><td>{bn(dcf.pv_terminal)}</td></tr></tbody></table></div>
    <p className="analysis-source-note">Giá trị doanh nghiệp {bn(dcf.ev)} tỷ − nợ vay {bn(dcf.debt)} tỷ + tiền {bn(dcf.cash)} tỷ = vốn chủ {bn(dcf.equity_value)} tỷ.</p>
    {s?.per_share && <>
      <h4>Độ nhạy: giá trị mỗi cổ phiếu (₫)</h4>
      <div className="peer-scroll"><table className="dcf-table"><thead><tr><th>WACC \ g</th>{s.terminal_growth.map((g: number) => <th key={g}>{pctText(g)}</th>)}</tr></thead>
        <tbody>{s.per_share.map((row: any[], i: number) => <tr key={i}><th>{pctText(s.wacc[i])}</th>{row.map((v, j) => <td key={j} className={i === 2 && j === 2 ? 'dcf-center' : ''}>{finite(v) ? num(v, 0) : '—'}</td>)}</tr>)}</tbody></table></div>
    </>}
    <h4>Giả định</h4>
    <ul className="dcf-assumptions">{(dcf.assumptions || []).map((a: string) => <li key={a}>{a}</li>)}</ul>
  </div>;
}
