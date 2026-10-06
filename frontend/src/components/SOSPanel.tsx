import { useState } from 'react';
import { sendMessage } from '../services/api';

const SOSPanel = () => {
  const [source, setSource] = useState('A');
  const [message, setMessage] = useState('HELP REQUIRED');

  const handleSendSOS = async () => {
    await sendMessage(source, 'H', message);
  };

  return (
    <div className="panel" style={{ borderLeft: '4px solid #d32f2f' }}>
      <h2>SOS Dispatch</h2>
      <div className="form-group">
        <label>Node (Source)</label>
        <select value={source} onChange={(e) => setSource(e.target.value)}>
          <option value="A">Rescue-A (192.168.1.10)</option>
          <option value="B">Relay-B (192.168.1.11)</option>
          <option value="C">Relay-C (192.168.1.12)</option>
          <option value="D">Relay-D (192.168.1.13)</option>
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
        <input type="text" value="Simulation Coordinates" disabled />
      </div>
      <button className="danger" onClick={handleSendSOS} style={{ width: '100%', marginTop: 'auto' }}>
        SEND SOS
      </button>
    </div>
  );
};

export default SOSPanel;
