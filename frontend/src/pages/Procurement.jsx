/**
 * Procurement Planner
 * Inputs: material, qty, deadline, preferred port, cost↔deadline priority.
 * Calls POST /api/procurement and renders manager preference vs AI tile.
 */
import { useEffect, useState } from 'react';
import { api } from '../api';
import { fmt, money } from '../utils/format';
import PageHead from '../components/PageHead';
import Field from '../components/Field';

export default function Procurement({ auth }) {
  const [refs, setRefs] = useState({ materials: {}, ports: {} });
  const [material, setMaterial] = useState('coking_coal');
  const [qty, setQty] = useState(80000);
  const [deadline, setDeadline] = useState(21);
  const [port, setPort] = useState('paradip');
  const [priority, setPriority] = useState(55);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    api('/api/refs')
      .then((data) => setRefs(data || {}))
      .catch(() => {});
  }, []);

  async function run() {
    setLoading(true);
    setMessage('');
    try {
      const live = await api('/api/procurement', {
        method: 'POST',
        body: JSON.stringify({
          material,
          quantity_mt: Number(qty),
          deadline_days: Number(deadline),
          port,
          plant_code: auth?.manager?.plant || 'RSP',
          priority: Number(priority),
        }),
      });
      setResult(live);
    } catch (err) {
      setMessage(err.message || 'Procurement plan failed');
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  const selected = result?.selected;
  const ai = result?.ai;
  const best = result?.best_overall;

  return (
    <div className="page">
      <PageHead
        eyebrow="PROCUREMENT INTELLIGENCE"
        title="Plan the next bulk cargo booking."
        desc="Material, deadline and preferred port drive a live cost / risk / urgency recommendation."
        action={
          <button className="primary" onClick={run} disabled={loading}>
            {loading ? 'Running model…' : 'Generate plan'}
          </button>
        }
      />

      <section className="panel">
        <div className="form-grid">
          <Field label="Material" help="Which bulk cargo is being planned.">
            <select value={material} onChange={(e) => setMaterial(e.target.value)}>
              {Object.entries(refs.materials || {}).map(([k, v]) => (
                <option key={k} value={k}>{v.name}</option>
              ))}
            </select>
          </Field>
          <Field label="Quantity" help="Planned cargo volume.">
            <div className="unit-input">
              <input type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
              <span>MT</span>
            </div>
          </Field>
          <Field label="Delivery deadline" help="Required final-arrival window (days).">
            <input type="number" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
          </Field>
          <Field label="Preferred port" help="The model evaluates your preference instead of blindly following it.">
            <select value={port} onChange={(e) => setPort(e.target.value)}>
              {Object.entries(refs.ports || {}).map(([k, v]) => (
                <option key={k} value={k}>{v.name}</option>
              ))}
            </select>
          </Field>
        </div>
        <div className="priority-box">
          <div>
            <b>Cost ↔ deadline preference</b>
            <small>Move toward cost to favor lower landed cost, or deadline to favor faster delivery.</small>
          </div>
          <div className="priority-control">
            <span>Cost</span>
            <input
              type="range"
              min="0"
              max="100"
              value={priority}
              onChange={(e) => setPriority(+e.target.value)}
            />
            <span>Deadline</span>
          </div>
        </div>
      </section>

      {message && <div className="error" style={{ marginTop: 12 }}>{message}</div>}

      {result && (
        <div className="grid two">
          <section className="panel preference">
            <div className="panel-label">MANAGER PREFERENCE</div>
            <div className="scenario">
              <b>{selected?.material_label || material}</b>
              <div>
                <span>Quantity</span>
                <strong>{fmt(selected?.quantity_mt || qty)} MT</strong>
              </div>
              <div>
                <span>Deadline</span>
                <strong>{deadline} days</strong>
              </div>
              <div>
                <span>Port</span>
                <strong>{selected?.port_label || port}</strong>
              </div>
              {selected && (
                <>
                  <div>
                    <span>Landed cost / MT</span>
                    <strong>{money(selected.total_cost_mt)}</strong>
                  </div>
                  <div>
                    <span>Total landed</span>
                    <strong>{money(selected.total_cost)}</strong>
                  </div>
                  <div>
                    <span>ETA</span>
                    <strong>{selected.eta_days} days</strong>
                  </div>
                </>
              )}
            </div>
          </section>

          <section className="panel model">
            <div className="panel-label">AI / MODEL OUTPUT</div>
            <div className="scenario">
              <b>{ai?.preferred_port || best?.port_label || '—'}</b>
              <div>
                <span>Origin</span>
                <strong>{ai?.origin_label || best?.origin_label || '—'}</strong>
              </div>
              <div>
                <span>Recommended quantity</span>
                <strong>{fmt(ai?.quantity_mt || qty)} MT</strong>
              </div>
              <div>
                <span>Urgency index</span>
                <strong>{ai?.urgency_index ?? '—'}/10</strong>
              </div>
              <div>
                <span>Days of cover</span>
                <strong>{ai?.days_of_cover ?? '—'}</strong>
              </div>
            </div>
            <p className="reason">{ai?.recommendation}</p>
          </section>
        </div>
      )}
    </div>
  );
}
