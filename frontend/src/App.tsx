import { useState, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import type { NetworkState } from './types';
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
      if (latestEvent.type === 'INITIAL_STATE' || latestEvent.type === 'SIMULATION_RESET') {
        setNetworkState(latestEvent.data);
      } else if (latestEvent.type === 'NODE_FAILED') {
        setNetworkState(prev => prev ? {
          ...prev, 
          nodes: prev.nodes.map(n => n.node_id === latestEvent.data.node_id ? { ...n, is_active: false } : n)
        } : null);
      } else if (latestEvent.type === 'NODE_RECOVERED') {
        setNetworkState(prev => prev ? {
          ...prev, 
          nodes: prev.nodes.map(n => n.node_id === latestEvent.data.node_id ? { ...n, is_active: true } : n)
        } : null);
      } else if (latestEvent.type === 'LINK_FAILED') {
        setNetworkState(prev => prev ? {
          ...prev,
          links: prev.links.map(l => 
            (l.node_a_id === latestEvent.data.node_a_id && l.node_b_id === latestEvent.data.node_b_id) ||
            (l.node_a_id === latestEvent.data.node_b_id && l.node_b_id === latestEvent.data.node_a_id)
              ? { ...l, is_active: false } : l
          )
        } : null);
      } else if (latestEvent.type === 'LINK_RECOVERED') {
        setNetworkState(prev => prev ? {
          ...prev,
          links: prev.links.map(l => 
            (l.node_a_id === latestEvent.data.node_a_id && l.node_b_id === latestEvent.data.node_b_id) ||
            (l.node_a_id === latestEvent.data.node_b_id && l.node_b_id === latestEvent.data.node_a_id)
              ? { ...l, is_active: true } : l
          )
        } : null);
      }
    }
  }, [events]);

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>RESQNET: Disaster-Resilient AODV Communication Network</h1>
        <div className={`status-badge ${status.toLowerCase()}`}>
          WebSocket: {status}
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
            <SOSPanel />
            <HospitalPanel events={events} />
          </div>
        </div>

        <div className="col-side">
          <ControlsPanel />
          <MetricsPanel events={events} />
          <EventLog events={events} onClear={clearEvents} />
        </div>
      </div>
    </div>
  );
}

export default App;
