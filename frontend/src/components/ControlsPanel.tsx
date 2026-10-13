import {
  failNode, recoverNode, failLink, recoverLink, resetSimulation, sendMessage,
  setRuntimeMode, startRealRuntime, stopRealRuntime
} from '../services/api';
import type { NetworkState, RuntimeMode } from '../types';

interface ControlsPanelProps {
  networkState: NetworkState | null;
  onModeChange?: (mode: RuntimeMode) => void;
}

const ControlsPanel = ({ networkState, onModeChange }: ControlsPanelProps) => {
  const isRealMode = networkState?.mode === 'real';

  const handleSwitchMode = async (mode: RuntimeMode) => {
    try {
      await setRuntimeMode(mode);
      if (onModeChange) {
        onModeChange(mode);
      }
    } catch (e) {
      console.error('Failed to change mode', e);
    }
  };

  const handleFailNode = async (nodeId: string) => await failNode(nodeId);
  const handleRecoverNode = async (nodeId: string) => await recoverNode(nodeId);
  const handleFailLink = async (a: string, b: string) => await failLink(a, b);
  const handleRecoverLink = async (a: string, b: string) => await recoverLink(a, b);

  const getNodeRole = (id: string) => {
    if (id === 'A') return 'Rescue-A';
    if (id === 'H') return 'Hospital-H';
    if (id === 'D') return 'Relay-D (Alternate)';
    return `Relay-${id}`;
  };

  return (
    <div className="panel">
      <h2>
        <span>Network Controls & Injection</span>
        <span style={{ fontSize: '0.72rem', color: '#64748b', fontWeight: 500 }}>Manual Scenario</span>
      </h2>

      {/* Mode Switcher */}
      <div style={{ marginBottom: '14px' }}>
        <div style={{ fontSize: '0.72rem', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 600, marginBottom: '6px' }}>
          Runtime Operating Mode
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <button
            type="button"
            className={!isRealMode ? 'primary' : ''}
            style={{ fontWeight: !isRealMode ? 700 : 500, fontSize: '0.8rem' }}
            onClick={() => handleSwitchMode('simulation')}
          >
            Simulation Mode
          </button>
          <button
            type="button"
            className={isRealMode ? 'primary' : ''}
            style={{
              fontWeight: isRealMode ? 700 : 500,
              fontSize: '0.8rem',
              background: isRealMode ? 'var(--color-real-mode)' : undefined,
              borderColor: isRealMode ? '#7c3aed' : undefined
            }}
            onClick={() => handleSwitchMode('real')}
          >
            Real UDP / LAN Mode
          </button>
        </div>
      </div>

      {isRealMode ? (
        <>
          <div className="controls-grid">
            <button type="button" className="success" onClick={() => startRealRuntime()} style={{ fontSize: '0.78rem' }}>
              Start All Nodes
            </button>
            <button type="button" className="danger" onClick={() => stopRealRuntime()} style={{ fontSize: '0.78rem' }}>
              Stop All Nodes
            </button>
            <button type="button" onClick={() => resetSimulation()} style={{ fontSize: '0.78rem' }}>
              Reset Runtime
            </button>
            <button type="button" className="primary" onClick={() => sendMessage('A', 'H', 'Real UDP Ping')} style={{ fontSize: '0.78rem' }}>
              Send UDP Ping
            </button>
          </div>
          <p style={{ fontSize: '0.72rem', color: '#94a3b8', marginBottom: '12px', lineHeight: '1.4' }}>
            Multi-Process Mode: Each node runs in an independent OS process. Stopping a relay severs UDP HELLO beacons, triggering AODV route rediscovery.
          </p>

          {networkState && (
            <div>
              <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px' }}>
                Node Process Controls
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {networkState.nodes.map((node) => (
                  <div key={node.node_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-surface)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                    <div>
                      <span style={{ fontWeight: 600, fontSize: '0.82rem' }}>{getNodeRole(node.node_id)}</span>
                      <span style={{ fontSize: '0.72rem', color: node.is_active ? '#34d399' : '#f87171', marginLeft: '6px', fontWeight: 700 }}>
                        {node.is_active ? 'UP (Online)' : 'DOWN (Stopped)'}
                      </span>
                      {node.endpoint && (
                        <div style={{ fontSize: '0.68rem', color: '#64748b', fontFamily: 'monospace' }}>{node.endpoint}</div>
                      )}
                    </div>
                    {node.is_active ? (
                      <button type="button" className="danger" onClick={() => handleFailNode(node.node_id)} style={{ padding: '3px 8px', fontSize: '11px' }}>
                        Stop (Fail)
                      </button>
                    ) : (
                      <button type="button" className="success" onClick={() => handleRecoverNode(node.node_id)} style={{ padding: '3px 8px', fontSize: '11px' }}>
                        Start (Recover)
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      ) : (
        <>
          <div className="controls-grid">
            <button type="button" className="primary" onClick={() => resetSimulation()} style={{ fontSize: '0.78rem' }}>
              Reset Simulation
            </button>
            <button type="button" className="primary" onClick={() => sendMessage('A', 'H', 'Simulation Start')} style={{ fontSize: '0.78rem' }}>
              Simulate Path Ping
            </button>
          </div>

          {networkState && (
            <>
              <div style={{ marginTop: '10px' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Node Failure Injection
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  {networkState.nodes.map((node) => (
                    <div key={node.node_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-surface)', padding: '5px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                      <span style={{ fontSize: '0.8rem' }}>
                        <strong>{getNodeRole(node.node_id)}</strong>{' '}
                        <span style={{ fontSize: '0.72rem', color: node.is_active ? '#34d399' : '#f87171' }}>
                          {node.is_active ? '(Active)' : '(Failed)'}
                        </span>
                      </span>
                      {node.is_active ? (
                        <button type="button" className="danger" onClick={() => handleFailNode(node.node_id)} style={{ padding: '2px 8px', fontSize: '11px' }}>
                          Fail Node
                        </button>
                      ) : (
                        <button type="button" className="success" onClick={() => handleRecoverNode(node.node_id)} style={{ padding: '2px 8px', fontSize: '11px' }}>
                          Recover
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ marginTop: '12px' }}>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '6px' }}>
                  Link Failure Injection
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  {networkState.links.map((link) => {
                    const key = [link.node_a_id, link.node_b_id].sort().join('-');
                    return (
                      <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-surface)', padding: '5px 8px', borderRadius: '4px', border: '1px solid var(--border-subtle)' }}>
                        <span style={{ fontSize: '0.8rem' }}>
                          {link.node_a_id} ↔ {link.node_b_id}{' '}
                          <span style={{ fontSize: '0.72rem', color: link.is_active ? '#34d399' : '#f87171' }}>
                            {link.is_active ? '(Active)' : '(Failed)'}
                          </span>
                        </span>
                        {link.is_active ? (
                          <button type="button" className="danger" onClick={() => handleFailLink(link.node_a_id, link.node_b_id)} style={{ padding: '2px 8px', fontSize: '11px' }}>
                            Sever Link
                          </button>
                        ) : (
                          <button type="button" className="success" onClick={() => handleRecoverLink(link.node_a_id, link.node_b_id)} style={{ padding: '2px 8px', fontSize: '11px' }}>
                            Restore
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
};

export default ControlsPanel;

