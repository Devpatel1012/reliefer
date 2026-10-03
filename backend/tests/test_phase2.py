import os
import sys
from pathlib import Path
from unittest.mock import patch

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_encryption_roundtrip():
    from encryption import decrypt_string, encrypt_string

    secret = "hf_my_super_secret_token_12345"
    encrypted = encrypt_string(secret)
    assert encrypted != secret
    assert encrypted is not None

    decrypted = decrypt_string(encrypted)
    assert decrypted == secret


def test_request_id_logging_header():
    response = client.get("/health")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


@patch("routers.resume_router.call_huggingface")
def test_resume_generation_mocked(mock_hf):
    from limiter import limiter
    limiter.reset()

    mock_hf.return_value = "## Professional Summary\nExperienced Software Engineer specialized in AI and Python."

    import uuid
    email = f"phase2_{uuid.uuid4().hex[:8]}@example.com"
    password = "securePassword123"

    # Signup & Login
    client.post("/signup", json={
        "name": "Phase2 Tester",
        "age": 28,
        "interest": "AI Engineering",
        "profession": "Software Engineer",
        "email": email,
        "password": password
    })
    login_resp = client.post("/login", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Set HF key
    client.put("/me/huggingface-key", json={"huggingface_api_key": "hf_test_token"}, headers=headers)

    # Generate resume
    gen_resp = client.post("/resume/generate", json={
        "job_title": "Senior AI Developer",
        "job_description": "We are seeking a Python developer with FastAPI and Pytest experience."
    }, headers=headers)

    assert gen_resp.status_code == 201
    data = gen_resp.json()
    assert data["job_title"] == "Senior AI Developer"
    assert "Experienced Software Engineer" in data["content"]
    assert data["version"] == 1


def test_alembic_setup_exists():
    alembic_ini = backend_dir / "alembic.ini"
    alembic_env = backend_dir / "alembic" / "env.py"
    assert alembic_ini.exists()
    assert alembic_env.exists()
