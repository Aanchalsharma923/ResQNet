import type { WSEvent } from '../types';

interface HospitalPanelProps {
  events: WSEvent[];
}

const HospitalPanel = ({ events }: HospitalPanelProps) => {
  // Filter for DATA_DELIVERED to Node H
  const deliveredMessages = events.filter(e => 
    e.type === 'DATA_DELIVERED' && 
    e.data.destination_id === 'H'
  );

  return (
    <div className="panel" style={{ borderLeft: '4px solid #388e3c' }}>
      <h2>Hospital Dashboard (H)</h2>
      <div className="message-list">
        {deliveredMessages.length === 0 ? (
          <p style={{ color: '#888', fontStyle: 'italic', textAlign: 'center', marginTop: '20px' }}>
            No incoming SOS messages.
          </p>
        ) : (
          deliveredMessages.map(evt => (
            <div key={evt.event_id} className="message-card sos">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '5px' }}>
                <strong style={{ color: '#ef5350' }}>SOS from Node {evt.data.sender_id}</strong>
                <span style={{ fontSize: '0.8rem', color: '#aaa' }}>
                  {new Date(evt.timestamp).toLocaleTimeString()}
                </span>
              </div>
              <p style={{ fontSize: '0.9rem' }}>{evt.data.payload}</p>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default HospitalPanel;
