import sys
import uuid
from pathlib import Path
from unittest.mock import patch

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


@patch("routers.resume_router.call_huggingface")
def test_phase7_exports_share_and_feedback(mock_hf):
    from limiter import limiter
    limiter.reset()

    mock_hf.return_value = "# Jane Doe\nSoftware Engineer resume content"

    email = f"phase7_{uuid.uuid4().hex[:8]}@example.com"
    password = "securePassword123"

    # 1. Signup & Login
    client.post("/signup", json={
        "name": "Phase7 User",
        "age": 29,
        "interest": "DevOps",
        "profession": "Cloud Architect",
        "email": email,
        "password": password
    })
    login_resp = client.post("/login", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Set HF key
    client.put("/me/huggingface-key", json={"huggingface_api_key": "hf_test_key_phase7"}, headers=headers)

    # Generate Resume
    gen_resp = client.post("/resume/generate", json={
        "job_title": "Cloud Architect",
        "job_description": "Seeking AWS Cloud Architect with Kubernetes skills"
    }, headers=headers)
    assert gen_resp.status_code == 201
    resume_id = gen_resp.json()["id"]

    # 2. Test TXT and MD export endpoints
    txt_resp = client.get(f"/resume/{resume_id}/export-txt", headers=headers)
    assert txt_resp.status_code == 200
    assert "Jane Doe" in txt_resp.text
    assert "text/plain" in txt_resp.headers["content-type"]

    md_resp = client.get(f"/resume/{resume_id}/export-md", headers=headers)
    assert md_resp.status_code == 200
    assert "Jane Doe" in md_resp.text
    assert "text/markdown" in md_resp.headers["content-type"]

    # 3. Test Share Link Generation & Public Access
    share_resp = client.post(f"/resume/{resume_id}/share", headers=headers)
    assert share_resp.status_code == 200
    share_data = share_resp.json()
    assert "share_token" in share_data
    token_str = share_data["share_token"]

    # Public unauthenticated GET
    public_resp = client.get(f"/resume/public/{token_str}")
    assert public_resp.status_code == 200
    assert public_resp.json()["id"] == resume_id

    # 4. Test Resume Rating & Feedback
    fb_resp = client.post(f"/resume/{resume_id}/feedback", json={
        "rating": 5,
        "feedback_text": "Great resume output! Matched keywords accurately."
    }, headers=headers)
    assert fb_resp.status_code == 200
    assert fb_resp.json()["rating"] == 5
