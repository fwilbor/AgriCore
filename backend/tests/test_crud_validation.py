"""REST CRUD + Pydantic validation."""

NEW_UNIT = {
    "serial_number": "jd8r-2026-9001",
    "model": "John Deere 8R 410",
    "equipment_type": "Tractor",
    "fuel_level": 88.5,
    "facility_id": 1,
}


def test_create_update_delete_equipment(client, admin):
    res = client.post("/api/equipment", json=NEW_UNIT, headers=admin)
    assert res.status_code == 201, res.text
    unit = res.json()
    assert unit["serial_number"] == "JD8R-2026-9001"  # normalised by a field_validator
    assert unit["status"] == "Idle"  # schema default
    assert unit["farm_name"] == "Prairie Crest North"

    res = client.patch(f"/api/equipment/{unit['id']}", json={"status": "Maintenance"}, headers=admin)
    assert res.status_code == 200
    assert res.json()["status"] == "Maintenance"
    assert res.json()["fuel_level"] == 88.5  # PATCH leaves unsent fields alone

    assert client.post("/api/equipment", json=NEW_UNIT, headers=admin).status_code == 409  # duplicate serial
    assert client.delete(f"/api/equipment/{unit['id']}", headers=admin).status_code == 204
    assert client.get(f"/api/equipment/{unit['id']}", headers=admin).status_code == 404


def test_pydantic_rejects_bad_payloads(client, admin):
    cases = [
        ({**NEW_UNIT, "fuel_level": 150}, "fuel_level"),
        ({**NEW_UNIT, "equipment_type": "Spaceship"}, "equipment_type"),
        ({**NEW_UNIT, "serial_number": "bad serial!"}, "serial_number"),
        ({k: v for k, v in NEW_UNIT.items() if k != "model"}, "model"),
    ]
    for payload, field in cases:
        res = client.post("/api/equipment", json=payload, headers=admin)
        assert res.status_code == 422
        assert res.json()["detail"][0]["loc"][-1] == field


def test_reference_checks(client, admin):
    assert client.post("/api/equipment", json={**NEW_UNIT, "serial_number": "X-0001", "facility_id": 999}, headers=admin).status_code == 422
    assert client.post("/api/equipment", json={**NEW_UNIT, "serial_number": "X-0002", "assigned_to_id": 1}, headers=admin).status_code == 422  # user 1 is the admin, not a farm hand


def test_equipment_with_history_cannot_be_deleted(client, admin):
    job = client.get("/api/jobs", headers=admin).json()[0]
    res = client.delete(f"/api/equipment/{job['equipment_id']}", headers=admin)
    assert res.status_code == 409


def test_farm_with_equipment_cannot_be_deleted(client, admin):
    assert client.delete("/api/farms/1", headers=admin).status_code == 409


def test_equipment_filters(client, admin):
    maint = client.get("/api/equipment", params={"status": "Maintenance"}, headers=admin).json()
    assert maint and all(e["status"] == "Maintenance" for e in maint)
    found = client.get("/api/equipment", params={"search": "lexion"}, headers=admin).json()
    assert found and all("Lexion" in e["model"] for e in found)


def test_create_job_and_user(client, admin):
    job = {"title": "Emergency spraying - North 40", "priority": "Critical", "equipment_id": 1}
    res = client.post("/api/jobs", json=job, headers=admin)
    assert res.status_code == 201 and res.json()["status"] == "Pending"

    user = {"email": "New.Hand@PrairieCrest.coop", "full_name": "New Hand", "role": "farm_hand", "password": "short"}
    assert client.post("/api/users", json=user, headers=admin).status_code == 422  # password too short
    res = client.post("/api/users", json={**user, "password": "longenough1"}, headers=admin)
    assert res.status_code == 201 and res.json()["email"] == "new.hand@prairiecrest.coop"
