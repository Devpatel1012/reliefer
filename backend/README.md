# Reliefer Backend

FastAPI backend for the Reliefer mini project. This replaces/extends the
original `main.py` + `schemas.py` + `models.py` + `database.py` you already
had, adding full profile management, job-description analysis, AI resume
generation via the Hugging Face Inference API, PDF export, and version
history — matching the feature list in the project proposal.

## 1. Setup

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env: set DATABASE_URL to your real Postgres creds, and JWT_SECRET_KEY
# to a long random string (e.g. `python -c "import secrets; print(secrets.token_hex(32))"`)
```

Make sure PostgreSQL is running and the database in `DATABASE_URL` exists
(create it with `createdb reliefer_db` or via psql/pgAdmin).

## 2. Run

```bash
uvicorn main:app --reload
```

Interactive API docs: http://127.0.0.1:8000/docs

Tables are created automatically on startup (`Base.metadata.create_all`).
Since the schema changed (new tables + `created_at` column on `users`), if
you already had a `users` table from the old version, either drop your dev
database and let it recreate, or add the new tables/columns manually —
there's no Alembic migration set up yet (see "Next steps" below).

## 3. Where things live

```
reliefer-backend/
├── main.py              # app assembly, CORS, routers, static frontend mount
├── database.py           # SQLAlchemy engine/session, reads DATABASE_URL from .env
├── models.py             # all tables: User, Skill, Project, Achievement,
│                          #   Education, Experience, ResumeTemplate, GeneratedResume
├── schemas.py             # Pydantic request/response models
├── security.py            # password hashing + JWT create/decode
├── dependencies.py        # get_current_user (JWT bearer auth dependency)
├── resume_ai.py           # JD fetch/keyword extraction, prompt building,
│                          #   Hugging Face API call, PDF rendering
└── routers/
    ├── auth_router.py       # /signup, /login, /me, /me/huggingface-key
    ├── skills_router.py     # /skills
    ├── projects_router.py   # /projects
    ├── achievements_router.py # /achievements
    ├── education_router.py  # /education
    ├── experience_router.py # /experience
    ├── templates_router.py  # /templates  (resume layout templates)
    └── resume_router.py     # /resume/analyze-jd, /resume/generate,
                              #   /resume/history, /resume/{id}, PDF export,
                              #   /dashboard
```

## 4. Auth flow (what changed from your original code)

Your original `/login` just returned the user's info with no token, so
there was no way to prove identity on later requests. It now returns an
`access_token` (JWT) in addition to the same fields the dashboard already
reads from `localStorage`, so `script.js` keeps working unmodified. Every
new endpoint (skills, projects, resume generation, etc.) requires that
token as a `Bearer` header:

```
Authorization: Bearer <access_token>
```

When you build the profile/resume UI later, store `access_token` from the
login response (e.g. alongside `reliefer_user` in localStorage) and attach
it to every `fetch()` call to the new endpoints.

## 5. Typical flow for the AI resume feature

1. User fills in profile data: `POST /skills`, `POST /projects`,
   `POST /education`, `POST /experience`, `POST /achievements`.
2. User sets their own Hugging Face key: `PUT /me/huggingface-key`.
3. (Optional) user saves a resume layout: `POST /templates`.
4. User pastes a JD or URL: `POST /resume/analyze-jd` to preview extracted
   keywords, then `POST /resume/generate` to actually produce tailored
   content — this calls the Hugging Face Inference API with the user's key
   and the candidate's real profile data, and stores the result as a new
   version.
5. `GET /resume/history` / `GET /resume/{id}` for version history,
   `GET /resume/{id}/export-pdf` to download a PDF.

`GET /dashboard` returns the summary counts (skills/projects/etc. and
whether an HF key is on file) if you want a quick dashboard-stats card.

## 6. Next steps / things intentionally left simple for a prototype

- No Alembic migrations — schema changes currently mean recreating the dev DB.
- Keyword extraction in `resume_ai.py` is a lightweight stopword/frequency
  approach, not real NLP — good enough to demo, swap for spaCy/KeyBERT later.
- `huggingface_api_key` is stored in plaintext; encrypt at rest before any
  real deployment.
- CORS is wide open (`allow_origins=["*"]`) for local dev — restrict it once
  you have a real frontend origin.
- PDF export uses a very simple `reportlab` text layout; swap in a styled
  HTML → PDF renderer (e.g. WeasyPrint) once the resume template UI exists.
