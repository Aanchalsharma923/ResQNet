import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import TopologyView from './TopologyView';
import type { NetworkState } from '../types';

const mockNetworkState: NetworkState = {
  nodes: [
    { node_id: 'A', ip_address: '192.168.1.10', is_active: true, latitude: 18.5204, longitude: 73.8567 },
    { node_id: 'B', ip_address: '192.168.1.11', is_active: false, latitude: 18.5210, longitude: 73.8580 }
  ],
  links: [
    { node_a_id: 'A', node_b_id: 'B', is_active: true }
  ]
};

describe('TopologyView', () => {
  it('renders nodes correctly based on network state', () => {
    render(<TopologyView networkState={mockNetworkState} events={[]} />);
    
    // Check nodes are rendered
    expect(screen.getByText('A')).toBeInTheDocument();
    expect(screen.getByText('B')).toBeInTheDocument();
    
    // Node B is inactive, which means it should have a specific class (we could check class if needed)
    // Testing the SVG rendering directly is harder but we can check if texts exist
  });

  it('renders packets properly based on events', () => {
    const mockEvents = [
      {
        type: 'DATA_DELIVERED',
        data: {
          packet_id: 'p1',
          source_id: 'A',
          destination_id: 'B',
          current_node: 'B',
          sender_id: 'A'
        }
      }
    ];
    
    render(<TopologyView networkState={mockNetworkState} events={mockEvents as any} />);
    
    // A packet circle should be in the DOM
    const circles = document.querySelectorAll('circle');
    // We expect some circles for nodes, plus one for the packet
    // Just ensuring no crash and that elements are rendered.
    expect(circles.length).toBeGreaterThan(2); 
  });

  it('renders active route banner and DOWN status indicator', () => {
    const routeState: NetworkState = {
      ...mockNetworkState,
      active_route: ['A', 'B', 'C', 'H']
    };
    render(<TopologyView networkState={routeState} events={[]} />);
    expect(screen.getByText('A → B → C → H')).toBeInTheDocument();
    expect(screen.getByText('DOWN')).toBeInTheDocument();
  });
});

