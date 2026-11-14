from fastapi.testclient import TestClient
from app.main import app
client=TestClient(app)
def test_health_and_contract():
    assert client.get("/health").json()["status"]=="ok"
    response=client.post("/api/rotations/compare",json={"farm":{"current_crop":"unknown","farm_area_ha":1},"strategy":"water_saving","candidate_crop_ids":["crop-unknown"]})
    body=response.json(); assert response.status_code==200; assert body["provenance"]["forecast_available"] is False; assert {"recommendations","rejected_alternatives","missing_data_warnings","provenance","scoring"}.issubset(body)
def test_new_endpoints():
    assert client.get("/api/crops").status_code==200; assert client.get("/api/soil/profile").status_code==200
