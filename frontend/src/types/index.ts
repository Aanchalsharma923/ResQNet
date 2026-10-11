export type ConnectionStatus = 'CONNECTING' | 'CONNECTED' | 'DISCONNECTED' | 'RECONNECTING';

export type RuntimeMode = 'simulation' | 'real';

export interface NodeState {
  node_id: string;
  ip_address: string;
  is_active: boolean;
  latitude: number;
  longitude: number;
  endpoint?: string;
  status?: string;
}

export interface SOSMessage {
  message_id: string;
  source_id: string;
  destination_id: string;
  message: string;
  latitude: number;
  longitude: number;
  priority: string;
  status: string;
  packet_id?: string;
  hop_count?: number;
  timestamp: string;
}

export interface LinkState {
  node_a_id: string;
  node_b_id: string;
  is_active: boolean;
}

export interface NetworkState {
  nodes: NodeState[];
  links: LinkState[];
  mode?: RuntimeMode;
  active_route?: string[];
  neighbor_health?: Record<string, Record<string, string>>;
}

export interface WSEvent {
  event_id: string;
  type: string;
  timestamp: string;
  data: any;
}

export interface Metrics {
  packets_sent: number;
  packets_delivered: number;
  packets_dropped: number;
  pdr: string;
  loss: string;
  avg_hop_count: string;
  rreq_count: number;
  rrep_count: number;
  rerr_count: number;
  route_discovery_time: string;
  recovery_time: string;
  latency: string;
  throughput: string;
}
