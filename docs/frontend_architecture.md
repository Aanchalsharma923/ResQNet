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
- `App.tsx`: Main emergency-response command center container. Houses the top incident overview bar (mesh health, active AODV route, hospital ingest status, latest alert) and mode indicator (`Simulation Mode` vs `Real UDP/LAN Mode`).
- `TopologyView.tsx`: SVG-based tactical network map serving as the visual centerpiece. Visualizes rescue nodes (`Rescue-A`, `Relay-B`, `Relay-C`, `Relay-D (Alt)`, `Hospital-H`), dynamic links, confirmed AODV route highlights, and in-flight packet flows based on real backend events.
- `MetricsPanel.tsx`: Features 4 headline metrics: Packet Delivery Ratio (PDR), Delivered SOS count, Route Recovery Time, and Active Route Hop Count. Includes a collapsible CNT viva protocol telemetry section displaying control overhead (RREQ, RREP, RERR), average hops, packet loss, and derived throughput context.
- `EventLog.tsx`: Dual-mode event log with a human-readable **Incident Timeline** summarizing routing events into plain English cards with timestamps, filtering high-frequency neighbor heartbeats by default. Features an expandable **Raw Protocol Event Log** for CNT viva inspection.
- `SOSPanel.tsx`: Tactical SOS emergency dispatch console with quick disaster presets (Medical Trauma, Flash Flood Evacuation, Structural Collapse), coordinate tracking, priority tagging, and anti-double-click dispatch protections.
- `HospitalPanel.tsx`: Emergency Hospital Command Inbox displaying only cryptographically/protocol-verified delivered SOS messages (`DATA_DELIVERED`/`SOS_DELIVERED` backed by `/api/hospital/inbox`), complete with hop counts, coordinates, timestamp, and incident acknowledgment responses.
- `ControlsPanel.tsx`: Fail/recover controls for mesh nodes with role badges, link failure simulation, and runtime mode selection.

## Phase 1 Redesign Checkpoint
As of Phase 1, the frontend has been redesigned into an emergency command center adhering strictly to the backend truth:
- No hardcoded routes or fabricated deliveries.
- Full responsive grid layout with dark navy/slate theme, status rings, and tactical accents.
- Clear distinction between Simulation Mode and Real UDP/LAN Mode.

## Testing
Component and integration tests are executed via `npm test` using Vitest and React Testing Library:
- `App.test.tsx`: Tests core layout, branding headers, and mode badges.
- `TopologyView.test.tsx`: Tests node rendering, status indicators, and route highlights.
- `EventLog.test.tsx`: Tests event rendering, filtering, and clear functionality.
