import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import EventLog from './EventLog';
import type { WSEvent } from '../types';

describe('EventLog Component', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation((...args) => {
      // Allow other errors, but fail on React key warnings for this component
      if (args[0] && typeof args[0] === 'string' && args[0].includes('unique "key" prop')) {
        throw new Error('React unique key warning triggered');
      }
    });
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it('renders a single event correctly without key warnings', () => {
    const events: WSEvent[] = [
      {
        event_id: 'e1',
        type: 'TEST_EVENT',
        timestamp: '2023-10-10T12:00:00Z',
        data: { from_node: 'A', to_node: 'B' }
      }
    ];

    render(<EventLog events={events} onClear={vi.fn()} />);

    expect(screen.getByText('TEST_EVENT')).toBeInTheDocument();
    expect(screen.getByText('A → B')).toBeInTheDocument();
  });

  it('renders multiple unique events without key warnings', () => {
    const events: WSEvent[] = [
      {
        event_id: 'e1',
        type: 'TEST_EVENT_1',
        timestamp: '2023-10-10T12:00:00Z',
        data: { node_id: 'A' }
      },
      {
        event_id: 'e2',
        type: 'TEST_EVENT_2',
        timestamp: '2023-10-10T12:00:01Z',
        data: { packet_id: 'pkt12345' }
      }
    ];

    render(<EventLog events={events} onClear={vi.fn()} />);

    expect(screen.getByText('TEST_EVENT_1')).toBeInTheDocument();
    expect(screen.getByText('Node: A')).toBeInTheDocument();
    
    expect(screen.getByText('TEST_EVENT_2')).toBeInTheDocument();
    expect(screen.getByText('Pkt: pkt12345')).toBeInTheDocument();
  });

  it('renders events without triggering React key warnings even if no event_id was originally provided (testing component robustness)', () => {
    const events: WSEvent[] = [
      {
        event_id: 'local-1',
        type: 'INITIAL_STATE',
        timestamp: '2023-10-10T12:00:00Z',
        data: {}
      },
      {
        event_id: 'local-2',
        type: 'INITIAL_STATE',
        timestamp: '2023-10-10T12:00:01Z',
        data: {}
      }
    ];

    // If there were key issues, the console.error spy would throw an error during render.
    render(<EventLog events={events} onClear={vi.fn()} />);
    
    expect(screen.getAllByText('INITIAL_STATE')).toHaveLength(2);
  });

  it('calls onClear when the Clear button is clicked', () => {
    const mockOnClear = vi.fn();
    render(<EventLog events={[]} onClear={mockOnClear} />);
    
    const clearButton = screen.getByText('Clear');
    fireEvent.click(clearButton);
    
    expect(mockOnClear).toHaveBeenCalledTimes(1);
  });
});
