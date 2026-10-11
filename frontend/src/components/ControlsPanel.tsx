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
  
  return (
    <div className="panel">
      <h2>Controls</h2>

      {/* Mode Switcher */}
      <div style={{ marginBottom: '15px' }}>
        <h3 style={{ fontSize: '0.85rem', marginBottom: '6px', color: '#888', textTransform: 'uppercase' }}>Network Mode</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
          <button 
            className={!isRealMode ? 'primary' : ''} 
            style={{ fontWeight: !isRealMode ? 'bold' : 'normal' }}
            onClick={() => handleSwitchMode('simulation')}
          >
            Simulation Mode
          </button>
          <button 
            className={isRealMode ? 'primary' : ''} 
            style={{ fontWeight: isRealMode ? 'bold' : 'normal' }}
            onClick={() => handleSwitchMode('real')}
          >
            Real UDP / LAN Mode
          </button>
        </div>
      </div>

      {isRealMode ? (
        <>
          <div className="controls-grid">
            <button className="primary" onClick={() => startRealRuntime()}>Start All Nodes</button>
            <button className="danger" onClick={() => stopRealRuntime()}>Stop All Nodes</button>
            <button onClick={() => resetSimulation()}>Reset Network</button>
            <button className="primary" onClick={() => sendMessage('A', 'H', 'Real UDP Ping')}>Send UDP Ping</button>
          </div>
          <p style={{ fontSize: '0.75rem', color: '#9e9e9e', marginBottom: '15px', lineHeight: '1.4' }}>
            In Real UDP Mode, each node runs as an independent process. Stopping a node terminates its real process; neighbors detect failure via missed UDP HELLOs and AODV reroutes.
          </p>

          {networkState && (
            <div>
              <h3 style={{ fontSize: '0.9rem', marginBottom: '10px' }}>Node Processes</h3>
              <div className="controls-list" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {networkState.nodes.map((node) => (
                  <div key={node.node_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#252525', padding: '6px 10px', borderRadius: '4px' }}>
                    <div>
                      <span style={{ fontWeight: 'bold' }}>Node {node.node_id}</span>
                      <span style={{ fontSize: '0.8rem', color: node.is_active ? '#4caf50' : '#f44336', marginLeft: '8px' }}>
                        {node.is_active ? 'UP (Running)' : 'DOWN (Stopped)'}
                      </span>
                      {node.endpoint && (
                        <div style={{ fontSize: '0.75rem', color: '#888' }}>{node.endpoint}</div>
                      )}
                    </div>
                    {node.is_active ? (
                      <button className="danger" onClick={() => handleFailNode(node.node_id)} style={{ padding: '4px 10px', fontSize: '12px' }}>Stop Process</button>
                    ) : (
                      <button className="success" onClick={() => handleRecoverNode(node.node_id)} style={{ padding: '4px 10px', fontSize: '12px' }}>Start Process</button>
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
            <button className="primary" onClick={() => resetSimulation()}>Reset Simulation</button>
            <button className="primary" onClick={() => sendMessage('A', 'H', 'Simulation Start')}>Start Simulation</button>
          </div>

          {networkState && (
            <>
              <div style={{ marginTop: '15px' }}>
                <h3 style={{ fontSize: '0.9rem', marginBottom: '10px' }}>Nodes</h3>
                <div className="controls-list" style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  {networkState.nodes.map((node) => (
                    <div key={node.node_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span>{node.node_id} {node.is_active ? '(Active)' : '(Failed)'}</span>
                      {node.is_active ? (
                        <button className="danger" onClick={() => handleFailNode(node.node_id)} style={{ padding: '2px 8px', fontSize: '12px' }}>Fail</button>
                      ) : (
                        <button className="success" onClick={() => handleRecoverNode(node.node_id)} style={{ padding: '2px 8px', fontSize: '12px' }}>Recover</button>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              <div style={{ marginTop: '15px' }}>
                <h3 style={{ fontSize: '0.9rem', marginBottom: '10px' }}>Links</h3>
                <div className="controls-list" style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                  {networkState.links.map((link) => {
                    const key = [link.node_a_id, link.node_b_id].sort().join('-');
                    return (
                      <div key={key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span>{link.node_a_id} ↔ {link.node_b_id} {link.is_active ? '(Active)' : '(Failed)'}</span>
                        {link.is_active ? (
                          <button className="danger" onClick={() => handleFailLink(link.node_a_id, link.node_b_id)} style={{ padding: '2px 8px', fontSize: '12px' }}>Fail</button>
                        ) : (
                          <button className="success" onClick={() => handleRecoverLink(link.node_a_id, link.node_b_id)} style={{ padding: '2px 8px', fontSize: '12px' }}>Recover</button>
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

