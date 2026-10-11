import { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import type { NetworkState, RuntimeMode } from './types';
import TopologyView from './components/TopologyView';
import EventLog from './components/EventLog';
import MetricsPanel from './components/MetricsPanel';
import ControlsPanel from './components/ControlsPanel';
import SOSPanel from './components/SOSPanel';
import HospitalPanel from './components/HospitalPanel';
import './App.css';

function App() {
  const wsUrl = `ws://${window.location.hostname}:8000/api/ws/simulation`;
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

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>RESQNET: Disaster-Resilient AODV Communication Network</h1>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div className={`mode-badge ${currentMode}`}>
            {currentMode === 'real' ? 'Real UDP/LAN Mode' : 'Simulation Mode'}
          </div>
          <div className={`status-badge ${status.toLowerCase()}`}>
            WebSocket: {status}
          </div>
        </div>
      </header>

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
            {networkState ? <SOSPanel networkState={networkState} /> : <div className="panel">Loading SOS...</div>}
            <HospitalPanel events={events} />
          </div>
        </div>

        <div className="col-side">
          <ControlsPanel networkState={networkState} />
          <MetricsPanel events={events} />
          <EventLog events={events} onClear={clearEvents} />
        </div>
      </div>
    </div>
  );
}

export default App;

