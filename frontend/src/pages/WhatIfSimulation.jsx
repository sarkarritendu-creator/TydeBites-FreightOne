/**
 * What-if Simulation — compare manager preference vs best alternative.
 */
import { useEffect, useState } from 'react';
import { api } from '../api';
import { money } from '../utils/format';
import PageHead from '../components/PageHead';
import Field from '../components/Field';

export default function WhatIfSimulation({ auth }) {
  const [refs, setRefs] = useState({ materials: {}, ports: {} });
  const [material, setMaterial] = useState('coking_coal');
  const [qty, setQty] = useState(80000);
  const [deadline, setDeadline] = useState(21);
  const [port, setPort] = useState('paradip');
  const [priority, setPriority] = useState(55);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api('/api/refs').then(setRefs).catch(() => {});
  }, []);

  async function run() {
    setLoading(true);
    try {
      const data = await api('/api/what-if', {
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
      setResult(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  const base = result?.base;
  const alt = result?.what_if;
  const diff = result?.difference;

  return (
    <div className="page">
      <PageHead
        eyebrow="WHAT-IF SIMULATION"
        title="Change the assumptions. Watch the decision move."
        desc="Compare your preferred port against the model’s best alternative under the same constraints."
        action={
          <button className="primary" onClick={run} disabled={loading}>
            {loading ? 'Simulating…' : 'Run simulation'}
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
          <Field label="Quantity (MT)">
            <input type="number" value={qty} onChange={(e) => setQty(e.target.value)} />
          </Field>
          <Field label="Deadline (days)">
            <input type="number" value={deadline} onChange={(e) => setDeadline(e.target.value)} />
          </Field>
          <Field label="Preferred port">
            <select value={port} onChange={(e) => setPort(e.target.value)}>
              {Object.entries(refs.ports || {}).map(([k, v]) => (
                <option key={k} value={k}>{v.name}</option>
              ))}
            </select>
          </Field>
        </div>
      </section>

      {result && base && alt && (
        <div className="grid two">
          <section className="panel preference">
            <div className="panel-label">PREFERRED CHOICE</div>
            <div className="scenario">
              <b>{base.port_label}</b>
              <div><span>Origin</span><strong>{base.origin_label}</strong></div>
              <div><span>Landed cost</span><strong>{money(base.total_cost)}</strong></div>
              <div><span>Cost / MT</span><strong>{money(base.total_cost_mt)}</strong></div>
              <div><span>ETA</span><strong>{base.eta_days} days</strong></div>
              <div><span>Risk</span><strong>{base.risk_score}</strong></div>
            </div>
          </section>
          <section className="panel model">
            <div className="panel-label">WHAT-IF ALTERNATIVE</div>
            <div className="scenario">
              <b>{alt.port_label}</b>
              <div><span>Origin</span><strong>{alt.origin_label}</strong></div>
              <div><span>Landed cost</span><strong>{money(alt.total_cost)}</strong></div>
              <div><span>Cost / MT</span><strong>{money(alt.total_cost_mt)}</strong></div>
              <div><span>ETA</span><strong>{alt.eta_days} days</strong></div>
              <div><span>Risk</span><strong>{alt.risk_score}</strong></div>
            </div>
          </section>
        </div>
      )}

      {diff && (
        <section className="panel" style={{ marginTop: 14 }}>
          <div className="panel-head">
            <div>
              <h3>Delta</h3>
              <p>{result.summary}</p>
            </div>
          </div>
          <div className="index-grid">
            <div>
              <small>Cost delta</small>
              <b style={{ color: diff.cost_delta < 0 ? 'var(--green)' : 'var(--red)' }}>
                {money(diff.cost_delta)}
              </b>
            </div>
            <div>
              <small>ETA delta</small>
              <b>{diff.eta_delta_days} days</b>
            </div>
            <div>
              <small>Risk delta</small>
              <b>{diff.risk_delta}</b>
            </div>
          </div>
        </section>
      )}
    </div>
  );
}
