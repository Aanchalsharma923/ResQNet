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

export interface DemoStageInfo {
  stage: number;
  name: string;
  concept: string;
  scenario: string;
  observations: string[];
  examiner_notes: string;
}

export interface DemoSummary {
  sos_dispatched: number;
  sos_delivered: number;
  acks_confirmed: number;
  packets_dropped: number;
  pdr: string;
  recovery_time: string;
  active_route_at_conclusion: string[];
  hop_count: number;
  rreq_count: number;
  rrep_count: number;
  rerr_count: number;
  mode: string;
  mode_explanation: string;
  confirmed_messages: Array<{
    message_id: string;
    status: string;
    rtt_ms?: number;
  }>;
}

export interface DemoState {
  current_stage: number;
  total_stages: number;
  status: 'ready' | 'running' | 'completed' | 'error';
  mode: RuntimeMode;
  stage_info: DemoStageInfo;
  active_route: string[];
  active_nodes: string[];
  metrics: Metrics;
  hospital_inbox: SOSMessage[];
  last_action_result?: any;
  summary?: DemoSummary | null;
}
