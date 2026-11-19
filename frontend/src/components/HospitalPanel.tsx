import { useState, useEffect } from 'react';
import type { WSEvent, SOSMessage } from '../types';
import { getHospitalInbox, respondHospital, getHospitalKey, setHospitalKey } from '../services/api';

interface HospitalPanelProps {
  events: WSEvent[];
}

const HospitalPanel = ({ events }: HospitalPanelProps) => {
  const [inbox, setInbox] = useState<SOSMessage[]>([]);
  const [responseMsg, setResponseMsg] = useState<{ [key: string]: string }>({});
  const [isReplying, setIsReplying] = useState<{ [key: string]: boolean }>({});
  const [sentReplies, setSentReplies] = useState<{ [key: string]: string }>({});
  const [clinicianKey, setClinicianKey] = useState<string>(getHospitalKey());
  const [replyError, setReplyError] = useState<{ [key: string]: string }>({});

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

  // Update inbox when real SOS_DELIVERED event arrives or reset happens
  useEffect(() => {
    if (events.length > 0) {
      if (events.some(e => e.type === 'SIMULATION_RESET')) {
        setInbox([]);
        return;
      }

      const hasSosDelivered = events.some(e => e.type === 'SOS_DELIVERED' || e.type === 'DATA_DELIVERED');
      if (hasSosDelivered) {
        // Optimistically insert from event if available
        const sosEvents = events.filter(e => e.type === 'SOS_DELIVERED' && e.data?.message_id);
        if (sosEvents.length > 0) {
          setInbox(prev => {
            const map = new Map(prev.map(m => [m.message_id, m]));
            for (const ev of sosEvents) {
              if (!map.has(ev.data.message_id)) {
                map.set(ev.data.message_id, ev.data);
              }
            }
            return Array.from(map.values());
          });
        }
        // Authoritatively sync with backend inbox
        getHospitalInbox().then(setInbox).catch(console.error);
      }
    }
  }, [events]);

  const handleRespond = async (sourceId: string, messageId: string) => {
    const msg = responseMsg[messageId] || 'Hospital triage team dispatched. Hold position.';
    setIsReplying(prev => ({ ...prev, [messageId]: true }));
    setReplyError(prev => ({ ...prev, [messageId]: '' }));
    try {
      await respondHospital('H', sourceId, msg, messageId);
      setSentReplies(prev => ({ ...prev, [messageId]: msg }));
      setResponseMsg(prev => ({ ...prev, [messageId]: '' }));
    } catch (err: any) {
      console.error('Failed to send hospital reply', err);
      setReplyError(prev => ({ ...prev, [messageId]: err?.message || 'Failed to dispatch triage response' }));
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

      {/* Clinician Authentication Credential */}
      <div style={{ marginBottom: '12px', padding: '6px 10px', background: 'var(--bg-surface)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
          <span style={{ fontSize: '0.7rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600 }}>
            Clinician Credential (X-Hospital-Key)
          </span>
          <span style={{ fontSize: '0.66rem', color: '#64748b' }}>
            Required in authenticated production
          </span>
        </div>
        <input
          type="password"
          placeholder="Enter clinician triage key if configured"
          value={clinicianKey}
          onChange={(e) => {
            setClinicianKey(e.target.value);
            setHospitalKey(e.target.value);
          }}
          style={{
            width: '100%',
            padding: '4px 8px',
            fontSize: '0.75rem',
            background: 'var(--bg-card)',
            border: '1px solid var(--border-subtle)',
            borderRadius: '4px',
            color: 'var(--text-main)',
            boxSizing: 'border-box'
          }}
        />
      </div>

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
                  <span>🚨</span> SOS from {sos.source_id === 'A' ? 'Rescue-A' : ['B', 'C', 'D'].includes(sos.source_id) ? `Relay-${sos.source_id}` : `Node-${sos.source_id}`}
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

              {sentReplies[sos.message_id] && (
                <div style={{ fontSize: '0.74rem', color: '#34d399', background: 'rgba(52, 211, 153, 0.1)', padding: '4px 8px', borderRadius: '4px', border: '1px solid rgba(52, 211, 153, 0.2)' }}>
                  ✓ Response Dispatched: "{sentReplies[sos.message_id]}"
                </div>
              )}

              {replyError[sos.message_id] && (
                <div style={{ fontSize: '0.74rem', color: '#f87171', background: 'rgba(239, 68, 68, 0.1)', padding: '4px 8px', borderRadius: '4px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                  ⚠️ {replyError[sos.message_id]}
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
