export type ConnectionStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'RECONNECTING';

export interface NodeState {
  node_id: string;
  ip_address: string;
  is_active: boolean;
}

export interface LinkState {
  node_a_id: string;
  node_b_id: string;
  is_active: boolean;
}

export interface NetworkState {
  nodes: NodeState[];
  links: LinkState[];
}

export interface WSEvent {
  event_id: string;
  type: string;
  timestamp: string;
  data: any;
}

export interface Metrics {
  total_events: number;
  total_packets_pending: number;
}
