import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import App from './App';

// Mock the child components to simplify testing the root component
vi.mock('./components/ControlsPanel', () => ({
  default: () => <div data-testid="mock-control-panel" />
}));
vi.mock('./components/EventLog', () => ({
  default: () => <div data-testid="mock-event-log" />
}));
vi.mock('./components/TopologyView', () => ({
  default: () => <div data-testid="mock-topology-view" />
}));
vi.mock('./components/MetricsPanel', () => ({
  default: () => <div data-testid="mock-metrics-panel" />
}));
vi.mock('./components/SOSPanel', () => ({
  default: () => <div data-testid="mock-sos-panel" />
}));
vi.mock('./components/HospitalPanel', () => ({
  default: () => <div data-testid="mock-hospital-panel" />
}));

describe('App', () => {
  it('renders the header and all main panels', () => {
    render(<App />);
    
    // Check header
    expect(screen.getByText('RESQNET: Disaster-Resilient AODV Communication Network')).toBeInTheDocument();
    
    // Check main panels
    expect(screen.getByText('Loading topology...')).toBeInTheDocument(); // TopologyView is not rendered until state loads
    expect(screen.getByTestId('mock-control-panel')).toBeInTheDocument();
    expect(screen.getByTestId('mock-metrics-panel')).toBeInTheDocument();
    expect(screen.getByTestId('mock-event-log')).toBeInTheDocument();
    // SOSPanel and HospitalPanel might also conditionally render or be inside panel-row
    expect(screen.getByTestId('mock-hospital-panel')).toBeInTheDocument();
  });
});
