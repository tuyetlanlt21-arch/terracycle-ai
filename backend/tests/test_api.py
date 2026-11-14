from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health():
    assert client.get("/health").json() == {"status": "ok"}

def test_demo_and_compare():
    payload = client.get("/api/demo").json()
    assert len(payload["fields"]) == 3
    response = client.post("/api/scenarios/compare", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert len(body["actions"]) == 3
    assert [x["priority"] for x in body["actions"]] == [1, 2, 3]
    assert body["provenance"]["forecast_available"] is False

def test_duplicate_field_rejected():
    payload = client.get("/api/demo").json()
    payload["fields"][1]["id"] = payload["fields"][0]["id"]
    assert client.post("/api/scenarios/compare", json=payload).status_code == 422

def test_negative_rain_rejected():
    payload = client.get("/api/demo").json()
    payload["rain_mm"] = -1
    assert client.post("/api/scenarios/compare", json=payload).status_code == 422
