import { failNode, recoverNode, failLink, recoverLink, resetSimulation, sendMessage } from '../services/api';
import type { NetworkState } from '../types';

interface ControlsPanelProps {
  networkState: NetworkState | null;
}

const ControlsPanel = ({ networkState }: ControlsPanelProps) => {
  const handleFailNode = async (nodeId: string) => await failNode(nodeId);
  const handleRecoverNode = async (nodeId: string) => await recoverNode(nodeId);
  const handleFailLink = async (a: string, b: string) => await failLink(a, b);
  const handleRecoverLink = async (a: string, b: string) => await recoverLink(a, b);
  
  return (
    <div className="panel">
      <h2>Controls</h2>
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
                // Ensure unique key for links
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
    </div>
  );
};

export default ControlsPanel;
