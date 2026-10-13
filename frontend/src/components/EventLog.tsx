import { useState } from 'react';
import type { WSEvent } from '../types';

interface EventLogProps {
  events: WSEvent[];
  onClear: () => void;
}

interface Narrative {
  title: string;
  desc: string;
  category: 'success' | 'alert' | 'warning' | 'info';
}

const getEventNarrative = (evt: WSEvent): Narrative => {
  const t = evt.type;
  const d = evt.data || {};

  if (t === 'INITIAL_STATE' || t === 'SIMULATION_RESET') {
    return {
      title: 'Topology State Synchronized',
      desc: 'Network state and active node baseline synchronized from runtime engine.',
      category: 'info'
    };
  }

  if (t === 'RREQ_GENERATED' || t === 'RREQ_CREATED') {
    const src = d.node_id || d.source_id || 'A';
    const dest = d.destination_id || 'H';
    return {
      title: 'AODV Route Request Initiated',
      desc: `Rescue-${src} is flooding RREQ to discover a path to Hospital-${dest}.`,
      category: 'warning'
    };
  }
  if (t === 'RREP_GENERATED') {
    return {
      title: 'Route Reply (RREP) Emitted',
      desc: `Hospital-${d.node_id || 'H'} accepted route request; unicasting RREP back to source.`,
      category: 'success'
    };
  }
  if (t === 'ROUTE_DISCOVERY_COMPLETED' || t === 'FORWARD_ROUTE_INSTALLED') {
    const next = d.next_hop || d.next || 'relay';
    return {
      title: 'AODV Path Established',
      desc: `Node ${d.node_id || 'A'} installed forward route to destination via Relay-${next}.`,
      category: 'success'
    };
  }
  if (t === 'NODE_FAILED') {
    return {
      title: 'Relay Failure Detected',
      desc: `Relay-${d.node_id} is down/unreachable.`,
      category: 'alert'
    };
  }
  if (t === 'NEIGHBOR_DOWN') {
    return {
      title: 'Neighbor Timeout Detected',
      desc: `Node ${d.node_id} detected loss of HELLO beacons from Relay-${d.neighbor_id}.`,
      category: 'alert'
    };
  }
  if (t === 'ROUTE_INVALIDATED') {
    return {
      title: 'Active Route Invalidated',
      desc: `Route to ${d.dest || d.destination || 'destination'} marked invalid due to severed link.`,
      category: 'alert'
    };
  }
  if (t === 'RERR_GENERATED' || t === 'RERR_FORWARDED') {
    return {
      title: 'Route Error (RERR) Broadcast',
      desc: `Notifying upstream precursors that the previous path is broken.`,
      category: 'warning'
    };
  }
  if (t === 'SOS_SENT' || t === 'DATA_CREATED') {
    return {
      title: 'Emergency SOS Dispatched',
      desc: `Rescue-${d.source_id || 'A'} transmitted high-priority emergency payload.`,
      category: 'info'
    };
  }
  if (t === 'DATA_FORWARDED') {
    return {
      title: 'Data Forwarded Along Path',
      desc: `Forwarded: ${d.from_node || d.node_id} → ${d.to_node || 'next hop'}.`,
      category: 'info'
    };
  }
  if (t === 'SOS_DELIVERED' || t === 'DATA_DELIVERED') {
    return {
      title: 'SOS Delivered at Hospital',
      desc: `Hospital-H validated and delivered packet to hospital application inbox.`,
      category: 'success'
    };
  }
  if (t === 'DATA_DROPPED') {
    return {
      title: 'Packet Dropped',
      desc: `Discarded: ${d.reason || 'No route available'}.`,
      category: 'alert'
    };
  }
  if (t === 'ACK_SENT') {
    return {
      title: 'Hospital Return ACK Dispatched',
      desc: `Hospital-H generated return ACK DATA packet addressed to Rescue-${d.destination_id || 'A'}.`,
      category: 'info'
    };
  }
  if (t === 'ACK_RECEIVED') {
    return {
      title: 'Hospital ACK Verified at Rescue Unit',
      desc: `Rescue-${d.source_id || 'A'} verified authentic return ACK from Hospital-${d.hospital_id || 'H'} (RTT: ${d.rtt_ms || '0'}ms). Bidirectional delivery confirmed!`,
      category: 'success'
    };
  }
  if (t === 'ACK_TIMEOUT') {
    return {
      title: 'Hospital ACK Timeout',
      desc: `Rescue-${d.source_id || 'A'} did not receive return ACK within configured deadline (${d.timeout_sec || 5}s).`,
      category: 'alert'
    };
  }
  if (t === 'ACK_RECEIVED_LATE') {
    return {
      title: 'Delayed Hospital ACK Accepted',
      desc: `Rescue-${d.source_id || 'A'} received delayed return ACK after deadline expiration (RTT: ${d.rtt_ms || '0'}ms). Status transitioned to LATE_CONFIRMED.`,
      category: 'warning'
    };
  }
  if (t === 'ACK_DUPLICATE_IGNORED') {
    return {
      title: 'Duplicate ACK Safely Ignored',
      desc: `Rescue-${d.source_id || 'A'} safely ignored duplicate return ACK.`,
      category: 'info'
    };
  }
  if (t === 'NEIGHBOR_HELLO_SENT') {
    return {
      title: 'Heartbeat Beacon',
      desc: `Node ${d.node_id} pinged neighbor ${d.neighbor_id}.`,
      category: 'info'
    };
  }

  return {
    title: t,
    desc: `Event notification from network runtime.`,
    category: 'info'
  };
};

const EventLog = ({ events, onClear }: EventLogProps) => {
  const [filterHellos, setFilterHellos] = useState(true);
  const [viewMode, setViewMode] = useState<'timeline' | 'technical'>('timeline');

  // Filter out repetitive HELLO heartbeats when filter is active
  const filteredEvents = filterHellos
    ? events.filter(e => e.type !== 'NEIGHBOR_HELLO_SENT')
    : events;

  return (
    <div className="panel">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
        <h2>Incident Timeline & Events</h2>
        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
          <button
            type="button"
            onClick={() => setViewMode(prev => prev === 'timeline' ? 'technical' : 'timeline')}
            style={{ padding: '3px 8px', fontSize: '11px' }}
          >
            {viewMode === 'timeline' ? 'Viva Protocol View' : 'Timeline View'}
          </button>
          <button
            type="button"
            onClick={onClear}
            style={{ padding: '3px 8px', fontSize: '11px' }}
          >
            Clear
          </button>
        </div>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px', fontSize: '0.72rem', color: '#94a3b8' }}>
        <span>Showing {filteredEvents.length} events</span>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={filterHellos}
            onChange={e => setFilterHellos(e.target.checked)}
            style={{ width: 'auto', margin: 0 }}
          />
          Filter HELLO Beacons
        </label>
      </div>

      <div className="incident-timeline">
        {filteredEvents.length === 0 ? (
          <p style={{ color: '#64748b', fontStyle: 'italic', textAlign: 'center', padding: '16px 0', fontSize: '0.82rem' }}>
            No network events recorded yet.
          </p>
        ) : (
          filteredEvents.map((evt) => {
            const narrative = getEventNarrative(evt);
            return (
              <div key={evt.event_id} className={`timeline-card ${narrative.category}`}>
                <div className="timeline-header">
                  <span className="timeline-title">
                    <span className="log-type">{evt.type}</span>
                    <span style={{ fontSize: '0.78rem', color: '#cbd5e1' }}>— {narrative.title}</span>
                  </span>
                  <span className="timeline-time log-time">
                    {new Date(evt.timestamp).toLocaleTimeString()}
                  </span>
                </div>

                <div className="timeline-desc">
                  {narrative.desc}
                </div>

                {/* Technical data badges for CNT Viva inspection */}
                <div style={{ display: 'flex', gap: '10px', fontSize: '0.72rem', color: '#94a3b8', marginTop: '2px' }}>
                  {evt.data && evt.data.from_node && evt.data.to_node && (
                    <div style={{ color: '#38bdf8' }}>{evt.data.from_node} &rarr; {evt.data.to_node}</div>
                  )}
                  {evt.data && evt.data.node_id && (
                    <div>Node: {evt.data.node_id}</div>
                  )}
                  {evt.data && evt.data.packet_id && (
                    <div>Pkt: {evt.data.packet_id.substring(0, 8)}</div>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default EventLog;
