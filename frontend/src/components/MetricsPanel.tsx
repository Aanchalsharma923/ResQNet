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
          <div className="metric-value">{metrics ? metrics.packets_sent : 'N/A'}</div>
          <div className="metric-label">Packets Sent</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">{metrics ? metrics.packets_delivered : 'N/A'}</div>
          <div className="metric-label">Delivered</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">{metrics ? metrics.packets_dropped : 'N/A'}</div>
          <div className="metric-label">Dropped</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">{metrics ? metrics.pdr : 'N/A'}</div>
          <div className="metric-label">PDR</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">{metrics ? metrics.loss : 'N/A'}</div>
          <div className="metric-label">Loss</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">{metrics ? metrics.avg_hop_count : 'N/A'}</div>
          <div className="metric-label">Avg Hops</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">{metrics ? metrics.rreq_count : 'N/A'}</div>
          <div className="metric-label">RREQ Count</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">{metrics ? metrics.rrep_count : 'N/A'}</div>
          <div className="metric-label">RREP Count</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">{metrics ? metrics.rerr_count : 'N/A'}</div>
          <div className="metric-label">RERR Count</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">N/A</div>
          <div className="metric-label">Discovery Time</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">N/A</div>
          <div className="metric-label">Recovery Time</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">N/A</div>
          <div className="metric-label">Latency</div>
        </div>
        <div className="metric-item">
          <div className="metric-value">N/A</div>
          <div className="metric-label">Throughput</div>
        </div>
      </div>
    </div>
  );
};

export default MetricsPanel;
