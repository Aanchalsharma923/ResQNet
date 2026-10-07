# Real Network Demonstration

## Setup Requirements
1. **Laptops:** 5 separate laptops connected to the same Wi-Fi or Ethernet LAN.
2. **Wi-Fi Isolation:** The network must allow direct peer-to-peer traffic.
3. **Firewalls:** All laptops must permit inbound UDP traffic on ports `50010-50014`.

## Preparation
1. Identify the private IP addresses of each laptop (e.g., `192.168.1.101`).
2. Update `configs/lan_nodes.json` so each node ID (`A` through `H`) accurately matches the IP address of its assigned laptop. Ensure ports are mapped correctly.
3. Distribute the `configs/lan_nodes.json` file to all 5 laptops.

## Execution

### Step 1: Start the Nodes
On Laptop 1: `python scripts/run_node.py --node-id A --config configs/lan_nodes.json --bind-host 0.0.0.0`
On Laptop 2: `python scripts/run_node.py --node-id B --config configs/lan_nodes.json --bind-host 0.0.0.0`
*(Repeat for C, D, and H)*

### Step 2: Verify Readiness
Check the console logs on all laptops. Ensure they display:
```
========================================
RESQNET NODE
========================================
...
Status: READY
```
And observe `HELLO` exchange indicating neighbors are healthy.

### Step 3: Trigger Route Discovery
*(In Phase 4.8 this will be done via UI, but for Phase 4.7 this represents the internal application flow where `A` wants to send DATA to `H`)*. 
Observe A generating a `RREQ` over the physical LAN to `B` and `D`.
Observe `H` replying with `RREP`.

### Step 4: Simulate Catastrophic Failure
Physically stop the Python process on Laptop 2 (Node `B`) by hitting `Ctrl+C`.

### Step 5: Observe AODV Route Recovery
1. Watch Laptop 1 (`A`) logs. After 3 seconds, observe: `HELLO TIMEOUT: B` and `NEIGHBOR_DOWN: B`.
2. Observe `A` invalidating the route through `B` and generating a `RERR`.
3. If new data is requested for `H`, observe `A` broadcasting a new `RREQ`.
4. The RREQ propagates through the remaining healthy network (`D` -> `C` -> `H`).
5. `H` replies with a new `RREP`.
6. Data delivery automatically recovers through the alternate physical path!
