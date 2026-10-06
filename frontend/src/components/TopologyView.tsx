import { useEffect, useState } from 'react';
import type { NetworkState, WSEvent } from '../types';

interface TopologyViewProps {
  networkState: NetworkState;
  events: WSEvent[];
}

interface NodePos {
  x: number;
  y: number;
}

const nodePositions: Record<string, NodePos> = {
  A: { x: 200, y: 250 },
  B: { x: 350, y: 100 },
  C: { x: 500, y: 250 },
  D: { x: 350, y: 400 },
  H: { x: 700, y: 250 },
};

interface PacketAnimation {
  id: string;
  from: string;
  to: string;
  type: string;
  progress: number;
}

const TopologyView = ({ networkState, events }: TopologyViewProps) => {
  const [animations, setAnimations] = useState<PacketAnimation[]>([]);

  useEffect(() => {
    if (events.length === 0) return;
    const latest = events[0];
    
    let fromNode = '';
    let toNode = '';
    let packetType = '';

    if (latest.type.includes('FORWARDED') || latest.type.includes('RECEIVED') || latest.type === 'DATA_DELIVERED') {
      // Find from and to
      if (latest.data.from_node && latest.data.to_node) {
        fromNode = latest.data.from_node;
        toNode = latest.data.to_node;
      } else if (latest.data.sender_id && latest.data.current_node) {
        fromNode = latest.data.sender_id;
        toNode = latest.data.current_node;
      } else if (latest.data.sender_id && latest.data.destination_id && latest.type.includes('RECEIVED')) {
        fromNode = latest.data.sender_id;
        toNode = latest.data.destination_id;
      }

      if (latest.type.startsWith('RREQ')) packetType = 'rreq';
      else if (latest.type.startsWith('RREP')) packetType = 'rrep';
      else if (latest.type.startsWith('RERR')) packetType = 'rerr';
      else if (latest.type.startsWith('DATA')) packetType = 'data';

      if (fromNode && toNode && packetType) {
        const animId = `${latest.event_id}-${Date.now()}`;
        setAnimations(prev => [...prev, { id: animId, from: fromNode, to: toNode, type: packetType, progress: 0 }]);
      }
    }
  }, [events]);

  useEffect(() => {
    if (animations.length === 0) return;

    const interval = setInterval(() => {
      setAnimations(prev => {
        return prev.map(a => ({ ...a, progress: a.progress + 0.05 }))
          .filter(a => a.progress < 1.0);
      });
    }, 50);

    return () => clearInterval(interval);
  }, [animations.length]);

  return (
    <svg className="topology-svg" viewBox="0 0 900 500">
      {/* Draw Links */}
      {networkState.links.map(link => {
        const posA = nodePositions[link.node_a_id];
        const posB = nodePositions[link.node_b_id];
        if (!posA || !posB) return null;
        return (
          <line
            key={`${link.node_a_id}-${link.node_b_id}`}
            x1={posA.x} y1={posA.y}
            x2={posB.x} y2={posB.y}
            className={`link ${!link.is_active ? 'failed' : ''}`}
          />
        );
      })}

      {/* Draw Packets */}
      {animations.map(anim => {
        const posA = nodePositions[anim.from];
        const posB = nodePositions[anim.to];
        if (!posA || !posB) return null;

        const x = posA.x + (posB.x - posA.x) * anim.progress;
        const y = posA.y + (posB.y - posA.y) * anim.progress;

        return (
          <circle
            key={anim.id}
            cx={x} cy={y}
            className={`packet ${anim.type}`}
          />
        );
      })}

      {/* Draw Nodes */}
      {networkState.nodes.map(node => {
        const pos = nodePositions[node.node_id];
        if (!pos) return null;
        const isHospital = node.node_id === 'H';
        return (
          <g key={node.node_id} transform={`translate(${pos.x}, ${pos.y})`}>
            <circle
              r={25}
              className={`node ${!node.is_active ? 'failed' : ''} ${isHospital ? 'hospital' : ''}`}
            />
            <text y={5} className="node-label">{node.node_id}</text>
            <text y={40} className="node-ip">{node.ip_address}</text>
          </g>
        );
      })}
    </svg>
  );
};

export default TopologyView;
