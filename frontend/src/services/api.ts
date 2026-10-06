import type { NetworkState, Metrics } from '../types';

const API_BASE = 'http://localhost:8000/api';

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
