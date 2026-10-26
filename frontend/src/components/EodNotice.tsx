import {useEffect, useState} from 'react';

type Meta = {asof?: string; expected_asof?: string; eod_stale?: boolean; refreshed_at?: string | null};

const vn = (iso?: string) => (iso ? iso.split('-').reverse().join('/') : '');

/** Cảnh báo khi dữ liệu EOD (điểm số, báo cáo) cũ hơn phiên gần nhất; kiểm tra lại mỗi 5 phút. */
export function EodNotice() {
  const [meta, setMeta] = useState<Meta | null>(null);
  useEffect(() => {
    let dead = false;
    const load = () => fetch('/api/meta').then(r => (r.ok ? r.json() : null))
      .then(j => { if (!dead && j) setMeta(j.data ?? j); }).catch(() => undefined);
    load();
    const t = window.setInterval(load, 300000);
    return () => { dead = true; window.clearInterval(t); };
  }, []);
  if (!meta?.eod_stale) return null;
  return (
    <div className="eod-notice" role="status">
      Dữ liệu EOD đang ở phiên {vn(meta.asof)}, phiên gần nhất là {vn(meta.expected_asof)}.
      Điểm số và báo cáo sẽ cập nhật sau khi chạy làm mới dữ liệu cuối ngày; giá trong phiên vẫn cập nhật trực tiếp.
    </div>
  );
}
