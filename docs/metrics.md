# ResQNet Metrics System

## Overview
The metrics system quantifies network performance and routing overhead in the ResQNet AODV implementation. All metrics are calculated and tracked in the backend `SimulationService`, acting as the single source of truth, and are exposed via the `/api/metrics` endpoint. The React frontend simply polls this endpoint and renders the values.

## Internal Mapping
The following maps each metric from its backend source calculation to its frontend display:

### 1. Packets Sent
- **Backend Source:** `_on_simulation_event` tracking `DATA_CREATED` events.
- **Calculation:** `packets_sent += 1`
- **API Field:** `packets_sent`
- **Frontend Display:** `metrics.packets_sent`

### 2. Packets Delivered
- **Backend Source:** `_on_simulation_event` tracking `DATA_DELIVERED` events.
- **Calculation:** `packets_delivered += 1`
- **API Field:** `packets_delivered`
- **Frontend Display:** `metrics.packets_delivered`

### 3. Packets Dropped
- **Backend Source:** `_on_simulation_event` tracking `DATA_DROPPED` events.
- **Calculation:** `packets_dropped += 1`
- **API Field:** `packets_dropped`
- **Frontend Display:** `metrics.packets_dropped`

### 4. PDR (Packet Delivery Ratio)
- **Backend Source:** Computed dynamically in `SimulationService.get_metrics()`.
- **Calculation:** `(packets_delivered / packets_sent) * 100` (Formatted as percentage). Returns `0%` if `packets_sent` is 0.
- **API Field:** `pdr`
- **Frontend Display:** `metrics.pdr`

### 5. Loss (Packet Loss Ratio)
- **Backend Source:** Computed dynamically in `SimulationService.get_metrics()`.
- **Calculation:** `(packets_dropped / packets_sent) * 100` (Formatted as percentage). Returns `0%` if `packets_sent` is 0.
- **API Field:** `loss`
- **Frontend Display:** `metrics.loss`

### 6. Avg Hops (Average Hop Count)
- **Backend Source:** `total_hop_count` tracked during `DATA_DELIVERED` events, combined with `packets_delivered`.
- **Calculation:** `total_hop_count / packets_delivered`. Returns `0` if no packets delivered.
- **API Field:** `avg_hop_count`
- **Frontend Display:** `metrics.avg_hop_count`

### 7. RREQ Count (Route Request Overhead)
- **Backend Source:** `_on_simulation_event` tracking `RREQ_GENERATED` events.
- **Calculation:** `rreq_count += 1`
- **API Field:** `rreq_count`
- **Frontend Display:** `metrics.rreq_count`

### 8. RREP Count (Route Reply Overhead)
- **Backend Source:** `_on_simulation_event` tracking `RREP_GENERATED` events.
- **Calculation:** `rrep_count += 1`
- **API Field:** `rrep_count`
- **Frontend Display:** `metrics.rrep_count`

### 9. RERR Count (Route Error Overhead)
- **Backend Source:** `_on_simulation_event` tracking `RERR_GENERATED` events.
- **Calculation:** `rerr_count += 1`
- **API Field:** `rerr_count`
- **Frontend Display:** `metrics.rerr_count`

### Unimplemented (Placeholder) Metrics
The following metrics are included in the API contract and frontend UI but currently return a hardcoded `"N/A"` as their computation requires timestamp tracking across async route resolution:
- **Discovery Time** (`route_discovery_time`)
- **Recovery Time** (`recovery_time`)
- **Latency** (`latency`)
- **Throughput** (`throughput`)
