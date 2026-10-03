import sys
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_requirements_and_env_example():
    req_path = backend_dir / "requirements.txt"
    req_text = req_path.read_text()
    assert "cryptography" in req_text
    assert "slowapi" in req_text

    env_path = backend_dir / ".env.example"
    env_text = env_path.read_text()
    assert "Fernet.generate_key()" in env_text


def test_rate_limiting_login():
    # Make multiple requests to /login to trigger 429
    responses = []
    for i in range(10):
        resp = client.post("/login", json={"email": f"fake_{i}@example.com", "password": "wrongpassword"})
        responses.append(resp.status_code)
    
    # At least one request after limit of 5 should return 429
    assert 429 in responses


def test_pydantic_v2_schemas():
    import schemas

    # Test UserResponse ConfigDict from_attributes
    class MockUser:
        id = 1
        name = "Test"
        age = 25
        interest = "AI"
        profession = "Dev"
        email = "test@example.com"
        is_active = True
        huggingface_api_key = "hf_12345"

    user_resp = schemas.UserResponse.model_validate(MockUser())
    assert user_resp.id == 1
    dumped = user_resp.model_dump(mode="json")
    assert dumped["huggingface_api_key"] == "***configured***"
