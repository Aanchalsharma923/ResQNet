import { failNode, recoverNode, failLink, recoverLink, resetSimulation, sendMessage } from '../services/api';


const ControlsPanel = () => {
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

      <div style={{ marginTop: '15px' }}>
        <h3 style={{ fontSize: '0.9rem', marginBottom: '10px' }}>Nodes</h3>
        <div className="controls-grid">
          <button className="danger" onClick={() => handleFailNode('B')}>Fail B</button>
          <button className="success" onClick={() => handleRecoverNode('B')}>Recover B</button>
          <button className="danger" onClick={() => handleFailNode('D')}>Fail D</button>
          <button className="success" onClick={() => handleRecoverNode('D')}>Recover D</button>
        </div>
      </div>

      <div style={{ marginTop: '15px' }}>
        <h3 style={{ fontSize: '0.9rem', marginBottom: '10px' }}>Links</h3>
        <div className="controls-grid">
          <button className="danger" onClick={() => handleFailLink('A', 'B')}>Fail A-B</button>
          <button className="success" onClick={() => handleRecoverLink('A', 'B')}>Recover A-B</button>
          <button className="danger" onClick={() => handleFailLink('C', 'H')}>Fail C-H</button>
          <button className="success" onClick={() => handleRecoverLink('C', 'H')}>Recover C-H</button>
        </div>
      </div>
    </div>
  );
};

export default ControlsPanel;
