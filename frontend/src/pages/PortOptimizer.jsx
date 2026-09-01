/**
 * Port Optimizer — ranks destination ports by cost / time / risk / history.
 */
import { useEffect, useState } from 'react';
import { api } from '../api';
import { money, fmt } from '../utils/format';
import PageHead from '../components/PageHead';
import Field from '../components/Field';

export default function PortOptimizer({ auth }) {
  const [refs, setRefs] = useState({ materials: {}, origins: {}, ports: {} });
  const [material, setMaterial] = useState('coking_coal');
  const [origin, setOrigin] = useState('australia');
  const [qty, setQty] = useState(80000);
  const [priority, setPriority] = useState(50);
  const [ranked, setRanked] = useState([]);
  const [best, setBest] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api('/api/refs').then(setRefs).catch(() => {});
  }, []);

  async function run() {
    setLoading(true);
    try {
      const data = await api('/api/optimizer', {
        method: 'POST',
        body: JSON.stringify({
          material,
          origin,
          quantity_mt: Number(qty),
          plant_code: auth?.manager?.plant || 'RSP',
          priority: Number(priority),
        }),
      });
      setRanked(data.ranked || []);
      setBest(data.best || null);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="page">
      <PageHead
        eyebrow="PORT OPTIMISER"
        title="Rank East Coast discharge options."
        desc="Cost, transit time, congestion, draft capability and historic preference are scored together."
        action={
          <button className="primary" onClick={run} disabled={loading}>
            {loading ? 'Scoring…' : 'Run ranking'}
          </button>
        }
      />

      <section className="panel">
        <div className="form-grid">
          <Field label="Material">
            <select value={material} onChange={(e) => setMaterial(e.target.value)}>
              {Object.entries(refs.materials || {}).map(([k, v]) => (
                <option key={k} value={k}>{v.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Origin">
            <select value={origin} onChange={(e) => setOrigin(e.target.value)}>
              {Object.entries(refs.origins || {}).map(([k, v]) => (
                <option key={k} value={k}>{v.label}</option>
              ))}
            </select>
          </Field>
          <Field label="Quantity (MT)">
            <input type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
          </Field>
          <Field label="Cost ↔ Time priority">
            <input
              type="range"
              min="0"
              max="100"
              value={priority}
              onChange={(e) => setPriority(+e.target.value)}
            />
          </Field>
        </div>
      </section>

      {best && (
        <section className="panel">
          <div className="panel-head">
            <div>
              <h3>AI preferred route</h3>
              <p>
                {best.port_label} via {best.origin_label} — score {best.score}
              </p>
            </div>
          </div>
          <div className="index-grid">
            <div><small>Landed / MT</small><b>{money(best.total_cost_mt)}</b></div>
            <div><small>Total cost</small><b>{money(best.total_cost)}</b></div>
            <div><small>ETA days</small><b>{best.eta_days}</b></div>
            <div><small>Risk</small><b>{best.risk_score}</b></div>
            <div><small>Congestion</small><b>{best.congestion}</b></div>
            <div><small>Max draft</small><b>{best.max_draft_m} m</b></div>
          </div>
        </section>
      )}

      {ranked.length > 0 && (
        <section className="panel">
          <div className="panel-head">
            <div><h3>Ranked ports</h3><p>Lower composite score is better.</p></div>
          </div>
          <div className="cons-grid">
            {ranked.map((r) => (
              <div className="cons-card" key={`${r.port}-${r.origin}`}>
                <div className="cons-top">
                  <div>
                    <b>#{r.rank} {r.port_label}</b>
                    <span>{r.origin_label} → {r.plant_code}</span>
                  </div>
                  <em className={`status ${r.rank === 1 ? 'on_schedule' : ''}`}>
                    {r.rank_label}
                  </em>
                </div>
                <div className="cons-metrics">
                  <div><small>Cost / MT</small><b>{money(r.total_cost_mt)}</b></div>
                  <div><small>ETA</small><b>{r.eta_days}d</b></div>
                  <div><small>Risk</small><b>{r.risk_score}</b></div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
