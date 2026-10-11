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

  const isActiveRouteLink = (nodeA: string, nodeB: string): boolean => {
    if (!networkState.active_route || networkState.active_route.length < 2) return false;
    const route = networkState.active_route;
    for (let i = 0; i < route.length - 1; i++) {
      if ((route[i] === nodeA && route[i + 1] === nodeB) || (route[i] === nodeB && route[i + 1] === nodeA)) {
        return true;
      }
    }
    return false;
  };

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Route Status Banner */}
      <div style={{
        position: 'absolute',
        top: 10,
        left: 10,
        background: 'rgba(20, 20, 20, 0.85)',
        border: '1px solid #444',
        borderRadius: 4,
        padding: '6px 12px',
        fontSize: '0.8rem',
        zIndex: 10,
        display: 'flex',
        alignItems: 'center',
        gap: '8px'
      }}>
        <span style={{ color: '#aaa', textTransform: 'uppercase', fontWeight: 'bold' }}>Active AODV Route:</span>
        {networkState.active_route && networkState.active_route.length > 0 ? (
          <span style={{ color: '#00e676', fontWeight: 'bold' }}>
            {networkState.active_route.join(' → ')}
          </span>
        ) : (
          <span style={{ color: '#ffb300', fontStyle: 'italic' }}>
            No active route (AODV discovery / recovering)
          </span>
        )}
      </div>

      <svg className="topology-svg" viewBox="0 0 900 500">
        {/* Draw Links */}
        {networkState.links.map(link => {
          const posA = nodePositions[link.node_a_id];
          const posB = nodePositions[link.node_b_id];
          if (!posA || !posB) return null;
          
          const key = [link.node_a_id, link.node_b_id].sort().join('-');
          const isActiveRoute = isActiveRouteLink(link.node_a_id, link.node_b_id);
          
          return (
            <line
              key={key}
              x1={posA.x} y1={posA.y}
              x2={posB.x} y2={posB.y}
              className={`link ${!link.is_active ? 'failed' : ''} ${isActiveRoute ? 'active-route' : ''}`}
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
          const displayAddr = node.endpoint || node.ip_address;
          return (
            <g key={node.node_id} transform={`translate(${pos.x}, ${pos.y})`}>
              <circle
                r={25}
                className={`node ${!node.is_active ? 'failed' : ''} ${isHospital ? 'hospital' : ''}`}
              />
              <text y={5} className="node-label">{node.node_id}</text>
              <text y={40} className="node-ip">{displayAddr}</text>
              {!node.is_active && (
                <text y={54} fill="#ff5252" fontSize="10" textAnchor="middle" fontWeight="bold">DOWN</text>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
};

export default TopologyView;
