"""The five key business questions, checked against the deterministic seed data."""


def test_low_fuel(client, admin):
    data = client.get("/api/analytics/low-fuel", headers=admin).json()
    assert data["count"] == 7
    assert all(i["fuel_level"] < 20 and i["status"] in ("Idle", "In-Use") for i in data["items"])
    assert [i["fuel_level"] for i in data["items"]] == sorted(i["fuel_level"] for i in data["items"])
    wider = client.get("/api/analytics/low-fuel", params={"threshold": 30}, headers=admin).json()
    assert wider["count"] >= data["count"]
    assert client.get("/api/analytics/low-fuel", params={"threshold": 101}, headers=admin).status_code == 422


def test_co_location(client, admin):
    data = client.get("/api/analytics/co-location", headers=admin).json()
    assert data["count"] == 5
    assert all(i["equipment_farm"] != i["farmhand_farm"] for i in data["items"])


def test_reliability(client, admin):
    rows = client.get("/api/analytics/reliability", headers=admin).json()
    assert len(rows) == 10
    worst = rows[0]
    assert worst["model"] == "Claas Lexion 8800"
    for r in rows:
        assert r["completed"] + r["failed"] == r["total_finished"]
        assert abs(r["completion_rate"] + r["failure_rate"] - 1) < 0.001


def test_maintenance_flags(client, admin):
    data = client.get("/api/analytics/maintenance-flags", headers=admin).json()
    flagged = {i["farm_name"] for i in data["items"] if i["flagged"]}
    assert flagged == {"Golden Hollow Ranch", "Willow Creek Elevator"}
    only = client.get("/api/analytics/maintenance-flags", params={"only_flagged": True}, headers=admin).json()
    assert {i["farm_name"] for i in only["items"]} == flagged  # HAVING clause path


def test_supervisor_activity(client, admin):
    rows = client.get("/api/analytics/supervisor-activity", headers=admin).json()
    assert len(rows) == 3
    for r in rows:
        assert r["direct_reports"] == 4
        assert r["reports_with_active_jobs"] == 3
    one = client.get("/api/analytics/supervisor-activity", params={"supervisor_id": rows[0]["supervisor_id"]}, headers=admin).json()
    assert len(one) == 1


def test_summary(client, auditor):
    s = client.get("/api/analytics/summary", headers=auditor).json()
    assert s["total_farms"] == 6
    assert s["total_equipment"] == 56
    assert s["low_fuel_count"] == 7
    assert s["maintenance_flagged_farms"] == 2
    assert s["colocation_discrepancies"] == 5
