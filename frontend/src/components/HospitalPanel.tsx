import { useState, useEffect } from 'react';
import type { WSEvent, SOSMessage } from '../types';
import { getHospitalInbox, respondHospital } from '../services/api';

interface HospitalPanelProps {
  events: WSEvent[];
}

const HospitalPanel = ({ events }: HospitalPanelProps) => {
  const [inbox, setInbox] = useState<SOSMessage[]>([]);
  const [responseMsg, setResponseMsg] = useState<{ [key: string]: string }>({});

  useEffect(() => {
    const fetchInbox = async () => {
      try {
        const data = await getHospitalInbox();
        setInbox(data);
      } catch (err) {
        console.error('Failed to fetch hospital inbox', err);
      }
    };
    fetchInbox();
  }, []);

  useEffect(() => {
    if (events.length > 0) {
      const latestEvent = events[0];
      if (latestEvent.type === 'SOS_DELIVERED') {
        const sos: SOSMessage = latestEvent.data;
        setInbox(prev => {
          if (!prev.find(m => m.message_id === sos.message_id)) {
            return [sos, ...prev];
          }
          return prev;
        });
      }
    }
  }, [events]);

  const handleRespond = async (sourceId: string, messageId: string) => {
    const msg = responseMsg[messageId] || 'Assistance is on the way.';
    await respondHospital('H', sourceId, msg);
    setResponseMsg(prev => ({ ...prev, [messageId]: '' }));
  };

  return (
    <div className="panel" style={{ borderLeft: '4px solid #388e3c', overflowY: 'auto', maxHeight: '400px' }}>
      <h2>Hospital Dashboard (H)</h2>
      <div className="message-list">
        {inbox.length === 0 ? (
          <p style={{ color: '#888', fontStyle: 'italic', textAlign: 'center', marginTop: '20px' }}>
            No incoming SOS messages.
          </p>
        ) : (
          inbox.map(sos => (
            <div key={sos.message_id} className="message-card sos" style={{ marginBottom: '15px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <strong style={{ color: '#ef5350' }}>SOS from Node {sos.source_id}</strong>
                <span style={{ fontSize: '0.8rem', color: '#aaa' }}>
                  {new Date(sos.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <div style={{ fontSize: '0.8rem', color: '#ccc', marginBottom: '5px' }}>
                <span>Priority: {sos.priority} | Lat: {sos.latitude.toFixed(4)}, Lon: {sos.longitude.toFixed(4)}</span>
              </div>
              <p style={{ fontSize: '0.9rem', marginBottom: '10px' }}>{sos.message}</p>
              
              <div style={{ display: 'flex', gap: '5px' }}>
                <input 
                  type="text" 
                  placeholder="Response message..."
                  value={responseMsg[sos.message_id] || ''}
                  onChange={e => setResponseMsg(prev => ({ ...prev, [sos.message_id]: e.target.value }))}
                  style={{ flex: 1, padding: '5px', background: '#222', color: '#fff', border: '1px solid #444' }}
                />
                <button 
                  onClick={() => handleRespond(sos.source_id, sos.message_id)}
                  style={{ padding: '5px 10px', background: '#388e3c', border: 'none', color: '#fff', cursor: 'pointer' }}
                >
                  Reply
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default HospitalPanel;
