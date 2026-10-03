import os
from pathlib import Path

import models
from database import engine
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from limiter import limiter
from logging_config import RequestLoggingMiddleware, setup_logging
from routers import (
    achievements_router,
    auth_router,
    education_router,
    experience_router,
    projects_router,
    resume_router,
    skills_router,
    templates_router,
)
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

load_dotenv()

# Initialize structured logging
log_level = os.getenv("LOG_LEVEL", "INFO")
json_format = os.getenv("LOG_FORMAT", "text").lower() == "json"
setup_logging(log_level=log_level, json_format=json_format)

# Resolve the frontend directory relative to this file (device independent).
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "Frontend" / "User_Signup"

# Create the database tables
models.Base.metadata.create_all(bind=engine)

raw_origins = os.getenv("ALLOWED_ORIGINS", "*")
allowed_origins = [o.strip() for o in raw_origins.split(",") if o.strip()]

app = FastAPI(title="Reliefer API", version="0.2.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if "*" not in allowed_origins else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)


@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "Reliefer API", "version": "0.2.0"}


# ─── Routers ────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(skills_router.router)
app.include_router(projects_router.router)
app.include_router(achievements_router.router)
app.include_router(education_router.router)
app.include_router(experience_router.router)
app.include_router(templates_router.router)
app.include_router(resume_router.router)


# ─── Frontend (unchanged, served as-is) ────────────────────
@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse(str(FRONTEND_DIR / "index.html"))


@app.get("/dashboard", include_in_schema=False)
def serve_dashboard():
    return FileResponse(str(FRONTEND_DIR / "dashboard.html"))


if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="static")
