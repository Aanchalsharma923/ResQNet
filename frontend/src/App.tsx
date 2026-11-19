import { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import type { NetworkState, RuntimeMode } from './types';
import { fetchNetworkState } from './services/api';
import TopologyView from './components/TopologyView';
import EventLog from './components/EventLog';
import MetricsPanel from './components/MetricsPanel';
import ControlsPanel from './components/ControlsPanel';
import SOSPanel from './components/SOSPanel';
import HospitalPanel from './components/HospitalPanel';
import GuidedDemoPanel from './components/GuidedDemoPanel';
import './App.css';

function App() {
  const getWsUrl = () => {
    if ((import.meta as any).env?.VITE_WS_URL) {
      return (import.meta as any).env.VITE_WS_URL;
    }
    if (typeof window !== 'undefined' && window.location) {
      const { protocol, host, hostname, port } = window.location;
      const wsProto = protocol === 'https:' ? 'wss:' : 'ws:';
      if (port && ['5173', '5174', '5175', '3000', '4173'].includes(port)) {
        return `ws://${hostname}:8000/api/ws/simulation`;
      }
      return `${wsProto}//${host}/ws`;
    }
    return 'ws://localhost:8000/api/ws/simulation';
  };

  const wsUrl = getWsUrl();
  const { status, events, clearEvents } = useWebSocket(wsUrl);

  const [networkState, setNetworkState] = useState<NetworkState | null>(null);

  const refreshNetworkState = async () => {
    try {
      const state = await fetchNetworkState();
      setNetworkState(state);
    } catch (err) {
      console.error('Failed to fetch network state', err);
    }
  };

  useEffect(() => {
    refreshNetworkState();
  }, []);

  // Parse events to maintain authoritative network state
  useEffect(() => {
    if (events.length > 0) {
      const latestEvent = events[0];
      const evType = latestEvent.type;
      const data = latestEvent.data || {};

      if (evType === 'INITIAL_STATE' || evType === 'SIMULATION_RESET') {
        if (data.nodes && data.links) {
          setNetworkState(data);
        } else {
          refreshNetworkState();
        }
      } else if (evType === 'RUNTIME_MODE_CHANGED') {
        refreshNetworkState();
      } else if (
        evType === 'NODE_FAILED' ||
        evType === 'NODE_RECOVERED' ||
        evType === 'LINK_FAILED' ||
        evType === 'LINK_RECOVERED' ||
        evType === 'NEIGHBOR_DOWN' ||
        evType === 'NEIGHBOR_RECOVERED' ||
        evType === 'ROUTE_DISCOVERY_COMPLETED' ||
        evType === 'ROUTE_INVALIDATED'
      ) {
        refreshNetworkState();
      }
    }
  }, [events]);

  const currentMode: RuntimeMode = networkState?.mode || 'simulation';

  // Derived high-level overview indicators
  const activeNodeCount = networkState?.nodes.filter(n => n.is_active).length ?? 0;
  const totalNodeCount = networkState?.nodes.length ?? 0;
  const hasRoute = Boolean(networkState?.active_route && networkState.active_route.length > 0);
  const activeRouteStr = hasRoute ? networkState!.active_route!.join(' → ') : 'None (Idle / Searching)';

  const hasDeliveredSOS = events.some(e => e.type === 'DATA_DELIVERED' || e.type === 'SOS_DELIVERED');
  const hasConfirmedACK = events.some(e => e.type === 'ACK_RECEIVED');
  const hasLateACK = events.some(e => e.type === 'ACK_RECEIVED_LATE');
  const hasTimeoutACK = events.some(e => e.type === 'ACK_TIMEOUT');

  const latestAlert = events.find(e =>
    e.type === 'ACK_RECEIVED' ||
    e.type === 'ACK_TIMEOUT' ||
    e.type === 'ACK_RECEIVED_LATE' ||
    e.type === 'ROUTE_ERROR_PROPAGATED' ||
    e.type === 'NODE_FAILED' ||
    e.type === 'NEIGHBOR_DOWN' ||
    e.type === 'ROUTE_INVALIDATED' ||
    e.type === 'DATA_DELIVERED' ||
    e.type === 'SOS_DELIVERED'
  );

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <div className="brand-section">
          <h1>RESQNET: Disaster-Resilient AODV Communication Network</h1>
          <p className="brand-subtitle">
            Emergency Tactical Mesh • On-Demand Routing Protocol Telemetry • Live Disaster Command Center
          </p>
        </div>
        <div className="header-badges">
          <div className={`mode-badge ${currentMode}`}>
            {currentMode === 'real' ? 'Real UDP/LAN Mode' : 'Simulation Mode'}
          </div>
          <div className={`status-badge ${status.toLowerCase()}`}>
            <span className="status-dot"></span>
            WebSocket: {status}
          </div>
        </div>
      </header>

      {status !== 'CONNECTED' && (
        <div style={{
          background: 'rgba(239, 68, 68, 0.15)',
          borderBottom: '1px solid rgba(239, 68, 68, 0.35)',
          padding: '8px 16px',
          color: '#f87171',
          fontSize: '0.82rem',
          fontWeight: 500,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '8px'
        }}>
          <span>⚠️</span>
          <span>
            <strong>Live Telemetry Paused:</strong> WebSocket is {status.toLowerCase()}. Displayed topology, active routes, and performance metrics may be stale. Attempting to reconnect...
          </span>
        </div>
      )}

      {/* Incident Overview Bar */}
      <div className="incident-overview">
        <div className="overview-card">
          <span className="overview-label">Mesh Operational Status</span>
          <span className="overview-value">
            <span className="status-dot" style={{ background: totalNodeCount > 0 && activeNodeCount === totalNodeCount ? '#4ade80' : activeNodeCount > 0 ? '#fbbf24' : '#ef4444' }}></span>
            {totalNodeCount > 0 ? `${activeNodeCount}/${totalNodeCount} Nodes Online` : 'Awaiting Telemetry'}
          </span>
        </div>

        <div className="overview-card">
          <span className="overview-label">Active Verified AODV Route</span>
          <span className={`overview-value ${hasRoute ? 'active' : ''}`} style={{ fontFamily: 'monospace' }}>
            {activeRouteStr}
          </span>
        </div>

        <div className="overview-card">
          <span className="overview-label">End-to-End Hospital ACK</span>
          <span className={`overview-value ${hasConfirmedACK ? 'healthy' : hasTimeoutACK ? 'error' : hasDeliveredSOS ? 'healthy' : ''}`}>
            <span className="status-dot" style={{ background: hasConfirmedACK ? '#4ade80' : hasLateACK ? '#fbbf24' : hasTimeoutACK ? '#ef4444' : hasDeliveredSOS ? '#38bdf8' : 'var(--text-muted)' }}></span>
            {hasConfirmedACK ? 'ACK Confirmed at Rescue-A' : hasLateACK ? 'Late ACK Received' : hasTimeoutACK ? 'ACK Timed Out' : hasDeliveredSOS ? 'Delivered at Hospital (Pending ACK)' : 'Standby'}
          </span>
        </div>

        <div className="overview-card">
          <span className="overview-label">Latest Incident / Protocol Action</span>
          <span className="overview-value" style={{ fontSize: '0.85rem' }}>
            {latestAlert ? `${latestAlert.type.replace(/_/g, ' ')}` : 'System Normal'}
          </span>
        </div>
      </div>

      {/* Guided Disaster Demonstration Presentation Bar */}
      <GuidedDemoPanel events={events} />

      <div className="dashboard-grid">
        <div className="col-main">
          <div className="panel topology-panel">
            <h2>Network Topology</h2>
            {networkState ? (
              <TopologyView networkState={networkState} events={events} />
            ) : (
              <p>Loading topology...</p>
            )}
          </div>

          <div className="panel-row">
            {networkState ? <SOSPanel networkState={networkState} events={events} /> : <div className="panel">Loading SOS...</div>}
            <HospitalPanel events={events} />
          </div>
        </div>

        <div className="col-side">
          <ControlsPanel networkState={networkState} onNetworkUpdate={refreshNetworkState} />
          <MetricsPanel events={events} networkState={networkState} />
          <EventLog events={events} onClear={clearEvents} />
        </div>
      </div>
    </div>
  );
}

export default App;

