import {useEffect, useMemo, useState} from 'react';
import {Layers3, X} from 'lucide-react';

export const COMPARE_MAX = 4;

interface Row {
  ticker: string; name: string | null; sector: string | null; rating: string; score: number | null;
  scores: Record<'F'|'T'|'V'|'S'|'R', number | null>;
  price?: number | null; reference_price?: number | null; upside_pct?: number | null;
  quality_gate?: {tier?: string};
}

/** Chỉ số tốt nhất của một hàng: cao hơn tốt (R: thấp hơn tốt); cần ít nhất 2 giá trị. */
export function bestIndex(vals: Array<number | null | undefined>, lowerBetter = false): number {
  let best = -1;
  vals.forEach((v, i) => {
    if (v == null || Number.isNaN(v)) return;
    if (best < 0 || (lowerBetter ? v < (vals[best] as number) : v > (vals[best] as number))) best = i;
  });
  return vals.filter(v => v != null && !Number.isNaN(v as number)).length >= 2 ? best : -1;
}

const f=(v:number|null|undefined,d=2)=>typeof v==='number'&&Number.isFinite(v)?v.toLocaleString('vi-VN',{maximumFractionDigits:d}):'—';

/** So sánh tối đa 4 mã cạnh nhau (điểm EOD theo hồ sơ đang chọn). */
export function ComparePage({profile, initial, catalog}: {profile: string; initial: string; catalog: any[]}) {
  const [rows, setRows] = useState<Row[]>([]);
  const [error, setError] = useState('');
  const [picked, setPicked] = useState<string[]>(() => initial ? [initial] : []);
  const [q, setQ] = useState('');
  useEffect(() => {
    let on = true;
    fetch(`/api/rankings?profile=${profile}&limit=500&include_unranked=true&sort=score&order=desc`)
      .then(r => {if (!r.ok) throw Error(`HTTP ${r.status}`); return r.json();})
      .then(b => {if (on) {setRows(b.items || []); setError('');}})
      .catch(() => {if (on) setError('Không tải được dữ liệu xếp hạng.');});
    return () => {on = false;};
  }, [profile]);
  const by = useMemo(() => new Map(rows.map(r => [r.ticker, r])), [rows]);
  const cols = picked.map(s => by.get(s)).filter(Boolean) as Row[];
  const sugg = useMemo(() => {
    const t = q.trim().toUpperCase();
    if (!t) return [];
    const src = rows.length ? rows.map(r => ({symbol: r.ticker, name: r.name})) : catalog;
    return src.filter((r: any) => !picked.includes(r.symbol) && (r.symbol.startsWith(t) || String(r.name || '').toUpperCase().includes(t))).slice(0, 6);
  }, [q, rows, catalog, picked]);
  const add = (s: string) => {if (picked.length < COMPARE_MAX && !picked.includes(s)) {setPicked([...picked, s]); setQ('');}};
  const lines: Array<{label: string; vals: Array<number | null | undefined>; d?: number; low?: boolean; hint?: string; noBest?: boolean; suffix?: string}> = [
    {label: 'Điểm tổng', vals: cols.map(r => r.score)},
    {label: 'F · Cơ bản', vals: cols.map(r => r.scores?.F)},
    {label: 'T · Kỹ thuật', vals: cols.map(r => r.scores?.T)},
    {label: 'V · Định giá', vals: cols.map(r => r.scores?.V)},
    {label: 'S · Tin tức', vals: cols.map(r => r.scores?.S)},
    {label: 'R · Rủi ro', vals: cols.map(r => r.scores?.R), low: true, hint: 'thấp hơn là tốt hơn'},
    {label: 'Giá đóng cửa', vals: cols.map(r => r.price), d: 0, noBest: true},
    {label: 'Giá tham chiếu ngành', vals: cols.map(r => r.reference_price), d: 0, noBest: true},
    {label: 'Chênh lệch so với giá tham chiếu', vals: cols.map(r => r.upside_pct), hint: 'không phải dự báo giá', noBest: true, suffix: '%'},
  ];
  return <div className="compare-page"><section className="panel"><div className="panel-heading"><h2><Layers3 size={16}/> So sánh mã</h2></div>
    <p className="subtle">Chọn tối đa {COMPARE_MAX} mã. Điểm là điểm EOD theo khung ở trang Phương pháp, không đổi theo giá trong phiên.</p>
    <div className="compare-pick">
      <input value={q} disabled={picked.length >= COMPARE_MAX} onChange={e => setQ(e.target.value)} placeholder={picked.length >= COMPARE_MAX ? 'Đã đủ số mã' : 'Thêm mã hoặc tên công ty'} aria-label="Thêm mã so sánh"
        onKeyDown={e => {if (e.key === 'Enter' && sugg[0]) add(sugg[0].symbol);}}/>
      {sugg.length>0&&<ul className="compare-suggest">{sugg.map((r: any) => <li key={r.symbol}><button type="button" onClick={() => add(r.symbol)}><strong>{r.symbol}</strong> <span className="subtle">{r.name}</span></button></li>)}</ul>}
    </div>
    {error && <p role="alert" className="negative">{error}</p>}
    {!cols.length && !error && <p className="subtle">Chưa chọn mã nào.</p>}
    {cols.length>0&&<div className="method-table-wrap"><table className="method-table compare-table"><thead><tr><th/>{cols.map(r => <th key={r.ticker}>{r.ticker}<small>{r.sector || '—'}</small><button type="button" className="compare-remove" aria-label={`Bỏ ${r.ticker}`} onClick={() => setPicked(picked.filter(s => s !== r.ticker))}><X size={12}/> Bỏ</button></th>)}</tr></thead>
      <tbody><tr><td>Khuyến nghị</td>{cols.map(r => <td key={r.ticker}><strong>{r.rating || '—'}</strong>{r.quality_gate?.tier === 'limited' && <small>dữ liệu hạn chế</small>}</td>)}</tr>
        {lines.map(ln => {const b = ln.noBest ? -1 : bestIndex(ln.vals, ln.low); return <tr key={ln.label}><td>{ln.label}{ln.hint && <small>{ln.hint}</small>}</td>{ln.vals.map((v, i) => <td key={cols[i]!.ticker} className={i === b ? 'compare-best' : ''}>{f(v, ln.d ?? 1)}{v != null && ln.suffix ? ln.suffix : ''}</td>)}</tr>;})}
      </tbody></table></div>}
    <p className="subtle">Ô đậm là giá trị tốt nhất trong hàng. Công cụ hỗ trợ phân tích, không phải lời khuyên đầu tư.</p>
  </section></div>;
}
