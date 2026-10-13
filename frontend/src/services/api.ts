import type { NetworkState, Metrics, RuntimeMode } from '../types';

const getApiBase = () => {
  if (typeof window !== 'undefined' && window.location && window.location.hostname) {
    return `http://${window.location.hostname}:8000/api`;
  }
  return 'http://localhost:8000/api';
};

const API_BASE = (import.meta as any).env?.VITE_API_URL || getApiBase();

export const fetchNetworkState = async (): Promise<NetworkState> => {
  const res = await fetch(`${API_BASE}/network`);
  return res.json();
};

export const resetSimulation = async () => {
  const res = await fetch(`${API_BASE}/simulation/reset`, { method: 'POST' });
  return res.json();
};

export const fetchMetrics = async (): Promise<Metrics> => {
  const res = await fetch(`${API_BASE}/metrics`);
  return res.json();
};

export const failNode = async (nodeId: string) => {
  const res = await fetch(`${API_BASE}/nodes/${nodeId}/fail`, { method: 'POST' });
  return res.json();
};

export const recoverNode = async (nodeId: string) => {
  const res = await fetch(`${API_BASE}/nodes/${nodeId}/recover`, { method: 'POST' });
  return res.json();
};

export const failLink = async (nodeA: string, nodeB: string) => {
  const res = await fetch(`${API_BASE}/links/fail`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_a: nodeA, node_b: nodeB }),
  });
  return res.json();
};

export const recoverLink = async (nodeA: string, nodeB: string) => {
  const res = await fetch(`${API_BASE}/links/recover`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ node_a: nodeA, node_b: nodeB }),
  });
  return res.json();
};

export const sendMessage = async (source: string, destination: string, message: string) => {
  const res = await fetch(`${API_BASE}/messages/send`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, destination, message }),
  });
  return res.json();
};

export const sendSOS = async (sosRequest: any) => {
  const res = await fetch(`${API_BASE}/sos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sosRequest),
  });
  return res.json();
};

export const getHospitalInbox = async () => {
  const res = await fetch(`${API_BASE}/hospital/inbox`);
  return res.json();
};

export const respondHospital = async (source: string, destination: string, message: string) => {
  const res = await fetch(`${API_BASE}/hospital/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, destination, message }),
  });
  return res.json();
};

export const fetchRuntimeMode = async (): Promise<{ mode: RuntimeMode }> => {
  const res = await fetch(`${API_BASE}/runtime/mode`);
  return res.json();
};

export const setRuntimeMode = async (mode: RuntimeMode): Promise<{ status: string; mode: RuntimeMode }> => {
  const res = await fetch(`${API_BASE}/runtime/mode`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode }),
  });
  return res.json();
};

export const fetchRuntimeStatus = async () => {
  const res = await fetch(`${API_BASE}/runtime/status`);
  return res.json();
};

export const startRealRuntime = async () => {
  const res = await fetch(`${API_BASE}/runtime/start`, { method: 'POST' });
  return res.json();
};

export const stopRealRuntime = async () => {
  const res = await fetch(`${API_BASE}/runtime/stop`, { method: 'POST' });
  return res.json();
};

export const stopRealNode = async (nodeId: string) => {
  const res = await fetch(`${API_BASE}/runtime/nodes/${nodeId}/stop`, { method: 'POST' });
  return res.json();
};

export const startRealNode = async (nodeId: string) => {
  const res = await fetch(`${API_BASE}/runtime/nodes/${nodeId}/start`, { method: 'POST' });
  return res.json();
};

export const fetchDemoStatus = async () => {
  const res = await fetch(`${API_BASE}/demo/status`);
  return res.json();
};

export const startDemo = async () => {
  const res = await fetch(`${API_BASE}/demo/start`, { method: 'POST' });
  return res.json();
};

export const nextDemoStage = async () => {
  const res = await fetch(`${API_BASE}/demo/next`, { method: 'POST' });
  return res.json();
};

export const prevDemoStage = async () => {
  const res = await fetch(`${API_BASE}/demo/prev`, { method: 'POST' });
  return res.json();
};

export const stepDemoStage = async (stage: number) => {
  const res = await fetch(`${API_BASE}/demo/step/${stage}`, { method: 'POST' });
  return res.json();
};

export const resetDemo = async () => {
  const res = await fetch(`${API_BASE}/demo/reset`, { method: 'POST' });
  return res.json();
};

