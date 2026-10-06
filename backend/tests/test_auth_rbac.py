"""Authentication (who are you?) and RBAC (what may you do?)."""


def test_login_returns_jwt_and_user(client):
    res = client.post("/api/auth/login", data={"username": "admin@prairiecrest.coop", "password": "AgriCore2026!"})
    assert res.status_code == 200
    body = res.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["role"] == "admin"
    assert "hashed_password" not in body["user"]  # response_model hides it


def test_wrong_password_is_401(client):
    res = client.post("/api/auth/login", data={"username": "admin@prairiecrest.coop", "password": "nope"})
    assert res.status_code == 401


def test_missing_or_bad_token_is_401(client):
    assert client.get("/api/equipment").status_code == 401
    assert client.get("/api/equipment", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_me(client, farm_hand):
    me = client.get("/api/auth/me", headers=farm_hand).json()
    assert me["full_name"] == "Tyler Hansen"
    assert me["role"] == "farm_hand"


def test_auditor_can_read_but_not_write(client, auditor):
    assert client.get("/api/equipment", headers=auditor).status_code == 200
    assert client.get("/api/analytics/summary", headers=auditor).status_code == 200
    assert client.get("/api/audit-logs", headers=auditor).status_code == 200
    farm = {"name": "Nope Farm", "location_region": "Nowhere", "capacity": 5}
    assert client.post("/api/farms", json=farm, headers=auditor).status_code == 403
    assert client.patch("/api/jobs/1/status", json={"status": "Completed"}, headers=auditor).status_code == 403


def test_farm_hand_cannot_use_admin_or_analytics_endpoints(client, farm_hand):
    assert client.get("/api/analytics/summary", headers=farm_hand).status_code == 403
    assert client.get("/api/users", headers=farm_hand).status_code == 403
    assert client.delete("/api/equipment/1", headers=farm_hand).status_code == 403


def test_farm_hand_only_sees_own_jobs_and_equipment(client, farm_hand):
    me = client.get("/api/auth/me", headers=farm_hand).json()
    jobs = client.get("/api/jobs", headers=farm_hand).json()
    assert jobs and all(j["operator_id"] == me["id"] for j in jobs)
    equipment = client.get("/api/equipment", headers=farm_hand).json()
    job_equipment = {j["equipment_id"] for j in jobs}
    assert all(e["assigned_to_id"] == me["id"] or e["id"] in job_equipment for e in equipment)


def test_farm_hand_gets_404_for_someone_elses_job(client, admin, farm_hand):
    me = client.get("/api/auth/me", headers=farm_hand).json()
    other = next(j for j in client.get("/api/jobs", headers=admin).json() if j["operator_id"] != me["id"])
    assert client.get(f"/api/jobs/{other['id']}", headers=farm_hand).status_code == 404


def test_farm_hand_status_change_and_equipment_sync(client, admin, farm_hand):
    pending = next(j for j in client.get("/api/jobs", params={"status": "Pending"}, headers=farm_hand).json())
    res = client.patch(f"/api/jobs/{pending['id']}/status", json={"status": "In-Progress"}, headers=farm_hand)
    assert res.status_code == 200 and res.json()["status"] == "In-Progress"
    unit = client.get(f"/api/equipment/{pending['equipment_id']}", headers=admin).json()
    assert unit["status"] == "In-Use"  # business rule: starting a job puts the machine to work

    res = client.patch(f"/api/jobs/{pending['id']}/status", json={"status": "Completed"}, headers=farm_hand)
    assert res.status_code == 200
    # Farm hands can't reopen finished work
    res = client.patch(f"/api/jobs/{pending['id']}/status", json={"status": "Pending"}, headers=farm_hand)
    assert res.status_code == 409


def test_actions_are_written_to_audit_log(client, auditor):
    logs = client.get("/api/audit-logs", params={"search": "farmhand@"}, headers=auditor).json()
    actions = {l["action"] for l in logs}
    assert {"LOGIN", "STATUS_CHANGE"} <= actions
