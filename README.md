# ResQNet

ResQNet is a disaster-resilient ad-hoc communication network simulator. It demonstrates how routing protocols (specifically AODV, introduced in Phase 2) can maintain communication between rescue teams and critical infrastructure when nodes or physical links fail.

## Phase 1: Core Network Engine

Phase 1 implements the foundational networking primitives:
- **Node**: Devices with valid IPv4 addressing and lifecycle states.
- **Link**: Bidirectional physical/logical connections between Nodes.
- **NetworkTopology**: Source-of-truth manager ensuring neighbors are strictly active and physically reachable.
- **Packet**: Data payload tracking lifecycle, routing history (actual hops visited), and TTL.
- **StaticRouter**: A baseline, deterministic router configured with a predefined route. It explicitly DOES NOT support dynamic pathfinding or failure recovery.
- **SimulationEngine**: Coordinates moving packets from source to destination using the topology and router, simulating hop-by-hop transmission.

### Running the Phase 1 CLI Demo

The Phase 1 demonstration proves the physical simulation layers function correctly, providing a rigorous baseline before AODV is introduced.

**Command:**
```bash
python -m resqnet.scripts.demo_phase1
```

**Scenario 1: Normal Communication**
The simulation configures the following topology:
```text
Rescue-A
    A
   / \
  B   D
   \ /
    C
    |
    H
 Hospital
```
The StaticRouter is strictly configured to traverse `A -> B -> C -> H`. The packet is successfully delivered via this route.

**Scenario 2: Intermediate Node Failure (No Auto-Recovery)**
Node `B` is artificially failed. When a new packet attempts to traverse the route, it drops at Node `A`.
Even though an alternate physical route `A -> D -> C -> H` exists, the `StaticRouter` strictly drops the packet. Dynamic alternate-route discovery and recovery are explicitly reserved for Phase 2 (AODV) to prove the simulation isn't magically "teleporting" packets.
