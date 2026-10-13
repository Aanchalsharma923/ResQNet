import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import GuidedDemoPanel from './GuidedDemoPanel';
import type { WSEvent } from '../types';

vi.mock('../services/api', () => ({
  fetchDemoStatus: vi.fn().mockResolvedValue({
    current_stage: 1,
    total_stages: 6,
    status: 'ready',
    mode: 'simulation',
    stage_info: {
      stage: 1,
      name: 'Initial Network & Topology Discovery',
      concept: 'Multi-Hop Mesh Topology (RFC 3561)',
      scenario: 'A 5-node wireless tactical mesh is deployed.',
      observations: [
        'All 5 nodes are online and operational.',
        'AODV discovers primary multi-hop path A -> B -> C -> H.'
      ],
      examiner_notes: 'AODV routes are established on demand.'
    },
    active_route: ['A', 'B', 'C', 'H'],
    active_nodes: ['A', 'B', 'C', 'D', 'H'],
    metrics: { pdr: '100%' },
    hospital_inbox: []
  }),
  startDemo: vi.fn().mockResolvedValue({ current_stage: 1 }),
  nextDemoStage: vi.fn().mockResolvedValue({ current_stage: 2 }),
  prevDemoStage: vi.fn().mockResolvedValue({ current_stage: 1 }),
  stepDemoStage: vi.fn().mockResolvedValue({ current_stage: 3 }),
  resetDemo: vi.fn().mockResolvedValue({ current_stage: 1 })
}));

describe('GuidedDemoPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders demo header and all 6 stage tabs', async () => {
    render(<GuidedDemoPanel events={[]} />);

    expect(screen.getByText('LIVE VIVA DEMO')).toBeInTheDocument();
    expect(screen.getByText(/Disaster Scenario Walkthrough/i)).toBeInTheDocument();

    // Check for all 6 stepper tabs
    expect(screen.getByText('1. Initial Mesh')).toBeInTheDocument();
    expect(screen.getByText('2. Dispatch SOS')).toBeInTheDocument();
    expect(screen.getByText('3. Hospital ACK')).toBeInTheDocument();
    expect(screen.getByText('4. Relay Failure')).toBeInTheDocument();
    expect(screen.getByText('5. Route Recovery')).toBeInTheDocument();
    expect(screen.getByText('6. Viva Defense')).toBeInTheDocument();
  });

  it('updates display when DEMO_STAGE_CHANGED event arrives', async () => {
    const stageEvent: WSEvent = {
      event_id: 'e-stage',
      type: 'DEMO_STAGE_CHANGED',
      timestamp: '2026-10-12T00:00:00Z',
      data: {
        current_stage: 2,
        total_stages: 6,
        status: 'running',
        mode: 'simulation',
        stage_info: {
          stage: 2,
          name: 'Emergency SOS Distress Dispatch',
          concept: 'DATA Packet Encapsulation',
          scenario: 'Rescue Team Alpha dispatches high-priority SOS.',
          observations: ['Distinct message ID generated.'],
          examiner_notes: 'Encapsulates emergency triage payload.'
        },
        active_route: ['A', 'B', 'C', 'H'],
        active_nodes: ['A', 'B', 'C', 'D', 'H'],
        metrics: { pdr: '100%' },
        hospital_inbox: []
      }
    };

    render(<GuidedDemoPanel events={[stageEvent]} />);

    expect(screen.getByText('Stage 2 of 6')).toBeInTheDocument();
    expect(screen.getByText('Emergency SOS Distress Dispatch')).toBeInTheDocument();
    expect(screen.getByText('DATA Packet Encapsulation')).toBeInTheDocument();
    expect(screen.getByText(/Rescue Team Alpha dispatches high-priority SOS/i)).toBeInTheDocument();
  });

  it('toggles guidance section on button click', async () => {
    const stageEvent: WSEvent = {
      event_id: 'e-stage',
      type: 'DEMO_STAGE_CHANGED',
      timestamp: '2026-10-12T00:00:00Z',
      data: {
        current_stage: 1,
        total_stages: 6,
        stage_info: {
          stage: 1,
          name: 'Initial Network',
          concept: 'Mesh Discovery',
          scenario: 'Mesh deployed.',
          observations: ['Nodes online.'],
          examiner_notes: 'Examiner note.'
        }
      }
    };

    render(<GuidedDemoPanel events={[stageEvent]} />);

    const toggleBtn = screen.getByText('▲ Hide Guidance');
    expect(toggleBtn).toBeInTheDocument();
    expect(screen.getByText(/Key Observations for Viva Examiner:/i)).toBeInTheDocument();

    // Click toggle to hide
    fireEvent.click(toggleBtn);
    expect(screen.getByText('▼ Show Guidance')).toBeInTheDocument();
    expect(screen.queryByText(/Key Observations for Viva Examiner:/i)).not.toBeInTheDocument();
  });

  it('renders Viva defense summary section when on stage 6', async () => {
    const stage6Event: WSEvent = {
      event_id: 'e-stage6',
      type: 'DEMO_STAGE_CHANGED',
      timestamp: '2026-10-12T00:00:00Z',
      data: {
        current_stage: 6,
        total_stages: 6,
        status: 'completed',
        stage_info: {
          stage: 6,
          name: 'Demonstration Results',
          concept: 'Viva Defense',
          scenario: 'Evaluation complete.',
          observations: ['100% PDR achieved.'],
          examiner_notes: 'Resilience verified.'
        },
        summary: {
          sos_dispatched: 2,
          sos_delivered: 2,
          acks_confirmed: 2,
          packets_dropped: 0,
          pdr: '100.0%',
          recovery_time: '150.0ms',
          active_route_at_conclusion: ['A', 'D', 'C', 'H'],
          hop_count: 3,
          rreq_count: 2,
          rrep_count: 2,
          rerr_count: 1,
          mode: 'simulation',
          mode_explanation: 'Simulation Mode: Discrete event logical clock.',
          confirmed_messages: []
        }
      }
    };

    render(<GuidedDemoPanel events={[stage6Event]} />);

    expect(screen.getByText('🎓 Final Demonstration Evaluation & Protocol Metrics')).toBeInTheDocument();
    expect(screen.getByText('100.0%')).toBeInTheDocument();
    expect(screen.getByText('150.0ms')).toBeInTheDocument();
    expect(screen.getByText('A → D → C → H')).toBeInTheDocument();
    expect(screen.getByText(/Simulation Mode: Discrete event logical clock/i)).toBeInTheDocument();
  });
});
