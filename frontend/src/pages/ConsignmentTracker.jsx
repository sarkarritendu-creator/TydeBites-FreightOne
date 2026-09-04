/**
 * Consignment Tracker — active, delayed, delivered, future.
 * "Open route map" opens visual vessel route (origin → ship → destination).
 */
import { useEffect, useState } from 'react';
import { Ship, MapPin } from 'lucide-react';
import { api } from '../api';
import { fmt } from '../utils/format';
import PageHead from '../components/PageHead';
import VesselMap from '../components/VesselMap';

/** Fallback coords — match backend data/source_ports.json & destination_ports.json */
const ORIGIN_COORDS = {
  australia: [-20.31, 118.575],
  indonesia: [-6.1045, 106.8804],
  south_africa: [-28.783, 32.037],
  brazil: [-23.9608, -46.3333],
  mozambique: [-25.9653, 32.5892],
  uae: [25.0118, 55.0617],
  oman: [24.364, 56.739],
  usa: [29.9511, -90.0715],
};
const DEST_COORDS = {
  paradip: [20.2644, 86.6947],
  haldia: [22.0333, 88.1],
  vizag: [17.6868, 83.2185],
  gangavaram: [17.6167, 83.2333],
};

export default function ConsignmentTracker({ auth }) {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState('all');
  const [mapCons, setMapCons] = useState(null);

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

  function openMap(c) {
    const origin = ORIGIN_COORDS[c.origin] || ORIGIN_COORDS.australia;
    const dest = DEST_COORDS[c.port] || DEST_COORDS.paradip;
    setMapCons({ consignment: c, originCoords: origin, destCoords: dest });
  }

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

      {mapCons && (
        <VesselMap
          consignment={mapCons.consignment}
          originCoords={mapCons.originCoords}
          destCoords={mapCons.destCoords}
          onClose={() => setMapCons(null)}
        />
      )}

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
            {String(c.status).toLowerCase() !== 'delivered' && (
              <button
                className="secondary small"
                style={{ marginTop: 12, width: '100%' }}
                onClick={() => openMap(c)}
              >
                <MapPin size={13} /> Open route map
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}