# Frontend Architecture

## Overview
The ResQNet frontend is a React-based application that acts as a visualization and control client for the ResQNet network simulation. The backend (FastAPI + Simulation Engine) is the single source of truth; the frontend makes no routing decisions and simply reflects the backend state.

## Stack
- React 18
- Vite
- TypeScript
- Tailwind CSS
- Lucide React (Icons)
- Vitest + Testing Library (Testing)

## Core Components
- `App.tsx`: Main application container, manages the WebSocket connection and state integration.
- `useSimulation.ts`: Custom React hook that handles WebSocket connection, state management, and parsing incoming backend events.
- `TopologyView.tsx`: SVG-based canvas visualizing nodes, links, and animated packet paths based on `route_history`.
- `ControlPanel.tsx`: UI for failing/recovering nodes and sending SOS messages.
- `MetricsPanel.tsx`: Displays network metrics (packets sent/delivered/dropped, control overhead, hop counts) sourced directly from the backend API. All calculation is handled backend-side to maintain a single source of truth. Unimplemented temporal metrics (latency, throughput) map to N/A.
- `EventLog.tsx`: Real-time scrolling list of chronological network events.

## Integration Freeze
As of Phase 3.5, the React frontend and the AODV WebSocket backend integration is **FROZEN**. The frontend correctly visualizes dynamic topology, end-to-end disaster scenarios, and real-time metrics without fabricating any network logic locally.

## State Management
State is managed primarily via `useSimulation.ts`, which maintains:
- `networkState`: The latest topology (nodes and links) and their statuses.
- `events`: A history of network events (RREQ, RREP, DATA forwarded/delivered).
- `metrics`: Polled regularly from the backend to ensure accuracy with the backend single source of truth.

## Testing
Component tests and integration tests reside alongside the components. `vitest` is used as the test runner.
