import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import app as api_app


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "it_service_management.db"
    api_app.DATABASE_URL = f"sqlite:///{db_path}"
    api_app.ensure_schema()
    with TestClient(api_app.app) as test_client:
        yield test_client


def create_request(client, **overrides):
    payload = {
        "requester_id": 1,
        "category_id": 1,
        "priority_id": 1,
        "sla_policy_id": 1,
        "subject": "Laptop not charging",
        "description": "The business laptop is not charging after the docking station update.",
    }
    payload.update(overrides)
    response = client.post("/api/v1/requests", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_request_success(client):
    body = create_request(client)
    assert body["requester_id"] == 1
    assert body["subject"] == "Laptop not charging"
    assert body["request_number"].startswith("REQ-")
    assert body["status"] == "New"


def test_list_requests_for_assignee(client):
    create_request(client, assigned_agent_id=2)
    response = client.get("/api/v1/requests?assignee_id=2")
    assert response.status_code == 200, response.text
    assert response.json()["total"] >= 1


def test_assign_request_success(client):
    created = create_request(client)
    response = client.post(f"/api/v1/requests/{created['id']}/assign", json={"assignee_id": 2, "reason": "Route to IT support"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assigned_agent_id"] == 2
    assert body["status"] == "Assigned"


def test_reassign_request_records_history(client):
    created = create_request(client, assigned_agent_id=2)
    response = client.post(f"/api/v1/requests/{created['id']}/assign", json={"assignee_id": 3, "reason": "Escalating to specialist"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["assigned_agent_id"] == 3


def test_invalid_assignee_rejected(client):
    created = create_request(client)
    response = client.post(f"/api/v1/requests/{created['id']}/assign", json={"assignee_id": 999, "reason": "bad user"})
    assert response.status_code == 400, response.text


def test_status_transition_allowed_and_invalid(client):
    created = create_request(client, assigned_agent_id=2)
    ok = client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "In Progress", "reason": "Starting diagnosis"})
    assert ok.status_code == 200, ok.text
    bad = client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "Resolved", "reason": "Bad transition"})
    assert bad.status_code == 400, bad.text


def test_status_requires_assignment_before_work_starts(client):
    created = create_request(client)
    response = client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "In Progress", "reason": "Work begins"})
    assert response.status_code == 400, response.text
    assert "assigned" in response.json()["detail"].lower()


def test_direct_closure_is_rejected_until_resolved(client):
    created = create_request(client, assigned_agent_id=2)
    response = client.post(f"/api/v1/requests/{created['id']}/status", json={"status": "Closed", "reason": "Done"})
    assert response.status_code == 400, response.text
    assert "resolved" in response.json()["detail"].lower()


def test_resolve_without_details_is_rejected(client):
    created = create_request(client, assigned_agent_id=2)
    response = client.post(f"/api/v1/requests/{created['id']}/resolve", json={"resolution_details": "   " , "resolved_by": 2})
    assert response.status_code == 422, response.text


def test_close_unresolved_request_is_rejected(client):
    created = create_request(client, assigned_agent_id=2)
    response = client.post(f"/api/v1/requests/{created['id']}/close", json={"closed_by": 2, "reason": "close"})
    assert response.status_code == 400, response.text
    assert "resolved" in response.json()["detail"].lower()


def test_successful_resolution_and_closure(client):
    created = create_request(client, assigned_agent_id=2)
    response = client.post(f"/api/v1/requests/{created['id']}/resolve", json={"resolution_details": "Replaced the battery and verified charging works.", "resolved_by": 2})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "Resolved"
    assert body["resolution_details"] == "Replaced the battery and verified charging works."

    close_response = client.post(f"/api/v1/requests/{created['id']}/close", json={"closed_by": 2, "reason": "Ticket completed"})
    assert close_response.status_code == 200, close_response.text
    closed = close_response.json()
    assert closed["status"] == "Closed"
    assert closed["closed_at"] is not None


def test_attempt_to_modify_closed_request_is_rejected(client):
    created = create_request(client, assigned_agent_id=2)
    client.post(f"/api/v1/requests/{created['id']}/resolve", json={"resolution_details": "Fixed the issue and validated the repair.", "resolved_by": 2})
    client.post(f"/api/v1/requests/{created['id']}/close", json={"closed_by": 2, "reason": "Request closed"})

    patch_response = client.patch(f"/api/v1/requests/{created['id']}", json={"subject": "Attempted modification after closure"})
    assert patch_response.status_code == 400, patch_response.text
    assert "closed" in patch_response.json()["detail"].lower()


def test_reports_unassigned_and_agents(client):
    create_request(client, assigned_agent_id=None)
    agents = client.get("/api/v1/users/agents")
    unassigned = client.get("/api/v1/reports/unassigned")
    assert agents.status_code == 200, agents.text
    assert unassigned.status_code == 200, unassigned.text
    assert unassigned.json()["total"] >= 1


def test_requests_can_be_filtered_by_same_day_date_range(client):
    created = create_request(client)
    request_date = datetime.fromisoformat(created["created_at"].replace("Z", "+00:00")).astimezone(timezone.utc)
    date_only = request_date.strftime("%Y-%m-%d")

    response = client.get("/api/v1/requests", params={"start_date": date_only, "end_date": date_only})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 1


def test_users_metadata_endpoint_works(client):
    response = client.get("/api/v1/users")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total"] >= 1
    assert any(item["role"] in {"IT_AGENT", "ADMIN", "EMPLOYEE"} for item in body["items"])
