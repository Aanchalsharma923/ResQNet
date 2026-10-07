import { useEffect, useState, useMemo } from 'react';
import type { NetworkState, WSEvent } from '../types';

interface TopologyViewProps {
  networkState: NetworkState;
  events: WSEvent[];
}

interface NodePos {
  x: number;
  y: number;
}

const DEFAULT_POSITIONS: Record<string, NodePos> = {
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

  // Compute node positions dynamically
  const nodePositions = useMemo(() => {
    const positions: Record<string, NodePos> = { ...DEFAULT_POSITIONS };
    const dynamicNodes = networkState.nodes.filter(n => !positions[n.node_id]);
    
    // Arrange additional nodes in a deterministic grid/circle pattern
    if (dynamicNodes.length > 0) {
      const centerX = 450;
      const centerY = 250;
      const radius = 220; // Try to keep them inside the SVG
      const angleStep = (2 * Math.PI) / dynamicNodes.length;
      
      dynamicNodes.forEach((node, idx) => {
        // Offset angle to start at top, or somewhere else
        const angle = idx * angleStep + Math.PI / 4; 
        positions[node.node_id] = {
          x: centerX + radius * Math.cos(angle),
          y: centerY + radius * Math.sin(angle),
        };
      });
    }
    return positions;
  }, [networkState.nodes]);

  useEffect(() => {
    if (events.length === 0) return;
    const latest = events[0];
    
    let fromNode = '';
    let toNode = '';
    let packetType = '';

    if (latest.type.includes('FORWARDED') || latest.type.includes('RECEIVED') || latest.type === 'DATA_DELIVERED') {
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
        const animId = `${latest.event_id}-${Date.now()}-${Math.random()}`;
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
        // Only return null if the position hasn't been computed (shouldn't happen now)
        if (!posA || !posB) return null;
        
        // Use a consistent order for keys so that A-B and B-A are the same key if duplicated, though the backend shouldn't
        const key = [link.node_a_id, link.node_b_id].sort().join('-');
        
        return (
          <line
            key={key}
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
