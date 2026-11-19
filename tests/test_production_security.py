import os
import pytest
from fastapi.testclient import TestClient

from resqnet.backend.app.main import app, validate_production_configuration
from resqnet.backend.app.services.runtime_manager import runtime_manager

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup_env():
    """Restores environment variables after each security test."""
    original_env = os.environ.copy()
    yield
    os.environ.clear()
    os.environ.update(original_env)

def test_production_simulation_mode_rejection():
    """Verify that production startup strictly rejects simulation mode."""
    os.environ["RESQNET_PRODUCTION"] = "true"
    os.environ["RESQNET_MODE"] = "simulation"
    os.environ["RESQNET_ADMIN_KEY"] = "strong_admin_key_123"
    os.environ["RESQNET_HOSPITAL_KEY"] = "strong_hospital_key_456"

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_configuration()
    assert "Production deployment requires RESQNET_MODE=real" in str(exc_info.value)

def test_production_missing_admin_key_rejection():
    """Verify that production startup strictly rejects empty or default admin key."""
    os.environ["RESQNET_PRODUCTION"] = "true"
    os.environ["RESQNET_MODE"] = "real"
    os.environ["RESQNET_ADMIN_KEY"] = ""
    os.environ["RESQNET_HOSPITAL_KEY"] = "strong_hospital_key_456"

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_configuration()
    assert "requires a secure RESQNET_ADMIN_KEY" in str(exc_info.value)

def test_production_missing_hospital_key_rejection():
    """Verify that production startup strictly rejects missing hospital clinician credential."""
    os.environ["RESQNET_PRODUCTION"] = "true"
    os.environ["RESQNET_MODE"] = "real"
    os.environ["RESQNET_ADMIN_KEY"] = "strong_admin_key_123"
    os.environ["RESQNET_HOSPITAL_KEY"] = ""

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_configuration()
    assert "requires a secure RESQNET_HOSPITAL_KEY" in str(exc_info.value)

def test_production_identical_keys_rejection():
    """Verify that network admin key cannot be reused as hospital clinician credential."""
    os.environ["RESQNET_PRODUCTION"] = "true"
    os.environ["RESQNET_MODE"] = "real"
    os.environ["RESQNET_ADMIN_KEY"] = "same_secret_key_123"
    os.environ["RESQNET_HOSPITAL_KEY"] = "same_secret_key_123"

    with pytest.raises(RuntimeError) as exc_info:
        validate_production_configuration()
    assert "RESQNET_ADMIN_KEY and RESQNET_HOSPITAL_KEY must not be identical" in str(exc_info.value)

def test_admin_key_authorization_lifecycle():
    """
    Test admin key enforcement on administrative controls:
    - Missing key -> HTTP 401
    - Invalid key -> HTTP 401
    - Correct key -> HTTP 200
    """
    admin_secret = "test_admin_auth_token_999"
    os.environ["RESQNET_ADMIN_KEY"] = admin_secret

    # 1. Missing header -> 401
    resp_missing = client.post("/api/nodes/B/fail")
    assert resp_missing.status_code == 401
    assert "Admin key required" in resp_missing.json()["detail"]

    # 2. Invalid header -> 401
    resp_invalid = client.post("/api/nodes/B/fail", headers={"X-Admin-Key": "wrong_key"})
    assert resp_invalid.status_code == 401

    # 3. Correct header -> 200
    resp_valid = client.post("/api/nodes/B/fail", headers={"X-Admin-Key": admin_secret})
    assert resp_valid.status_code == 200
    assert resp_valid.json()["is_active"] is False

    # Recover with correct key
    resp_rec = client.post("/api/nodes/B/recover", headers={"X-Admin-Key": admin_secret})
    assert resp_rec.status_code == 200
    assert resp_rec.json()["is_active"] is True

def test_hospital_clinician_authentication_and_sos_correlation():
    """
    Test hospital clinician triage authentication and SOS correlation:
    - Missing clinician credential -> HTTP 401
    - Admin key provided instead -> HTTP 401 (privilege separation)
    - Missing SOS reference -> HTTP 400
    - Non-existent SOS ID -> HTTP 404
    - Valid credential + Valid SOS -> HTTP 200
    """
    admin_secret = "admin_token_001"
    clinician_secret = "doctor_token_002"
    os.environ["RESQNET_ADMIN_KEY"] = admin_secret
    os.environ["RESQNET_HOSPITAL_KEY"] = clinician_secret

    # Reset simulation
    client.post("/api/simulation/reset", headers={"X-Admin-Key": admin_secret})

    # Dispatch legitimate SOS from Rescue-A
    sos_payload = {
        "source_id": "A",
        "destination_id": "H",
        "message": "Trauma victim at Sector 4",
        "latitude": 18.5204,
        "longitude": 73.8567,
        "priority": "CRITICAL",
        "auto_discover": True
    }
    sos_resp = client.post("/api/sos", json=sos_payload)
    assert sos_resp.status_code == 200
    valid_sos_id = sos_resp.json()["message_id"]

    # 1. Anonymous visitor attempts response without key -> 401
    anon_resp = client.post("/api/hospital/respond", json={
        "source_id": "H",
        "destination_id": "A",
        "sos_message_id": valid_sos_id,
        "message": "Stay calm."
    })
    assert anon_resp.status_code == 401

    # 2. Network admin attempts response using admin key -> 401 (separated roles)
    admin_cross_resp = client.post(
        "/api/hospital/respond",
        headers={"X-Hospital-Key": admin_secret},
        json={
            "source_id": "H",
            "destination_id": "A",
            "sos_message_id": valid_sos_id,
            "message": "Admin message."
        }
    )
    assert admin_cross_resp.status_code == 401

    # 3. Missing sos_message_id -> 400
    missing_sos_resp = client.post(
        "/api/hospital/respond",
        headers={"X-Hospital-Key": clinician_secret},
        json={
            "source_id": "H",
            "destination_id": "A",
            "sos_message_id": "",
            "message": "Instruction."
        }
    )
    assert missing_sos_resp.status_code == 400

    # 4. Unknown/fabricated SOS ID -> 404
    fake_sos_resp = client.post(
        "/api/hospital/respond",
        headers={"X-Hospital-Key": clinician_secret},
        json={
            "source_id": "H",
            "destination_id": "A",
            "sos_message_id": "SOS-FAKE-99999",
            "message": "Instruction."
        }
    )
    assert fake_sos_resp.status_code == 404

    # 5. Authenticated clinician with valid existing SOS ID -> 200
    valid_resp = client.post(
        "/api/hospital/respond",
        headers={"X-Hospital-Key": clinician_secret},
        json={
            "source_id": "H",
            "destination_id": "A",
            "sos_message_id": valid_sos_id,
            "message": "Administer oxygen and maintain airway. Medevac airborne."
        }
    )
    assert valid_resp.status_code == 200

def test_websocket_origin_security():
    """Verify that strict WebSocket origin validation rejects unauthorized origins."""
    os.environ["RESQNET_STRICT_WS_ORIGIN"] = "true"

    # Unauthorized external origin should be rejected with code 1008
    with pytest.raises(Exception):
        with client.websocket_connect("/ws", headers={"Origin": "https://malicious-site.example.com"}):
            pass

    # Allowed origin (e.g. localhost) should be accepted
    with client.websocket_connect("/ws", headers={"Origin": "http://localhost:5173"}) as ws:
        init_ev = ws.receive_json()
        assert init_ev["type"] == "INITIAL_STATE"

def test_health_api_exposes_runtime_mode():
    """Verify that /health exposes active runtime mode and real runtime status."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "ResQNet"
    assert "runtime_mode" in data
    assert "real_runtime_running" in data
