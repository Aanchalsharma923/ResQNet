import type { NetworkState, Metrics, RuntimeMode } from '../types';

// Admin key is strictly stored in localStorage or runtime state — NEVER baked into static JS assets
let currentAdminKey: string =
  (typeof window !== 'undefined' ? localStorage.getItem('resqnet_admin_key') || '' : '');

export const setAdminKey = (key: string) => {
  currentAdminKey = key;
  if (typeof window !== 'undefined') {
    if (key) {
      localStorage.setItem('resqnet_admin_key', key);
    } else {
      localStorage.removeItem('resqnet_admin_key');
    }
  }
};

export const getAdminKey = () => currentAdminKey;

// Hospital Clinician Key for triage instruction submission
let currentHospitalKey: string =
  (typeof window !== 'undefined' ? localStorage.getItem('resqnet_hospital_key') || '' : '');

export const setHospitalKey = (key: string) => {
  currentHospitalKey = key;
  if (typeof window !== 'undefined') {
    if (key) {
      localStorage.setItem('resqnet_hospital_key', key);
    } else {
      localStorage.removeItem('resqnet_hospital_key');
    }
  }
};

export const getHospitalKey = () => currentHospitalKey;

const getAuthHeaders = (extraHeaders?: Record<string, string>): Record<string, string> => {
  const headers: Record<string, string> = { ...extraHeaders };
  if (currentAdminKey) {
    headers['X-Admin-Key'] = currentAdminKey;
  }
  return headers;
};

const getApiBase = () => {
  if ((import.meta as any).env?.VITE_API_URL) {
    return (import.meta as any).env.VITE_API_URL;
  }
  if (typeof window !== 'undefined' && window.location) {
    const { protocol, host, hostname, port } = window.location;
    // In dev environment where frontend runs on a vite port (5173-5175, 3000, 4173), direct to backend 8000
    if (port && ['5173', '5174', '5175', '3000', '4173'].includes(port)) {
      return `http://${hostname}:8000/api`;
    }
    // In production behind Nginx/reverse proxy on standard port 80/443 or domain, use same-origin /api
    return `${protocol}//${host}/api`;
  }
  return 'http://localhost:8000/api';
};

const API_BASE = getApiBase();

async function handleResponse(res: Response, _endpoint: string) {
  let data: any = null;
  try {
    data = await res.json();
  } catch {
    // response was not JSON
  }

  if (!res.ok) {
    const errorDetail =
      (data && (data.detail || data.error || data.message)) ||
      `HTTP ${res.status}: ${res.statusText || 'Request failed'}`;
    const err = new Error(typeof errorDetail === 'string' ? errorDetail : JSON.stringify(errorDetail));
    (err as any).status = res.status;
    (err as any).data = data;
    throw err;
  }

  return data;
}

function formatNetworkError(err: any, endpoint: string): Error {
  if (err?.name === 'TypeError' && err?.message?.toLowerCase().includes('fetch')) {
    return new Error(
      `Cannot connect to ResQNet backend at ${endpoint} (Failed to fetch — verify FastAPI backend is running on port 8000 and CORS allows origin)`
    );
  }
  return err instanceof Error ? err : new Error(String(err));
}

export const fetchNetworkState = async (): Promise<NetworkState> => {
  const url = `${API_BASE}/network`;
  try {
    const res = await fetch(url);
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const resetSimulation = async () => {
  const url = `${API_BASE}/simulation/reset`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const fetchMetrics = async (): Promise<Metrics> => {
  const url = `${API_BASE}/metrics`;
  try {
    const res = await fetch(url);
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const failNode = async (nodeId: string) => {
  const url = `${API_BASE}/nodes/${nodeId}/fail`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const recoverNode = async (nodeId: string) => {
  const url = `${API_BASE}/nodes/${nodeId}/recover`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const failLink = async (nodeA: string, nodeB: string) => {
  const url = `${API_BASE}/links/fail`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ node_a: nodeA, node_b: nodeB }),
    });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const recoverLink = async (nodeA: string, nodeB: string) => {
  const url = `${API_BASE}/links/recover`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ node_a: nodeA, node_b: nodeB }),
    });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const sendMessage = async (source: string, destination: string, message: string) => {
  const url = `${API_BASE}/messages/send`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source, destination, message }),
    });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const sendSOS = async (sosRequest: any) => {
  const url = `${API_BASE}/sos`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(sosRequest),
    });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const getHospitalInbox = async () => {
  const url = `${API_BASE}/hospital/inbox`;
  try {
    const res = await fetch(url);
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const respondHospital = async (
  source: string,
  destination: string,
  message: string,
  sos_message_id?: string
) => {
  const url = `${API_BASE}/hospital/respond`;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (currentHospitalKey) {
    headers['X-Hospital-Key'] = currentHospitalKey;
  }
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        source_id: source,
        destination_id: destination,
        source,
        destination,
        message,
        sos_message_id,
      }),
    });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const fetchRuntimeMode = async (): Promise<{ mode: RuntimeMode }> => {
  const url = `${API_BASE}/runtime/mode`;
  try {
    const res = await fetch(url);
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const setRuntimeMode = async (mode: RuntimeMode): Promise<{ status: string; mode: RuntimeMode }> => {
  const url = `${API_BASE}/runtime/mode`;
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: getAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ mode }),
    });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const fetchRuntimeStatus = async () => {
  const url = `${API_BASE}/runtime/status`;
  try {
    const res = await fetch(url);
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const startRealRuntime = async () => {
  const url = `${API_BASE}/runtime/start`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const stopRealRuntime = async () => {
  const url = `${API_BASE}/runtime/stop`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const stopRealNode = async (nodeId: string) => {
  const url = `${API_BASE}/runtime/nodes/${nodeId}/stop`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const startRealNode = async (nodeId: string) => {
  const url = `${API_BASE}/runtime/nodes/${nodeId}/start`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const fetchDemoStatus = async () => {
  const url = `${API_BASE}/demo/status`;
  try {
    const res = await fetch(url);
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const startDemo = async () => {
  const url = `${API_BASE}/demo/start`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const nextDemoStage = async () => {
  const url = `${API_BASE}/demo/next`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const prevDemoStage = async () => {
  const url = `${API_BASE}/demo/prev`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const stepDemoStage = async (stage: number) => {
  const url = `${API_BASE}/demo/step/${stage}`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};

export const resetDemo = async () => {
  const url = `${API_BASE}/demo/reset`;
  try {
    const res = await fetch(url, { method: 'POST', headers: getAuthHeaders() });
    return await handleResponse(res, url);
  } catch (err) {
    throw formatNetworkError(err, url);
  }
};
