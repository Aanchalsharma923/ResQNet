import { useEffect, useState } from 'react';
import type { Metrics, WSEvent, NetworkState } from '../types';
import { fetchMetrics } from '../services/api';

interface MetricsPanelProps {
  events: WSEvent[];
  networkState?: NetworkState | null;
}

const MetricsPanel = ({ events, networkState }: MetricsPanelProps) => {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);

  useEffect(() => {
    // Refresh metrics whenever a new WebSocket event arrives
    fetchMetrics().then(setMetrics).catch(console.error);
  }, [events]);

  const activeHopCount = networkState?.active_route && networkState.active_route.length > 1
    ? `${networkState.active_route.length - 1} Hops`
    : (metrics && metrics.avg_hop_count !== '0' && metrics.avg_hop_count !== 'N/A' ? `${metrics.avg_hop_count} Hops` : 'N/A');

  const isRealMode = networkState?.mode === 'real';

  return (
    <div className="panel">
      <h2>
        <span>Network Performance</span>
        <span style={{
          fontSize: '0.72rem',
          color: isRealMode ? '#c4b5fd' : '#38bdf8',
          fontWeight: 600,
          background: isRealMode ? 'rgba(139, 92, 246, 0.15)' : 'rgba(2, 132, 199, 0.15)',
          padding: '2px 8px',
          borderRadius: '4px',
          border: `1px solid ${isRealMode ? 'rgba(139, 92, 246, 0.3)' : 'rgba(2, 132, 199, 0.3)'}`
        }}>
          {isRealMode ? 'Real UDP Socket Telemetry' : 'Simulated Network Telemetry'}
        </span>
      </h2>

      {/* 4 Headline Metrics */}
      <div className="metrics-headline-grid">
        <div className="headline-metric featured">
          <div className="headline-value green">{metrics ? metrics.pdr : '0%'}</div>
          <div className="headline-label">Delivery Ratio (PDR)</div>
        </div>

        <div className="headline-metric">
          <div className="headline-value">{metrics ? metrics.packets_delivered : '0'}</div>
          <div className="headline-label">Delivered SOS</div>
        </div>

        <div className="headline-metric">
          <div className={`headline-value ${metrics && metrics.recovery_time !== 'N/A' ? 'amber' : ''}`}>
            {metrics ? metrics.recovery_time : 'N/A'}
          </div>
          <div className="headline-label">Recovery Time</div>
          {metrics?.recovery_time === 'N/A' && (
            <div style={{ fontSize: '0.65rem', color: '#64748b', marginTop: '2px' }}>
              Measured after failover
            </div>
          )}
        </div>

        <div className="headline-metric">
          <div className="headline-value cyan">{activeHopCount}</div>
          <div className="headline-label">Active Path Hops</div>
        </div>
      </div>

      {/* Collapsible Secondary Protocol Metrics (CNT Viva) */}
      <button
        type="button"
        className="telemetry-toggle-btn"
        onClick={() => setShowTechnicalDetails(prev => !prev)}
      >
        {showTechnicalDetails ? '▲ Hide Protocol Telemetry' : '▼ Technical Protocol Telemetry (CNT Viva)'}
      </button>

      {showTechnicalDetails && (
        <>
          <div className="metrics-secondary-grid">
            <div className="metric-sub-item">
              <span className="metric-sub-label">Packets Sent</span>
              <span className="metric-sub-value">{metrics ? metrics.packets_sent : '0'}</span>
            </div>
            <div className="metric-sub-item">
              <span className="metric-sub-label">Delivered</span>
              <span className="metric-sub-value">{metrics ? metrics.packets_delivered : '0'}</span>
            </div>
            <div className="metric-sub-item">
              <span className="metric-sub-label">Dropped</span>
              <span className="metric-sub-value">{metrics ? metrics.packets_dropped : '0'}</span>
            </div>

            <div className="metric-sub-item">
              <span className="metric-sub-label">PDR</span>
              <span className="metric-sub-value">{metrics ? metrics.pdr : '0%'}</span>
            </div>
            <div className="metric-sub-item">
              <span className="metric-sub-label">Loss</span>
              <span className="metric-sub-value">{metrics ? metrics.loss : '0%'}</span>
            </div>
            <div className="metric-sub-item">
              <span className="metric-sub-label">Avg Hops</span>
              <span className="metric-sub-value">{metrics ? metrics.avg_hop_count : '0'}</span>
            </div>

            <div className="metric-sub-item">
              <span className="metric-sub-label">RREQ Count</span>
              <span className="metric-sub-value">{metrics ? metrics.rreq_count : '0'}</span>
            </div>
            <div className="metric-sub-item">
              <span className="metric-sub-label">RREP Count</span>
              <span className="metric-sub-value">{metrics ? metrics.rrep_count : '0'}</span>
            </div>
            <div className="metric-sub-item">
              <span className="metric-sub-label">RERR Count</span>
              <span className="metric-sub-value">{metrics ? metrics.rerr_count : '0'}</span>
            </div>

            <div className="metric-sub-item">
              <span className="metric-sub-label">Discovery Time</span>
              <span className="metric-sub-value">
                {metrics && metrics.route_discovery_time !== 'N/A' ? metrics.route_discovery_time : 'N/A (Awaits RREP)'}
              </span>
            </div>
            <div className="metric-sub-item">
              <span className="metric-sub-label">Latency</span>
              <span className="metric-sub-value">
                {metrics && metrics.latency !== 'N/A' ? metrics.latency : 'N/A (Transit delay)'}
              </span>
            </div>
            <div className="metric-sub-item">
              <span className="metric-sub-label">Throughput</span>
              <span className="metric-sub-value">
                {metrics && metrics.throughput !== 'N/A' ? metrics.throughput : 'N/A (Active burst)'}
              </span>
            </div>
          </div>
          <p className="telemetry-footnote">
            Note: All values reflect actual runtime measurements. Uncalculated temporal metrics are clearly indicated as N/A until live packet bursts occur.
          </p>
        </>
      )}
    </div>
  );
};

export default MetricsPanel;
