/**
 * Freight Intelligence — BDI history + 90-day forecast, booking window, weather.
 */
import { useEffect, useState } from 'react';
import {
  LineChart, Line, CartesianGrid, XAxis, YAxis, ResponsiveContainer,
} from 'recharts';
import { Clock3, CloudRain } from 'lucide-react';
import { api } from '../api';
import PageHead from '../components/PageHead';
import Chart from '../components/Chart';

export default function FreightIntelligence() {
  const [data, setData] = useState(null);
  const [weather, setWeather] = useState(null);

  useEffect(() => {
    Promise.allSettled([
      api('/api/freight-intelligence'),
      api('/api/weather'),
    ]).then(([f, w]) => {
      setData(f.status === 'fulfilled' ? f.value : null);
      setWeather(w.status === 'fulfilled' ? w.value : null);
    });
  }, []);

  const forecast = data?.forecast || { history: [], forecast: [] };
  const chart = [
    ...(Array.isArray(forecast.history) ? forecast.history.slice(-30) : []),
    ...(Array.isArray(forecast.forecast) ? forecast.forecast.slice(0, 60) : []),
  ];
  const weatherSeries = weather?.series || [];
  const weatherRisk = weather?.risk || { no_delay: 42, slight: 28, moderate: 20, high: 10 };

  return (
    <div className="page">
      <PageHead
        eyebrow="FREIGHT MARKET INTELLIGENCE"
        title="Market signals before the booking window closes."
        desc="BDI trend, forecast horizon, weather exposure and booking timing in one view."
      />
      <div className="grid two">
        <section className="panel">
          <div className="panel-head">
            <div>
              <h3>BDI history + 90-day model horizon</h3>
              <p>Historical freight movement and the current forecast.</p>
            </div>
          </div>
          <Chart data={chart} />
        </section>
        <section className="panel">
          <h3>Recommended booking window</h3>
          <div className="decision buy">
            <div className="decision-icon"><Clock3 size={20} /></div>
            <div>
              <span className="eyebrow">MODEL TIMING OUTPUT</span>
              <h2>Book around day {data?.booking_window?.best_day || '—'}</h2>
              <p>
                {data?.booking_window?.reason ||
                  'Model balances projected freight rate, weather risk and procurement lead time.'}
                {data?.booking_window?.expected_savings_percent != null && (
                  <> Estimated saving opportunity: {data.booking_window.expected_savings_percent}%.</>
                )}
              </p>
            </div>
          </div>
          <div className="index-grid">
            {Object.entries(
              data?.indices || { BDI: '—', Capesize: '—', Panamax: '—', Fuel: '—', Congestion: '—' },
            ).map(([k, v]) => (
              <div key={k}>
                <small>{k}</small>
                <b>{v}</b>
              </div>
            ))}
          </div>
        </section>
      </div>
      <section className="panel weather-panel">
        <div className="panel-head">
          <div>
            <h3>How is the weather today at Bay of Bengal?</h3>
            <p>{weather?.status || 'Loading regional weather risk…'}</p>
          </div>
          <CloudRain size={22} />
        </div>
        <div className="weather-grid">
          <ResponsiveContainer width="100%" height={230}>
            <LineChart data={weatherSeries}>
              <CartesianGrid stroke="#2d3e5b" strokeDasharray="4 4" />
              <XAxis dataKey="day" tick={{ fill: '#90a3bd', fontSize: 10 }} />
              <YAxis tick={{ fill: '#90a3bd', fontSize: 10 }} />
              <Line dataKey="risk" stroke="#edb353" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
          <div className="risk-bars">
            {Object.entries(weatherRisk).map(([k, v]) => (
              <div key={k}>
                <span className={`risk-color ${k}`} />
                <b>{k.replace('_', ' ')}</b>
                <em>{v}%</em>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}
