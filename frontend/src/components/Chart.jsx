/**
 * Reusable AreaChart wrapper for BDI / freight series.
 * Expects data rows with either `bdi` or a numeric field; falls back gracefully.
 */
import {
  Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';

export default function Chart({ data = [], height = 280 }) {
  const rows = Array.isArray(data) ? data : [];
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={rows}>
        <defs>
          <linearGradient id="bdiFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#4d95ef" stopOpacity={0.35} />
            <stop offset="100%" stopColor="#4d95ef" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#2d3e5b" strokeDasharray="4 4" />
        <XAxis
          dataKey="date"
          tick={{ fill: '#90a3bd', fontSize: 10 }}
          tickFormatter={(v) => (v ? String(v).slice(5) : '')}
        />
        <YAxis tick={{ fill: '#90a3bd', fontSize: 10 }} domain={['auto', 'auto']} />
        <Tooltip
          contentStyle={{ background: '#111f35', border: '1px solid #2a3d5f', borderRadius: 8 }}
          labelStyle={{ color: '#91a4bf' }}
        />
        <Area
          type="monotone"
          dataKey="bdi"
          stroke="#4d95ef"
          fill="url(#bdiFill)"
          strokeWidth={2}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
