import io
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from fastapi.testclient import TestClient
from limiter import limiter
from main import app

client = TestClient(app)

SAMPLE_RESUME_TEXT = """
Jane Doe
Software Engineer | San Francisco, CA

EXPERIENCE
Tech Corp | Senior Software Engineer | 2021 - Present
- Built scalable FastAPI microservices with PostgreSQL and Docker.
- Improved system throughput by 45%.

Data Solutions | Software Engineer | 2019 - 2021
- Developed React frontends and Python APIs.

EDUCATION
University of California | B.S. Computer Science | 2019

SKILLS
Python, JavaScript, React, FastAPI, PostgreSQL, Docker, AWS, Git

PROJECTS
E-Commerce Platform
- Built full stack online store using React and Python.
- Tech stack: React, Python, SQLite
"""

def test_resume_parser_pure_text():
    from resume_parser import parse_resume_text_to_json
    parsed = parse_resume_text_to_json(SAMPLE_RESUME_TEXT)
    assert len(parsed["skills"]) > 0
    assert "Python" in parsed["skills"]
    assert "FastAPI" in parsed["skills"]
    assert len(parsed["experience"]) >= 1
    assert len(parsed["education"]) >= 1

def test_resume_upload_and_import_flow():
    import uuid
    limiter.reset()
    unique_id = uuid.uuid4().hex[:6]
    email = f"resume_user_{unique_id}@example.com"
    password = "Password123!"

    # Signup & Login
    signup_resp = client.post("/signup", json={
        "name": "Resume User",
        "age": 28,
        "interest": "AI",
        "profession": "Engineer",
        "email": email,
        "password": password
    })
    assert signup_resp.status_code == 201

    login_resp = client.post("/login", json={"email": email, "password": password})
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Test parse-text endpoint
    res = client.post("/resume/parse-text", json={"text": SAMPLE_RESUME_TEXT}, headers=headers)
    assert res.status_code == 200
    parsed_data = res.json()
    assert "skills" in parsed_data
    assert "Python" in parsed_data["skills"]

    # 2. Test import-parsed endpoint
    import_res = client.post("/resume/import-parsed", json=parsed_data, headers=headers)
    assert import_res.status_code == 200
    import_json = import_res.json()
    assert import_json["imported_counts"]["skills"] > 0
    assert import_json["imported_counts"]["experience"] > 0

    # 3. Verify user's profile got populated
    summary_res = client.get("/dashboard/summary", headers=headers)
    assert summary_res.status_code == 200
    summary = summary_res.json()
    assert summary["total_skills"] > 0
    assert summary["total_experience"] > 0

def test_resume_file_upload_txt():
    import uuid
    limiter.reset()
    unique_id = uuid.uuid4().hex[:6]
    email = f"resume_file_user_{unique_id}@example.com"
    password = "Password123!"

    client.post("/signup", json={
        "name": "File User",
        "age": 25,
        "interest": "Tech",
        "profession": "Dev",
        "email": email,
        "password": password
    })

    login_resp = client.post("/login", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    file_bytes = SAMPLE_RESUME_TEXT.encode("utf-8")
    files = {"file": ("my_resume.txt", io.BytesIO(file_bytes), "text/plain")}

    res = client.post("/resume/upload", files=files, headers=headers)
    assert res.status_code == 200
    parsed = res.json()
    assert len(parsed["skills"]) > 0

