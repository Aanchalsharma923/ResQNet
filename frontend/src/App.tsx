import { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import type { NetworkState, RuntimeMode } from './types';
import TopologyView from './components/TopologyView';
import EventLog from './components/EventLog';
import MetricsPanel from './components/MetricsPanel';
import ControlsPanel from './components/ControlsPanel';
import SOSPanel from './components/SOSPanel';
import HospitalPanel from './components/HospitalPanel';
import GuidedDemoPanel from './components/GuidedDemoPanel';
import './App.css';

function App() {
  const host = typeof window !== 'undefined' && window.location?.hostname ? window.location.hostname : 'localhost';
  const wsUrl = (import.meta as any).env?.VITE_WS_URL || `ws://${host}:8000/api/ws/simulation`;
  const { status, events, clearEvents } = useWebSocket(wsUrl);

  const [networkState, setNetworkState] = useState<NetworkState | null>(null);

  // Parse events to maintain local network state
  useEffect(() => {
    if (events.length > 0) {
      const latestEvent = events[0];
      const evType = latestEvent.type;
      const data = latestEvent.data || {};

      if (evType === 'INITIAL_STATE' || evType === 'SIMULATION_RESET') {
        setNetworkState(data);
      } else if (evType === 'RUNTIME_MODE_CHANGED') {
        setNetworkState(prev => prev ? { ...prev, mode: data.mode } : null);
      } else if (evType === 'NODE_FAILED') {
        setNetworkState(prev => {
          if (!prev) return null;
          const failedId = data.node_id;
          const newRoute = prev.active_route ? prev.active_route.filter(n => n !== failedId) : [];
          return {
            ...prev,
            nodes: prev.nodes.map(n => n.node_id === failedId ? { ...n, is_active: false } : n),
            active_route: newRoute.length === (prev.active_route?.length || 0) ? prev.active_route : []
          };
        });
      } else if (evType === 'NODE_RECOVERED') {
        setNetworkState(prev => prev ? {
          ...prev,
          nodes: prev.nodes.map(n => n.node_id === data.node_id ? { ...n, is_active: true } : n)
        } : null);
      } else if (evType === 'NEIGHBOR_DOWN') {
        setNetworkState(prev => {
          if (!prev) return null;
          const neighborId = data.neighbor_id;
          const shouldClearRoute = prev.active_route?.includes(neighborId);
          return {
            ...prev,
            nodes: prev.nodes.map(n => n.node_id === neighborId ? { ...n, is_active: false } : n),
            active_route: shouldClearRoute ? [] : prev.active_route
          };
        });
      } else if (evType === 'NEIGHBOR_RECOVERED') {
        setNetworkState(prev => prev ? {
          ...prev,
          nodes: prev.nodes.map(n => n.node_id === data.neighbor_id ? { ...n, is_active: true } : n)
        } : null);
      } else if (evType === 'ROUTE_DISCOVERY_COMPLETED' || evType === 'FORWARD_ROUTE_INSTALLED') {
        if (data.active_route) {
          setNetworkState(prev => prev ? { ...prev, active_route: data.active_route } : null);
        }
      } else if (evType === 'ROUTE_INVALIDATED') {
        setNetworkState(prev => prev ? { ...prev, active_route: [] } : null);
      } else if (evType === 'LINK_FAILED') {
        setNetworkState(prev => prev ? {
          ...prev,
          links: prev.links.map(l =>
            (l.node_a_id === data.node_a_id && l.node_b_id === data.node_b_id) ||
            (l.node_a_id === data.node_b_id && l.node_b_id === data.node_a_id)
              ? { ...l, is_active: false } : l
          )
        } : null);
      } else if (evType === 'LINK_RECOVERED') {
        setNetworkState(prev => prev ? {
          ...prev,
          links: prev.links.map(l =>
            (l.node_a_id === data.node_a_id && l.node_b_id === data.node_b_id) ||
            (l.node_a_id === data.node_b_id && l.node_b_id === data.node_a_id)
              ? { ...l, is_active: true } : l
          )
        } : null);
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
          <ControlsPanel networkState={networkState} />
          <MetricsPanel events={events} networkState={networkState} />
          <EventLog events={events} onClear={clearEvents} />
        </div>
      </div>
    </div>
  );
}

export default App;

