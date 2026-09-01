/**
 * Consignment Tracker — active, delayed, delivered, future.
 */
import { useEffect, useState } from 'react';
import { Ship } from 'lucide-react';
import { api } from '../api';
import { fmt } from '../utils/format';
import PageHead from '../components/PageHead';

export default function ConsignmentTracker({ auth }) {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    const plant = auth?.manager?.plant || '';
    const q = plant ? `?plant_code=${encodeURIComponent(plant)}` : '';
    api(`/api/consignments${q}`)
      .then((d) => setItems(d.consignments || []))
      .catch(() => setItems([]));
  }, [auth?.manager?.plant]);

  const filtered = items.filter((c) => {
    if (filter === 'all') return true;
    return String(c.status || '').toLowerCase() === filter;
  });

  return (
    <div className="page">
      <PageHead
        eyebrow="CONSIGNMENT TRACKER"
        title="Every vessel, every status."
        desc="Active, delayed, delivered and future fixtures with ETA and recovery context."
      />

      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {['all', 'on schedule', 'delayed', 'delivered', 'future'].map((f) => (
          <button
            key={f}
            className={filter === f ? 'primary small' : 'secondary small'}
            onClick={() => setFilter(f)}
          >
            {f}
          </button>
        ))}
      </div>

      <div className="cons-grid">
        {filtered.map((c) => (
          <div className="cons-card" key={c.id}>
            <div className="cons-top">
              <div>
                <b>{c.id}</b>
                <span>
                  {c.material_label || c.material} · {c.origin_label || c.origin} →{' '}
                  {c.port_label || c.port}
                </span>
              </div>
              <em
                className={`status ${
                  String(c.status).toLowerCase() === 'delayed' ? 'delayed' : 'on_schedule'
                }`}
              >
                {String(c.status).toLowerCase() === 'delayed'
                  ? `Delayed ${c.delay_days || 0}d`
                  : c.status}
              </em>
            </div>
            <div className="route-line">
              <Ship size={13} /><i />Port<i />Plant
            </div>
            <div className="cons-metrics">
              <div><small>Vessel</small><b>{c.vessel}</b></div>
              <div><small>Tonnage</small><b>{fmt(c.tonnage)} MT</b></div>
              <div><small>Progress</small><b>{c.progress_pct || 0}%</b></div>
              <div><small>Port ETA</small><b>{c.eta_port_date || '—'}</b></div>
              <div><small>Final arrival</small><b>{c.expected_final_arrival || '—'}</b></div>
              <div><small>Position</small><b style={{ fontSize: 10 }}>{c.position || '—'}</b></div>
            </div>
            {c.delay_reason && (
              <p style={{ fontSize: 11, color: 'var(--muted)', marginTop: 10 }}>
                {c.delay_reason}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
