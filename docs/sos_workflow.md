# SOS Workflow

## Overview
The SOS mechanism simulates a disaster victim (at a Rescue Node) sending an emergency message to a central hospital node (Node H). The frontend acts merely as the trigger, and the backend handles routing the SOS message over the AODV routing protocol.

## Step-by-Step Flow

1. **User Action**: The user selects a source node and inputs an SOS message (along with location details and priority) via the `ControlPanel`.
2. **API Request**: The frontend makes a POST request to `/api/sos` with the `SOSMessageRequest` payload.
3. **Backend Service**: `SimulationService.send_sos()` intercepts the request and generates a `DATA` packet containing the structured SOS payload.
4. **Route Discovery (AODV)**:
    - If the source node has no active route to the Hospital ('H'), it buffers the DATA packet and broadcasts an `RREQ` (Route Request).
    - The `RREQ` traverses intermediate nodes until it reaches 'H', which responds with an `RREP` (Route Reply).
    - Upon receiving the `RREP`, the source node unbuffers the DATA packet and forwards it.
5. **Data Delivery**: 
    - The DATA packet hops through the intermediate nodes exactly according to the established route.
    - Node H receives the packet and it's appended to the `hospital_inbox` in the `SimulationService`.
6. **Disaster Recovery**:
    - If a link or node fails during or after route establishment, attempting to send the SOS will result in a link failure at the intermediate node.
    - The intermediate node generates an `RERR` (Route Error), propagating it back to the source.
    - The next attempt to send the SOS triggers a *new* route discovery process, circumventing the failed node to successfully deliver the message.
7. **Frontend Updates**:
    - Throughout this process, the `SimulationService` and `AODVRouter` emit WebSocket events (e.g., `RREQ_GENERATED`, `DATA_FORWARDED`, `DATA_DELIVERED`, `ROUTE_INVALIDATED`).
    - The frontend `useSimulation` hook processes these events to animate packet movement on the `TopologyView` and logs them in the `EventLog`.
