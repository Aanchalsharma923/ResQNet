import { useState, useEffect } from 'react';
import type { WSEvent, SOSMessage } from '../types';
import { getHospitalInbox, respondHospital } from '../services/api';

interface HospitalPanelProps {
  events: WSEvent[];
}

const HospitalPanel = ({ events }: HospitalPanelProps) => {
  const [inbox, setInbox] = useState<SOSMessage[]>([]);
  const [responseMsg, setResponseMsg] = useState<{ [key: string]: string }>({});
  const [isReplying, setIsReplying] = useState<{ [key: string]: boolean }>({});

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

  // Update inbox when real SOS_DELIVERED event arrives
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
    const msg = responseMsg[messageId] || 'Hospital triage team dispatched. Hold position.';
    setIsReplying(prev => ({ ...prev, [messageId]: true }));
    try {
      await respondHospital('H', sourceId, msg);
      setResponseMsg(prev => ({ ...prev, [messageId]: '' }));
    } catch (err) {
      console.error('Failed to send hospital reply', err);
    } finally {
      setIsReplying(prev => ({ ...prev, [messageId]: false }));
    }
  };

  return (
    <div className="panel hospital-panel">
      <h2>
        <span style={{ color: '#34d399', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <span>🏥</span> Hospital Operations Dashboard (Node H)
        </span>
        <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 500 }}>
          {inbox.length} Confirmed {inbox.length === 1 ? 'Incident' : 'Incidents'}
        </span>
      </h2>

      <div className="hospital-inbox-list">
        {inbox.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '30px 10px', color: '#64748b' }}>
            <p style={{ fontSize: '0.88rem', fontStyle: 'italic', marginBottom: '4px' }}>
              No incoming emergency SOS signals received.
            </p>
            <p style={{ fontSize: '0.74rem', color: '#475569' }}>
              Hospital inbox updates strictly upon authenticated destination packet arrival.
            </p>
          </div>
        ) : (
          inbox.map(sos => (
            <div key={sos.message_id} className="sos-card">
              <div className="sos-card-header">
                <span className="sos-card-title">
                  <span>🚨</span> SOS from Rescue-{sos.source_id}
                </span>
                <span className="sos-delivery-badge">
                  ✓ Received & Verified at Hospital
                </span>
              </div>

              <div className="sos-card-meta" style={{ display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: '4px' }}>
                <span>
                  <strong>Priority:</strong> <span style={{ color: sos.priority === 'CRITICAL' ? '#f87171' : '#fbbf24' }}>{sos.priority}</span>
                  {sos.latitude && sos.longitude && (
                    <span style={{ marginLeft: '8px' }}>
                      | <strong>GPS:</strong> {sos.latitude.toFixed(4)}°, {sos.longitude.toFixed(4)}°
                    </span>
                  )}
                  {sos.hop_count !== undefined && (
                    <span style={{ marginLeft: '8px' }}>
                      | <strong>Hops:</strong> {sos.hop_count}
                    </span>
                  )}
                </span>
                <span style={{ color: '#94a3b8' }}>
                  {new Date(sos.timestamp).toLocaleTimeString()}
                </span>
              </div>

              <div className="sos-card-body">
                "{sos.message}"
              </div>

              {sos.message_id && (
                <div style={{ fontSize: '0.68rem', color: '#64748b', fontFamily: 'monospace' }}>
                  MSG-ID: {sos.message_id}
                </div>
              )}

              {/* Response to sender */}
              <div style={{ display: 'flex', gap: '6px', marginTop: '4px' }}>
                <input 
                  type="text" 
                  placeholder="Transmit hospital response to field unit..."
                  value={responseMsg[sos.message_id] || ''}
                  onChange={e => setResponseMsg(prev => ({ ...prev, [sos.message_id]: e.target.value }))}
                  style={{ flex: 1, padding: '6px 10px', fontSize: '0.8rem' }}
                />
                <button 
                  type="button"
                  className="success"
                  disabled={isReplying[sos.message_id]}
                  onClick={() => handleRespond(sos.source_id, sos.message_id)}
                  style={{ padding: '6px 12px', fontSize: '0.8rem', whiteSpace: 'nowrap' }}
                >
                  {isReplying[sos.message_id] ? 'Transmitting...' : 'Reply'}
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
