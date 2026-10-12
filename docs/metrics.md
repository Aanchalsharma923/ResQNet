# ResQNet Metrics System

## Overview
The metrics system quantifies network performance, routing reliability, and protocol overhead in the ResQNet AODV implementation. Metrics are tracked across both runtime engines:
1. **Simulation Mode** (`SimulationService`): Deterministic event-driven simulation where step-based events track packet counters, hop counts, and control messages.
2. **Real Network Mode** (`RealNetworkRuntime`): Real independent multi-process nodes communicating over UDP datagrams, with full wall-clock timestamp tracking for discovery time, recovery time, latency, and throughput.

Metrics are exposed via the `/api/metrics` endpoint and rendered live by the React frontend dashboard `MetricsPanel`.

---

## Metric Definitions & Formulas

### 1. Packets Sent (`packets_sent`)
- **Definition**: Total number of distinct end-to-end user `DATA` packets created and injected at source nodes.
- **Backend Source**: Tracked on `DATA_CREATED` events.
- **Counting Rule**: Counted once at packet origination. Intermediate forwardings (`DATA_FORWARDED`) do **not** increment this counter.
- **Formula**: `packets_sent = count(DATA_CREATED)`

### 2. Packets Delivered (`packets_delivered`)
- **Definition**: Total number of `DATA` packets that successfully reach their destination node.
- **Backend Source**: Tracked on `DATA_DELIVERED` events at destination nodes.
- **Counting Rule**: Counted once upon final destination reception.
- **Formula**: `packets_delivered = count(DATA_DELIVERED)`

### 3. Packets Dropped (`packets_dropped`)
- **Definition**: Total number of `DATA` packets discarded due to unroutable destinations (no route available), link failures, or TTL expiration.
- **Backend Source**: Tracked on `DATA_DROPPED` events.
- **Counting Rule**: Counted when a packet cannot be forwarded. Control packets (RREQ/RREP/RERR) are not counted as user data drops.
- **Formula**: `packets_dropped = count(DATA_DROPPED)`

### 4. Packet Delivery Ratio (`pdr`)
- **Definition**: Percentage of injected DATA packets successfully delivered to the destination.
- **Formula**:
  $$\text{PDR} = \left(\frac{\text{packets\_delivered}}{\text{packets\_sent}}\right) \times 100\%$$
- **Edge Case**: Returns `0%` if `packets_sent == 0`. Formatted to 1 decimal place (e.g., `50.0%`).

### 5. Packet Loss Ratio (`loss`)
- **Definition**: Percentage of injected DATA packets that were dropped.
- **Formula**:
  $$\text{Loss} = \left(\frac{\text{packets\_dropped}}{\text{packets\_sent}}\right) \times 100\%$$
- **Edge Case**: Returns `0%` if `packets_sent == 0`. Formatted to 1 decimal place (e.g., `50.0%`).
- **Mathematical Reconciliation**: Because every injected packet either completes delivery or is dropped:
  $$\text{packets\_sent} = \text{packets\_delivered} + \text{packets\_dropped} \implies \text{PDR} + \text{Loss} = 100.0\%$$

### 6. Average Hop Count (`avg_hop_count`)
- **Definition**: Mean number of network hops traversed by delivered DATA packets.
- **Formula**:
  $$\text{avg\_hop\_count} = \frac{\sum \text{hop\_count}}{\text{packets\_delivered}}$$
- **Edge Case**: Returns `0` if no packets delivered.

### 7. RREQ Count (`rreq_count`)
- **Definition**: Total number of AODV Route Request packets originated in the network.
- **Backend Source**: Tracked on `RREQ_GENERATED` events.
- **Counting Rule**: Flooded forwards (`RREQ_FORWARDED`) do **not** increment this counter.

### 8. RREP Count (`rrep_count`)
- **Definition**: Total number of AODV Route Reply packets originated in the network.
- **Backend Source**: Tracked on `RREP_GENERATED` events.
- **Counting Rule**: Unicast forwards (`RREP_FORWARDED`) do **not** increment this counter.

### 9. RERR Count (`rerr_count`)
- **Definition**: Total number of AODV Route Error packets originated in the network upon link/neighbor failure.
- **Backend Source**: Tracked on `RERR_GENERATED` events.
- **Counting Rule**: Propagated forwards (`RERR_FORWARDED`) do **not** increment this counter.

---

## Dynamic Telemetry Metrics (Real Network Mode)

In Real Network Mode (`RealNetworkRuntime`), wall-clock timestamps provide empirical measurement of time-based metrics:

### 10. Route Discovery Time (`route_discovery_time`)
- **Definition**: Time elapsed between source node RREQ creation and source receipt of RREP (route established).
- **Measurement**:
  - $t_{\text{start}}$: timestamp of `RREQ_GENERATED` at initiating source.
  - $t_{\text{end}}$: timestamp of `ROUTE_DISCOVERY_COMPLETED` at initiating source.
  - $\text{Discovery Time} = (t_{\text{end}} - t_{\text{start}}) \times 1000\text{ ms}$.
- **Fallback**: Returns `"N/A"` if no route discovery occurred or in simulation mode.

### 11. Route Recovery Time (`recovery_time`)
- **Definition**: Total duration from catastrophic failure / route invalidation until the alternate route is discovered and installed.
- **Measurement**:
  - $t_{\text{failure}}$: timestamp when route invalidation / neighbor failure occurs on the active route (`ROUTE_INVALIDATED` or `NEIGHBOR_DOWN`).
  - $t_{\text{recovery}}$: timestamp when alternate route discovery completes (`ROUTE_DISCOVERY_COMPLETED`).
  - $\text{Recovery Time} = (t_{\text{recovery}} - t_{\text{failure}}) \times 1000\text{ ms}$.
- **Fallback**: Returns `"N/A"` if no failure recovery has occurred or in simulation mode.

### 12. End-to-End Latency (`latency`)
- **Definition**: Average end-to-end transit latency across all delivered DATA packets.
- **Measurement**:
  - For each delivered packet $i$: $\text{lat}_i = (t_{\text{delivered}, i} - t_{\text{created}, i}) \times 1000\text{ ms}$.
  - $\text{latency} = \frac{\sum_{i=1}^N \text{lat}_i}{N}\text{ ms}$.
- **Fallback**: Returns `"N/A"` if 0 packets have been delivered.

### 13. Throughput (`throughput`)
- **Definition**: Effective transmission throughput of delivered payload data during active transit.
- **Measurement**:
  - Sum of delivered payload bytes: $B = \sum \text{payload\_bytes}_i$.
  - Sum of packet transit durations: $T = \sum (t_{\text{delivered}, i} - t_{\text{created}, i})$ (in seconds).
  - Effective throughput in kbps:
    $$\text{Throughput} = \frac{B \times 8}{T \times 1000}\text{ kbps}$$
- **Rationale**: Measuring throughput over active delivery transit periods isolates channel performance from inter-event idle intervals or demo delays (e.g. heartbeat timeout waits).
- **Fallback**: Returns `"N/A"` if 0 packets delivered or transit duration unavailable. Never substitutes 0 for missing data.
