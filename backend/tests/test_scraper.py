import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

import pytest
from fastapi.testclient import TestClient
from main import app
from limiter import limiter
from scraper import scrape_github_profile, scrape_linkedin_profile

client = TestClient(app)


def _make_readme_mock(content: str = "") -> MagicMock:
    """Helper: returns a mock README API response."""
    import base64
    m = MagicMock()
    if content:
        m.status_code = 200
        encoded = base64.b64encode(content.encode()).decode()
        m.json.return_value = {"content": encoded, "encoding": "base64"}
    else:
        m.status_code = 404
        m.json.return_value = {}
    return m


def test_github_scraper_mocked():
    mock_user_res = {
        "name": "Octocat",
        "bio": "Open Source Maintainer",
        "company": "GitHub",
        "location": "San Francisco",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif"
    }

    mock_repos_res = [
        {
            "name": "Hello-World",
            "description": "My first repository on GitHub!",
            "language": "Python",
            "html_url": "https://github.com/octocat/Hello-World",
            "stargazers_count": 120,
            "forks_count": 5,
            "created_at": "2021-01-01T00:00:00Z",
            "fork": False,
            "archived": False,
        },
        {
            "name": "Spoon-Knife",
            "description": "This repo is for practicing.",
            "language": "TypeScript",
            "html_url": "https://github.com/octocat/Spoon-Knife",
            "stargazers_count": 45,
            "forks_count": 2,
            "created_at": "2022-03-15T00:00:00Z",
            "fork": False,
            "archived": False,
        }
    ]

    readme_hw = "Hello World is a Python project that demonstrates basic GitHub usage with automated CI/CD pipelines and unit tests."
    readme_sk = ""  # Spoon-Knife has no README

    call_sequence = [
        # 1st: user profile
        _build_mock(200, mock_user_res),
        # 2nd: repos list
        _build_mock(200, mock_repos_res),
        # 3rd: README for Hello-World
        _make_readme_mock(readme_hw),
        # 4th: README for Spoon-Knife (404)
        _make_readme_mock(readme_sk),
    ]

    with patch("requests.get", side_effect=call_sequence):
        data = scrape_github_profile("octocat")
        assert "skills" in data
        assert "Python" in data["skills"]
        assert "TypeScript" in data["skills"]
        assert len(data["projects"]) == 2
        # Hello-World has more stars → higher score → should be first
        titles = [p["title"] for p in data["projects"]]
        assert "Hello-World" in titles
        assert "Spoon-Knife" in titles
        assert data["profile_info"]["name"] == "Octocat"
        # README content should appear in description of Hello-World
        hw_proj = next(p for p in data["projects"] if p["title"] == "Hello-World")
        assert len(hw_proj["description"]) > 20


def _build_mock(status: int, json_data) -> MagicMock:
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_data
    return m


def test_github_endpoint_flow():
    import uuid
    limiter.reset()
    email = f"github_user_{uuid.uuid4().hex[:6]}@example.com"
    password = "Password123!"

    client.post("/signup", json={
        "name": "GitHub Scraper Test",
        "age": 25,
        "interest": "Open Source",
        "profession": "Dev",
        "email": email,
        "password": password
    })

    login_resp = client.post("/login", json={"email": email, "password": password})
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    mock_user_res = {
        "name": "Test Dev",
        "bio": "Full Stack Engineer",
        "company": "Tech Corp"
    }
    mock_repos_res = [
        {
            "name": "fastapi-reliefer",
            "description": "AI resume tailor app",
            "language": "Python",
            "html_url": "https://github.com/testdev/fastapi-reliefer",
            "stargazers_count": 10,
            "forks_count": 1,
            "created_at": "2024-01-01T00:00:00Z",
            "fork": False,
            "archived": False,
        }
    ]

    readme_content = "fastapi-reliefer is an AI-powered resume tailoring platform built with FastAPI, Python, and HuggingFace."

    call_sequence = [
        _build_mock(200, mock_user_res),
        _build_mock(200, mock_repos_res),
        _make_readme_mock(readme_content),
    ]

    with patch("requests.get", side_effect=call_sequence):
        res = client.post("/import/github", json={"github_username": "testdev"}, headers=headers)
        assert res.status_code == 200
        data = res.json()
        assert "projects" in data
        assert data["projects"][0]["title"] == "fastapi-reliefer"
        # README-sourced description should be rich
        assert len(data["projects"][0]["description"]) > 20


def test_linkedin_scraper_fallback():
    with patch("requests.get") as mock_get:
        mock_resp = MagicMock()
        mock_resp.status_code = 999  # Anti-bot response
        mock_get.return_value = mock_resp

        data = scrape_linkedin_profile("https://www.linkedin.com/in/test-profile")
        assert "warning" in data
        assert "LinkedIn restricts direct web scraping" in data["warning"]
