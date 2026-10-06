import type { WSEvent } from '../types';


interface EventLogProps {
  events: WSEvent[];
  onClear: () => void;
}

const EventLog = ({ events, onClear }: EventLogProps) => {
  return (
    <div className="panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2>Event Log</h2>
        <button onClick={onClear} style={{ padding: '2px 8px', fontSize: '12px' }}>Clear</button>
      </div>
      <div className="event-log">
        {events.map((evt) => (
          <div key={evt.event_id} className="log-entry">
            <span className="log-time">
              {new Date(evt.timestamp).toLocaleTimeString()}
            </span>
            <span className="log-type">{evt.type}</span>
            {evt.data.from_node && evt.data.to_node && (
              <div>{evt.data.from_node} &rarr; {evt.data.to_node}</div>
            )}
            {evt.data.node_id && <div>Node: {evt.data.node_id}</div>}
            {evt.data.packet_id && <div>Pkt: {evt.data.packet_id.substring(0, 8)}</div>}
          </div>
        ))}
      </div>
    </div>
  );
};

export default EventLog;
