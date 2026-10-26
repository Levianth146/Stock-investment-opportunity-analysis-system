import {useMarketStream} from '../live/useMarketStream';
const fmt=(v:number,d=2)=>v.toLocaleString('vi-VN',{maximumFractionDigits:d});

const PHASE: Record<string, string> = {
  pre: 'Trước giờ giao dịch', morning: 'Phiên sáng', lunch: 'Nghỉ trưa',
  afternoon: 'Phiên chiều', atc: 'ATC', closed: 'Đã đóng cửa',
};

function n(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/**
 * Thanh thị trường: VN-Index và độ rộng. Dữ liệu chỉ hiện khi API có nguồn trực tiếp hoặc giá phiên gần nhất
 * của hub; không có thì ẩn (giao diện vẫn dùng snapshot).
 */
export function MarketLiveBar() {
  const {data, conn} = useMarketStream(true);
  const idx = data?.index;
  const price = n(idx?.price?.value);
  if (!data || price == null || (idx?.source !== 'realtime' && idx?.source !== 'eod')) return null;
  const chg = n(idx.change_pct?.value);
  const live = data.realtime?.state === 'live' && idx.price?.basis === 'live';
  const phase = data.session?.phase ? PHASE[data.session.phase] || data.session.phase : null;
  const b = data.breadth || {};
  const up = n(b.up), down = n(b.down), flat = n(b.flat);
  return (
    <div className={`market-live-bar ${live ? 'is-live' : ''}`} role="status" aria-label="VN-Index">
      <strong>VN-Index</strong>
      <span className="mlb-num">{fmt(price, 2)}</span>
      {chg != null && <span className={`mlb-num ${chg >= 0 ? 'positive' : 'negative'}`}>{chg >= 0 ? '+' : ''}{fmt(chg, 2)}%</span>}
      <span className="mlb-state">
        {live ? <><span className="live-dot"/> Trực tiếp</> : (idx.label || 'Đóng cửa (tạm tính)')}
        {live && phase ? ` · ${phase}` : ''}
        {conn === 'fallback' && live ? ' · cập nhật định kỳ' : ''}
      </span>
      {up != null && down != null && (
        <span className="mlb-breadth">
          <span className="positive">▲ {fmt(up, 0)}</span>
          <span className="muted-text">■ {fmt(flat ?? 0, 0)}</span>
          <span className="negative">▼ {fmt(down, 0)}</span>
        </span>
      )}
    </div>
  );
}
