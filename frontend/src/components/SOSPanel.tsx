import { useState, useEffect } from 'react';
import { sendSOS } from '../services/api';
import type { NetworkState, WSEvent } from '../types';

interface SOSPanelProps {
  networkState: NetworkState;
  events?: WSEvent[];
}

const SOSPanel = ({ networkState, events = [] }: SOSPanelProps) => {
  const [source, setSource] = useState('A');
  const [message, setMessage] = useState('HELP REQUIRED - IMMEDIATE EVACUATION');
  const [priority, setPriority] = useState('CRITICAL');
  const [isSending, setIsSending] = useState(false);
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error' | 'info'; text: string } | null>(null);

  // Listen for live ACK events
  useEffect(() => {
    if (events.length > 0) {
      const latest = events[0];
      if (latest.type === 'ACK_RECEIVED') {
        const d = latest.data || {};
        setFeedback({
          type: 'success',
          text: `✓ Hospital Return ACK Verified! RTT: ${d.rtt_ms ?? 0}ms. Full bidirectional path confirmed.`
        });
      } else if (latest.type === 'ACK_TIMEOUT') {
        setFeedback({
          type: 'error',
          text: '⚠️ Hospital Return ACK timed out after configured deadline.'
        });
      } else if (latest.type === 'ACK_RECEIVED_LATE') {
        const d = latest.data || {};
        setFeedback({
          type: 'info',
          text: `ℹ️ Delayed Hospital Return ACK received and confirmed late (RTT: ${d.rtt_ms ?? 0}ms).`
        });
      }
    }
  }, [events]);

  const selectedNode = networkState.nodes.find(n => n.node_id === source);
  const lat = selectedNode ? selectedNode.latitude.toFixed(4) : '18.5204';
  const lon = selectedNode ? selectedNode.longitude.toFixed(4) : '73.8567';

  const PRESETS = [
    { label: 'Immediate Evacuation', text: 'HELP REQUIRED - IMMEDIATE EVACUATION', priority: 'CRITICAL' },
    { label: 'Medical Aid Needed', text: 'CASUALTY REPORTED - MEDICAL AID REQUIRED', priority: 'HIGH' },
    { label: 'Relay Check / SITREP', text: 'RESCUE UNIT STATUS OK - MESH CHECK', priority: 'MEDIUM' }
  ];

  const handleSendSOS = async () => {
    if (!selectedNode) return;
    if (isSending) return; // Prevent duplicate rapid clicks

    setIsSending(true);
    setFeedback({ type: 'info', text: 'Dispatching emergency SOS to network...' });

    try {
      const res = await sendSOS({
        source_id: source,
        destination_id: 'H',
        message,
        latitude: selectedNode.latitude,
        longitude: selectedNode.longitude,
        priority
      });

      if (res && (res.success || res.status === 'success' || !res.error)) {
        setFeedback({
          type: 'success',
          text: `SOS dispatched from Node ${source} to Hospital H. AODV discovering route.`
        });
      } else {
        setFeedback({
          type: 'error',
          text: res?.error || 'Failed to dispatch SOS signal.'
        });
      }
    } catch (err: any) {
      setFeedback({
        type: 'error',
        text: err?.message || 'Network error communicating with backend.'
      });
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="panel" style={{ borderLeft: '4px solid #ef4444' }}>
      <h2>
        <span style={{ color: '#f87171', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>🚨</span> Emergency SOS Dispatch
        </span>
        <span style={{ fontSize: '0.72rem', color: '#94a3b8', fontWeight: 500 }}>Target: Hospital-H</span>
      </h2>

      {/* Quick Scenario Presets */}
      <div style={{ display: 'flex', gap: '6px', marginBottom: '12px' }}>
        {PRESETS.map(p => (
          <button
            key={p.label}
            type="button"
            onClick={() => { setMessage(p.text); setPriority(p.priority); }}
            style={{
              fontSize: '0.72rem',
              padding: '4px 8px',
              background: '#131c31',
              border: '1px solid #334155',
              flex: 1,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis'
            }}
          >
            {p.label}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
        <div className="form-group">
          <label>Source Node</label>
          <select value={source} onChange={(e) => setSource(e.target.value)}>
            {networkState.nodes.filter(n => n.node_id !== 'H').map(n => (
              <option key={n.node_id} value={n.node_id}>
                {n.node_id === 'A' ? 'Rescue-A' : `Relay-${n.node_id}`} ({n.endpoint || n.ip_address})
              </option>
            ))}
          </select>
        </div>

        <div className="form-group">
          <label>Priority Level</label>
          <select value={priority} onChange={(e) => setPriority(e.target.value)}>
            <option value="CRITICAL">Critical (Life Threatening)</option>
            <option value="HIGH">High Priority</option>
            <option value="MEDIUM">Medium / Informational</option>
          </select>
        </div>
      </div>

      <div className="form-group">
        <label>Distress Message Payload</label>
        <textarea
          rows={2}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Enter distress message..."
        />
      </div>

      <div className="form-group">
        <label>GPS Coordinates</label>
        <input
          type="text"
          value={`Latitude: ${lat}° N, Longitude: ${lon}° E`}
          disabled
          style={{ color: '#94a3b8', fontSize: '0.8rem', background: '#0a0f1d' }}
        />
      </div>

      {feedback && (
        <div style={{
          padding: '6px 10px',
          borderRadius: '4px',
          fontSize: '0.78rem',
          marginBottom: '10px',
          background: feedback.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : feedback.type === 'error' ? 'rgba(239, 68, 68, 0.15)' : 'rgba(56, 189, 248, 0.15)',
          color: feedback.type === 'success' ? '#34d399' : feedback.type === 'error' ? '#f87171' : '#38bdf8',
          border: `1px solid ${feedback.type === 'success' ? '#059669' : feedback.type === 'error' ? '#dc2626' : '#0284c7'}`
        }}>
          {feedback.text}
        </div>
      )}

      <button
        type="button"
        className="danger"
        onClick={handleSendSOS}
        disabled={isSending || !selectedNode?.is_active}
        style={{ width: '100%', marginTop: 'auto', padding: '10px', fontSize: '0.92rem', letterSpacing: '0.5px' }}
      >
        {isSending ? 'DISPATCHING SOS...' : '🚨 BROADCAST EMERGENCY SOS'}
      </button>
    </div>
  );
};

export default SOSPanel;
