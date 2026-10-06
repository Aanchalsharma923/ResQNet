# Phase 1: Core Network Engine - Implementation Plan

This document details the atomic implementation tasks for Phase 1. Each task must be fully implemented and verified via automated tests before moving to the next.

## Task 1: Project Structure and Dependency Setup
- **Objective**: Establish the Python module structure and testing framework.
- **Files Involved**:
  - `requirements.txt`
  - `resqnet/__init__.py`
  - `resqnet/backend/__init__.py`
  - `resqnet/backend/app/__init__.py`
  - `resqnet/backend/app/models/__init__.py`
  - `resqnet/backend/app/simulation/__init__.py`
  - `resqnet/backend/app/routing/__init__.py`
  - `tests/__init__.py`
  - `tests/conftest.py`
- **Dependencies**: `pytest`
- **Implementation Details**: Create the directory structure as specified in the project specification. Set up `pytest` as the test runner. No functional code yet.
- **Acceptance Criteria**: Running `pytest` should succeed with "no tests ran".
- **Verification Command**: `pytest`

## Task 2: Node Model and IPv4 Validation
- **Objective**: Create the core entity representing a network node.
- **Files Involved**: 
  - `resqnet/backend/app/models/node.py`
  - `tests/test_node.py`
- **Implementation Details**:
  - `Node` class with `node_id` (string), `ip_address` (string), and `is_active` (boolean).
  - Validation to ensure `ip_address` is a valid IPv4 string format.
  - Ability to fail and recover a node (toggle `is_active`).
- **Acceptance Criteria**: Node instantiates correctly with valid IPs. Fails on invalid IPs. State can be toggled.
- **Verification Command**: `pytest tests/test_node.py -v`

## Task 3: Bidirectional Link Model
- **Objective**: Model the physical/logical connection between two nodes.
- **Files Involved**:
  - `resqnet/backend/app/models/link.py`
  - `tests/test_link.py`
- **Dependencies**: Task 2 (`Node`)
- **Implementation Details**:
  - `Link` class holding references to two `Node` objects.
  - `is_active` status (if the link is physically broken).
  - Bidirectional logic: if A is linked to B, B is linked to A.
- **Acceptance Criteria**: Link can connect two nodes. Can report if a connection between two specific IPs exists and is active.
- **Verification Command**: `pytest tests/test_link.py -v`

## Task 4: Network Topology
- **Objective**: Manage the collection of nodes and links.
- **Files Involved**:
  - `resqnet/backend/app/simulation/topology.py`
  - `tests/test_topology.py`
- **Dependencies**: Task 2, Task 3
- **Implementation Details**:
  - `NetworkTopology` class with methods to add nodes and links.
  - Method to fetch a node by IP.
  - Method to fetch neighbors of a given node (only active links and active neighbor nodes).
- **Acceptance Criteria**: Topology correctly registers the 5-node setup. Correctly returns active neighbors for a node.
- **Verification Command**: `pytest tests/test_topology.py -v`

## Task 5: Packet Model
- **Objective**: Represent data moving through the network.
- **Files Involved**:
  - `resqnet/backend/app/models/packet.py`
  - `tests/test_packet.py`
- **Implementation Details**:
  - `Packet` class containing `packet_id`, `source_ip`, `destination_ip`, `payload`, `ttl` (Time to Live), and `hop_count`.
  - Simple enum/type for packet types (e.g., `DATA` vs future control packets).
- **Acceptance Criteria**: Packet initializes correctly, hop count can be incremented, TTL can be decremented.
- **Verification Command**: `pytest tests/test_packet.py -v`

## Task 6: StaticRouter Baseline
- **Objective**: Provide a dummy routing mechanism strictly to test the forwarding engine, before AODV is implemented.
- **Files Involved**:
  - `resqnet/backend/app/routing/base.py`
  - `resqnet/backend/app/routing/static_router.py`
  - `tests/test_static_router.py`
- **Dependencies**: Task 4, Task 5
- **Implementation Details**:
  - Abstract `BaseRouter` interface with a `get_next_hop(destination_ip)` method.
  - `StaticRouter` pre-programmed with explicit static routes (e.g., A knows next hop to H is B. B knows next hop to H is C. C knows next hop to H is H).
- **Acceptance Criteria**: `StaticRouter` correctly returns the configured next hop IP for the baseline route.
- **Verification Command**: `pytest tests/test_static_router.py -v`

## Task 7: Simulation Engine and Forwarding
- **Objective**: Execute the hop-by-hop packet movement.
- **Files Involved**:
  - `resqnet/backend/app/simulation/engine.py`
  - `tests/test_engine.py`
- **Dependencies**: Tasks 4, 5, 6
- **Implementation Details**:
  - `SimulationEngine` ties `NetworkTopology` and a collection of `Routers` (one per node).
  - Method `send_packet(packet)`: simulates the hop-by-hop transmission.
  - If next hop is inactive/link broken, packet is DROPPED.
  - If TTL hits 0, packet is DROPPED.
  - If next hop is the destination, packet is DELIVERED.
- **Acceptance Criteria**: Packet successfully travels A → B → C → H and returns DELIVERED status.
- **Verification Command**: `pytest tests/test_engine.py -v`

## Task 8: CLI Demonstration and Failure Validation
- **Objective**: End-to-end demonstration of the baseline network.
- **Files Involved**:
  - `resqnet/scripts/demo_phase1.py`
- **Dependencies**: Task 7
- **Implementation Details**:
  - Instantiate the specific 5-node topology (A, B, C, D, H).
  - Configure `StaticRouter` for A → B → C → H.
  - Send packet "HELP REQUIRED". Print hops. Verify delivery.
  - Fail node B (`node_b.is_active = False`).
  - Send packet again.
  - Verify packet drops at A (since B is unreachable) and NO automatic reroute happens.
- **Acceptance Criteria**: Script runs, visually proving the required baseline success and failure scenarios.
- **Verification Command**: `python resqnet/scripts/demo_phase1.py`
