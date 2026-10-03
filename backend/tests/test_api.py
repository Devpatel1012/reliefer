import os
import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


def test_auth_and_user_profile():
    email = "test_pytest_user@example.com"
    password = "securePassword123"

    # Signup
    signup_resp = client.post("/signup", json={
        "name": "Pytest User",
        "age": 26,
        "interest": "Machine Learning",
        "profession": "AI Engineer",
        "email": email,
        "password": password
    })
    if signup_resp.status_code == 400:
        assert "already registered" in signup_resp.text
    else:
        assert signup_resp.status_code == 201

    # Login
    login_resp = client.post("/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Get /me
    me_resp = client.get("/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == email

    # Update profile /me
    update_resp = client.put("/me", json={"profession": "Senior AI Architect"}, headers=headers)
    assert update_resp.status_code == 200
    assert update_resp.json()["profession"] == "Senior AI Architect"

    # Set Hugging Face Key (Encrypted at rest)
    hf_resp = client.put("/me/huggingface-key", json={"huggingface_api_key": "hf_test_secret_key_abcdef"}, headers=headers)
    assert hf_resp.status_code == 200
    assert hf_resp.json()["huggingface_api_key"] is not None


def test_master_profile_crud():
    email = "test_pytest_user@example.com"
    password = "securePassword123"
    login_resp = client.post("/login", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Skills CRUD
    skill_resp = client.post("/skills/", json={"name": "Pytest", "category": "Testing", "proficiency": "Expert"}, headers=headers)
    assert skill_resp.status_code == 201
    skill_id = skill_resp.json()["id"]

    get_skills = client.get("/skills/", headers=headers)
    assert get_skills.status_code == 200
    assert any(s["id"] == skill_id for s in get_skills.json())

    del_skill = client.delete(f"/skills/{skill_id}", headers=headers)
    assert del_skill.status_code == 204

    # Projects CRUD
    proj_resp = client.post("/projects/", json={"title": "Test Suite", "technologies": "Pytest"}, headers=headers)
    assert proj_resp.status_code == 201

    # Summary API
    summary_resp = client.get("/dashboard/summary", headers=headers)
    assert summary_resp.status_code == 200
    assert summary_resp.json()["total_projects"] >= 1
