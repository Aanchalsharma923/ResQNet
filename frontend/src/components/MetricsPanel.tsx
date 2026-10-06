import { useEffect, useState } from 'react';
import type { Metrics, WSEvent } from '../types';
import { fetchMetrics } from '../services/api';

const MetricsPanel = ({ events }: { events: WSEvent[] }) => {
  const [metrics, setMetrics] = useState<Metrics | null>(null);

  useEffect(() => {
    // Refresh metrics when a new event arrives
    fetchMetrics().then(setMetrics).catch(console.error);
  }, [events]);

  return (
    <div className="panel">
      <h2>Metrics</h2>
      <div className="metrics-grid">
        <div className="metric-item">
          <div className="metric-value">{metrics ? metrics.total_events : 'N/A'}</div>
          <div className="metric-label">Total Events</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">{metrics ? metrics.total_packets_pending : 'N/A'}</div>
          <div className="metric-label">Pending Pkts</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">N/A</div>
          <div className="metric-label">PDR</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">N/A</div>
          <div className="metric-label">Loss</div>
        </div>
      </div>
    </div>
  );
};

export default MetricsPanel;
