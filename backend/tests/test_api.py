import os
import tempfile

os.environ["DATABASE_URL"] = "sqlite:///" + tempfile.mktemp(suffix=".db")
os.environ["JOB_MODE"] = "inline"
os.environ["DEMO_PASSWORD"] = "test-only-password-123"
import pytest
from fastapi.testclient import TestClient
from app.db import Base, engine, Session, Run
from app.seed import seed
from app.main import app, attempts


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(engine)
    seed()
    with TestClient(app) as c:
        yield c
    engine.dispose()


def sign_in(c, role="admin"):
    attempts.clear()
    assert (
        c.post(
            "/api/login",
            json={
                "email": role + "@gridmind.local",
                "password": "test-only-password-123",
            },
        ).status_code
        == 200
    )


def test_auth_and_roles(client):
    assert client.get("/api/factories").status_code == 401
    sign_in(client, "viewer")
    assert client.get("/api/factories").status_code == 200
    assert client.post("/api/runs", json={"dataset_id": 1}).status_code == 403
    assert client.post("/api/factories", json={}).status_code == 403
    assert client.get("/api/audit").status_code == 403
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_complete_journey(client):
    sign_in(client)
    ds = client.get("/api/datasets").json()
    assert len(ds) == 6
    job = client.post("/api/runs", json={"dataset_id": ds[0]["id"]}).json()
    run = client.get(f'/api/runs/{job["id"]}').json()
    assert run["status"] == "complete"
    with Session() as db:
        assert db.get(Run, job["id"]).result["baseline"]["optimized"]["rows"]
    sim = client.post(f'/api/simulations/{job["id"]}').json()
    assert (
        client.post(
            f'/api/simulations/{sim["id"]}/control', json={"action": "seek", "value": 5}
        ).json()["cursor"]
        == 5
    )
    for fmt in ("csv", "pdf"):
        r = client.get(f'/api/reports/{job["id"]}?format={fmt}')
        assert r.status_code == 200
        if fmt == "pdf":
            assert r.content.startswith(b"%PDF")
    scenario = client.post(
        "/api/runs",
        json={"kind": "scenario", "dataset_id": 1, "changes": {"tariff_scale": 1.25}},
    ).json()
    r = client.get(f'/api/runs/{scenario["id"]}').json()
    assert r["status"] == "complete" and r["result"]["difference"]["cost"] > 0


def test_import_and_forecast_job(client):
    sign_in(client)
    csv = client.get("/api/datasets/1/csv").content
    imported = client.post(
        "/api/datasets/import", files={"file": ("meter.csv", csv, "text/csv")}
    )
    assert imported.status_code == 200
    job = client.post(
        "/api/runs", json={"kind": "forecast", "dataset_id": imported.json()["id"]}
    ).json()
    assert client.get(f'/api/runs/{job["id"]}').json()["status"] == "complete"
    opt = client.post(
        "/api/runs",
        json={"dataset_id": imported.json()["id"], "forecast_id": job["id"]},
    ).json()
    result = client.get(f'/api/runs/{opt["id"]}').json()
    assert (
        result["status"] == "complete" and result["result"]["input_kind"] == "forecast"
    )


def test_csrf_and_cookie(client):
    sign_in(client)
    assert (
        client.post(
            "/api/logout", headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    r = client.post(
        "/api/login",
        json={"email": "admin@gridmind.local", "password": "test-only-password-123"},
    )
    assert (
        "HttpOnly" in r.headers["set-cookie"]
        and "SameSite=strict" in r.headers["set-cookie"]
    )
