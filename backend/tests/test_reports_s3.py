"""Service report uploads go through boto3 into (mocked) S3."""
from app.config import get_settings
from app.storage import get_s3_client


def my_job(client, headers):
    return client.get("/api/jobs", headers=headers).json()[0]


def test_farm_hand_uploads_report_to_s3(client, farm_hand):
    job = my_job(client, farm_hand)
    files = {"file": ("pump-check.txt", b"Pressure 42 psi, seals OK", "text/plain")}
    res = client.post(f"/api/jobs/{job['id']}/reports", files=files, data={"notes": "All good"}, headers=farm_hand)
    assert res.status_code == 201, res.text
    report = res.json()
    assert report["file_url"].startswith(f"s3://{get_settings().s3_bucket}/service-reports/job-{job['id']}/")
    assert report["file_size"] == 25

    # The object really is in the bucket, with the right bytes
    key = report["file_url"].split("/", 3)[3]
    obj = get_s3_client().get_object(Bucket=get_settings().s3_bucket, Key=key)
    assert obj["Body"].read() == b"Pressure 42 psi, seals OK"

    # ...and is reachable only through a short-lived presigned URL
    link = client.get(f"/api/reports/{report['id']}/download-url", headers=farm_hand).json()
    assert "Signature" in link["url"] or "X-Amz-Signature" in link["url"]
    assert link["expires_in"] == 300


def test_upload_rejects_wrong_type_and_auditor(client, farm_hand, auditor, admin):
    job = my_job(client, farm_hand)
    exe = {"file": ("virus.exe", b"MZ...", "application/x-msdownload")}
    assert client.post(f"/api/jobs/{job['id']}/reports", files=exe, headers=farm_hand).status_code == 415
    txt = {"file": ("a.txt", b"hello", "text/plain")}
    assert client.post(f"/api/jobs/{job['id']}/reports", files=txt, headers=auditor).status_code == 403


def test_seeded_reports_exist_in_s3(client, admin):
    reports = client.get("/api/reports", headers=admin).json()
    assert len(reports) >= 70
    pdf = next(r for r in reports if r["content_type"] == "application/pdf")
    key = pdf["file_url"].split("/", 3)[3]
    body = get_s3_client().get_object(Bucket=get_settings().s3_bucket, Key=key)["Body"].read()
    assert body.startswith(b"%PDF")
