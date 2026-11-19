import urllib.request
import json
import time

BASE_URL = "http://127.0.0.1:8000/api"
HEADERS = {
    "Content-Type": "application/json",
    "Origin": "http://127.0.0.1:5174"
}

def post(endpoint, data=None):
    url = f"{BASE_URL}/{endpoint}"
    payload = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=payload, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get(endpoint):
    url = f"{BASE_URL}/{endpoint}"
    req = urllib.request.Request(url, headers={"Origin": "http://127.0.0.1:5174"}, method="GET")
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    print("=== STEP 1: RESET SIMULATION ===")
    reset_res = post("simulation/reset")
    print("Reset response:", reset_res)

    net_initial = get("network")
    print(f"Initial network: {len(net_initial['nodes'])} nodes active={all(n['is_active'] for n in net_initial['nodes'])}, route={net_initial['active_route']}")
    assert net_initial['active_route'] == []

    inbox_initial = get("hospital/inbox")
    print(f"Initial hospital inbox count: {len(inbox_initial)}")
    assert len(inbox_initial) == 0

    metrics_initial = get("metrics")
    print(f"Initial metrics: PDR={metrics_initial['pdr']}, sent={metrics_initial['packets_sent']}, delivered={metrics_initial['packets_delivered']}, dropped={metrics_initial['packets_dropped']}")
    assert metrics_initial['packets_sent'] == 0

    print("\n=== STEP 2: DISPATCH FRESH UNIQUELY IDENTIFIED SOS ===")
    unique_msg_id = f"LIVE-SOS-{int(time.time())}"
    sos_payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "CRITICAL RESCUE NEEDED AT FLOOD SECTOR 4",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "CRITICAL",
        "message_id": unique_msg_id,
        "auto_discover": True
    }
    sos_res = post("sos", sos_payload)
    print("SOS Dispatch Response:")
    print("  Success:", sos_res.get("success"))
    print("  Message ID:", sos_res.get("message_id"))
    print("  Route History:", sos_res.get("packet", {}).get("route_history"))
    print("  ACK Status:", sos_res.get("ack_status"))
    print("  RTT (ms):", sos_res.get("rtt_ms"))
    assert sos_res.get("success") is True
    assert sos_res.get("packet", {}).get("route_history") == ["A", "B", "C", "H"]
    assert sos_res.get("ack_status") == "CONFIRMED"

    print("\n=== STEP 3: VERIFY EXACT MESSAGE IN /api/hospital/inbox ===")
    inbox = get("hospital/inbox")
    print(f"Inbox total items: {len(inbox)}")
    assert len(inbox) == 1
    inbox_item = inbox[0]
    print(f"Inbox item message_id: {inbox_item['message_id']}")
    print(f"Inbox item message: {inbox_item['message']}")
    print(f"Inbox item source_id: {inbox_item['source_id']}")
    print(f"Inbox item priority: {inbox_item['priority']}")
    assert inbox_item["message_id"] == unique_msg_id
    assert inbox_item["message"] == "CRITICAL RESCUE NEEDED AT FLOOD SECTOR 4"
    assert inbox_item["source_id"] == "A"
    assert inbox_item["priority"] == "CRITICAL"

    print("\n=== STEP 4: QUERY /api/sos/status/{message_id} FOR ACK STATE ===")
    status_info = get(f"sos/status/{unique_msg_id}")
    print("ACK Tracking Info:")
    print("  Message ID:", status_info["message_id"])
    print("  Status:", status_info["status"])
    print("  Source:", status_info["source_id"])
    print("  Destination:", status_info["destination_id"])
    print("  Confirmed At:", status_info["confirmed_at"])
    print("  RTT (ms):", status_info["rtt_ms"])
    assert status_info["status"] == "CONFIRMED"
    assert status_info["rtt_ms"] is not None and status_info["rtt_ms"] >= 0.0

    print("\n=== STEP 5: COMPARE /api/network, /api/metrics, /api/events ===")
    net_after = get("network")
    print("Active route in /api/network:", net_after["active_route"])
    assert net_after["active_route"] == ["A", "B", "C", "H"]

    metrics_after = get("metrics")
    print(f"Metrics after SOS: PDR={metrics_after['pdr']}, Sent={metrics_after['packets_sent']}, Delivered={metrics_after['packets_delivered']}, Dropped={metrics_after['packets_dropped']}, Hops={metrics_after['avg_hop_count']}")
    assert metrics_after["pdr"] == "100.0%"
    assert metrics_after["packets_sent"] == 1
    assert metrics_after["packets_delivered"] == 1
    assert metrics_after["packets_dropped"] == 0

    events = get("events")
    print(f"Total events recorded: {len(events)}")
    print("Sample events:", events[-5:])

    print("\n=== STEP 6: TEST ALTERNATE ROUTE FAILOVER ===")
    print("Failing link A-B...")
    fail_ab = post("links/fail", {"node_a": "A", "node_b": "B"})
    print("Link fail response:", fail_ab)

    net_failed = get("network")
    ab_active = any(l["is_active"] for l in net_failed["links"] if (l["node_a_id"] == "A" and l["node_b_id"] == "B") or (l["node_a_id"] == "B" and l["node_b_id"] == "A"))
    print(f"Is link A-B active: {ab_active}, active route: {net_failed['active_route']}")
    assert ab_active is False
    assert net_failed["active_route"] == []

    unique_msg_id_2 = f"LIVE-ALT-{int(time.time())}"
    sos_payload_alt = {
        "source_id": "A",
        "destination_id": "H",
        "message": "FAILOVER TEST VIA RELAY-D",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "HIGH",
        "message_id": unique_msg_id_2,
        "auto_discover": True
    }
    sos_alt_res = post("sos", sos_payload_alt)
    print("Alternate Route SOS Dispatch Response:")
    print("  Success:", sos_alt_res.get("success"))
    print("  Message ID:", sos_alt_res.get("message_id"))
    print("  Route History:", sos_alt_res.get("packet", {}).get("route_history"))
    print("  ACK Status:", sos_alt_res.get("ack_status"))
    assert sos_alt_res.get("success") is True
    assert sos_alt_res.get("packet", {}).get("route_history") == ["A", "D", "C", "H"]
    assert sos_alt_res.get("ack_status") == "CONFIRMED"

    net_alt = get("network")
    print("Active route after alternate delivery:", net_alt["active_route"])
    assert net_alt["active_route"] == ["A", "D", "C", "H"]

    inbox_after_alt = get("hospital/inbox")
    print(f"Hospital inbox total items: {len(inbox_after_alt)}")
    assert len(inbox_after_alt) == 2

    print("\n=== STEP 7: TEST RESET AND REPEAT WITHOUT STALE STATE ===")
    post("simulation/reset")
    inbox_reset = get("hospital/inbox")
    metrics_reset = get("metrics")
    net_reset = get("network")
    print(f"After reset -> inbox: {len(inbox_reset)}, PDR: {metrics_reset['pdr']}, active route: {net_reset['active_route']}")
    assert len(inbox_reset) == 0
    assert metrics_reset["packets_sent"] == 0
    assert net_reset["active_route"] == []

    unique_msg_id_3 = f"REPEAT-TEST-{int(time.time())}"
    sos_payload_3 = {
        "source_id": "A",
        "destination_id": "H",
        "message": "REPEAT DISPATCH FRESH STATE",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "CRITICAL",
        "message_id": unique_msg_id_3,
        "auto_discover": True
    }
    sos_res_3 = post("sos", sos_payload_3)
    assert sos_res_3.get("success") is True
    assert sos_res_3.get("packet", {}).get("route_history") == ["A", "B", "C", "H"]
    inbox_repeat = get("hospital/inbox")
    assert len(inbox_repeat) == 1
    assert inbox_repeat[0]["message_id"] == unique_msg_id_3
    print("Repeat dispatch succeeded with exactly 1 fresh item in hospital inbox!")

    print("\n>>> ALL LIVE VERIFICATION CRITERIA PASSED CLEANLY! <<<")

if __name__ == "__main__":
    main()
