import { useState } from 'react';
import { sendSOS } from '../services/api';
import { NetworkState } from '../types';

const SOSPanel = ({ networkState }: { networkState: NetworkState }) => {
  const [source, setSource] = useState('A');
  const [message, setMessage] = useState('HELP REQUIRED');
  const [priority, setPriority] = useState('HIGH');

  const selectedNode = networkState.nodes.find(n => n.node_id === source);
  const lat = selectedNode ? selectedNode.latitude.toFixed(4) : '';
  const lon = selectedNode ? selectedNode.longitude.toFixed(4) : '';

  const handleSendSOS = async () => {
    if (!selectedNode) return;
    await sendSOS({
      source_id: source,
      destination_id: 'H',
      message,
      latitude: selectedNode.latitude,
      longitude: selectedNode.longitude,
      priority
    });
  };

  return (
    <div className="panel" style={{ borderLeft: '4px solid #d32f2f' }}>
      <h2>SOS Dispatch</h2>
      <div className="form-group">
        <label>Node (Source)</label>
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          {networkState.nodes.filter(n => n.node_id !== 'H').map(n => (
            <option key={n.node_id} value={n.node_id}>Node {n.node_id} ({n.ip_address})</option>
          ))}
        </select>
      </div>
      <div className="form-group">
        <label>Priority</label>
        <select value={priority} onChange={(e) => setPriority(e.target.value)}>
          <option value="CRITICAL">Critical</option>
          <option value="HIGH">High</option>
          <option value="MEDIUM">Medium</option>
        </select>
      </div>
      <div className="form-group">
        <label>Message</label>
        <textarea 
          rows={3} 
          value={message} 
          onChange={(e) => setMessage(e.target.value)}
        />
      </div>
      <div className="form-group">
        <label>Location</label>
        <input type="text" value={`Lat: ${lat}, Lon: ${lon}`} disabled />
      </div>
      <button className="danger" onClick={handleSendSOS} style={{ width: '100%', marginTop: 'auto' }}>
        SEND SOS
      </button>
    </div>
  );
};

export default SOSPanel;
