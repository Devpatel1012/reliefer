
import models
import schemas
from database import get_db
from dependencies import get_current_user
from encryption import decrypt_string
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from limiter import limiter
from resume_ai import (
    build_prompt,
    call_huggingface,
    extract_keywords,
    fetch_job_description_from_url,
    render_pdf,
)
from resume_formatter import format_resume
from resume_parser import extract_text, parse_resume_text_to_json
from scraper import scrape_github_profile, scrape_linkedin_profile
from sqlalchemy.orm import Session

router = APIRouter(tags=["Resume"])



def _resolve_job_description(job_description: str | None, job_url: str | None) -> str:
    if job_description and job_description.strip():
        return job_description.strip()
    if job_url and job_url.strip():
        return fetch_job_description_from_url(job_url.strip())
    raise HTTPException(status_code=400, detail="Provide either job_description or job_url")


@router.post("/resume/analyze-jd", response_model=schemas.JDAnalyzeResponse)
def analyze_job_description(
    payload: schemas.JDAnalyzeRequest,
    current_user: models.User = Depends(get_current_user),
):
    jd_text = _resolve_job_description(payload.job_description, payload.job_url)
    keywords = extract_keywords(jd_text)
    return {"keywords": keywords, "job_description_used": jd_text}


@router.post(
    "/resume/generate",
    response_model=schemas.GeneratedResumeResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("3/minute")
def generate_resume(
    request: Request,
    payload: schemas.ResumeGenerateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not current_user.huggingface_api_key:
        raise HTTPException(
            status_code=400,
            detail="No Hugging Face API key on file. Set one via PUT /me/huggingface-key first.",
        )

    jd_text = _resolve_job_description(payload.job_description, payload.job_url)
    keywords = extract_keywords(jd_text)

    template = None
    if payload.template_id:
        template = (
            db.query(models.ResumeTemplate)
            .filter(
                models.ResumeTemplate.id == payload.template_id,
                models.ResumeTemplate.user_id == current_user.id,
            )
            .first()
        )
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
    else:
        template = (
            db.query(models.ResumeTemplate)
            .filter(
                models.ResumeTemplate.user_id == current_user.id,
                models.ResumeTemplate.is_default.is_(True),
            )
            .first()
        )

    prompt = build_prompt(
        user=current_user,
        job_description=jd_text,
        keywords=keywords,
        template_content=template.content if template else None,
    )

    hf_key = decrypt_string(current_user.huggingface_api_key)
    generated_content = call_huggingface(
        api_key=hf_key,
        prompt=prompt,
        model=payload.model,
    )

    latest = (
        db.query(models.GeneratedResume)
        .filter(models.GeneratedResume.user_id == current_user.id)
        .order_by(models.GeneratedResume.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    db_resume = models.GeneratedResume(
        user_id=current_user.id,
        template_id=template.id if template else None,
        job_title=payload.job_title,
        job_description=jd_text,
        extracted_keywords=", ".join(keywords),
        content=generated_content,
        version=next_version,
    )
    db.add(db_resume)
    db.commit()
    db.refresh(db_resume)
    return db_resume


@router.get("/resume/history", response_model=list[schemas.GeneratedResumeResponse])
def resume_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.GeneratedResume)
        .filter(models.GeneratedResume.user_id == current_user.id)
        .order_by(models.GeneratedResume.created_at.desc())
        .all()
    )


def _get_owned_resume(resume_id: int, db: Session, current_user: models.User) -> models.GeneratedResume:
    resume = (
        db.query(models.GeneratedResume)
        .filter(
            models.GeneratedResume.id == resume_id,
            models.GeneratedResume.user_id == current_user.id,
        )
        .first()
    )
    if not resume:
        raise HTTPException(status_code=404, detail="Generated resume not found")
    return resume


@router.get("/resume/{resume_id}", response_model=schemas.GeneratedResumeResponse)
def get_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return _get_owned_resume(resume_id, db, current_user)


@router.delete("/resume/{resume_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    resume = _get_owned_resume(resume_id, db, current_user)
    db.delete(resume)
    db.commit()


@router.get("/resume/{resume_id}/export-pdf")
def export_resume_pdf(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    resume = _get_owned_resume(resume_id, db, current_user)
    formatted_content = format_resume(resume.content)
    pdf_bytes = render_pdf(title=f"{current_user.name} - Resume", content=formatted_content)
    filename = f"resume_v{resume.version}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/resume/{resume_id}/export-txt")
def export_resume_txt(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    resume = _get_owned_resume(resume_id, db, current_user)
    formatted_content = format_resume(resume.content)
    filename = f"resume_v{resume.version}.txt"
    return Response(
        content=formatted_content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/resume/{resume_id}/export-md")
def export_resume_md(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    resume = _get_owned_resume(resume_id, db, current_user)
    formatted_content = format_resume(resume.content)
    filename = f"resume_v{resume.version}.md"
    return Response(
        content=formatted_content,
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/resume/{resume_id}/share", response_model=schemas.ResumeShareResponse)
def share_resume(
    resume_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    import secrets
    resume = _get_owned_resume(resume_id, db, current_user)
    if not resume.share_token:
        resume.share_token = secrets.token_urlsafe(16)
        db.commit()
        db.refresh(resume)
    
    return {
        "share_token": resume.share_token,
        "share_url": f"/resume/public/{resume.share_token}"
    }


@router.get("/resume/public/{share_token}", response_model=schemas.GeneratedResumeResponse)
def get_public_resume(
    share_token: str,
    db: Session = Depends(get_db),
):
    resume = db.query(models.GeneratedResume).filter(models.GeneratedResume.share_token == share_token).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Shared resume not found or link expired")
    return resume


@router.post("/resume/{resume_id}/feedback", response_model=schemas.GeneratedResumeResponse)
def submit_resume_feedback(
    resume_id: int,
    payload: schemas.ResumeFeedbackRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    resume = _get_owned_resume(resume_id, db, current_user)
    resume.rating = payload.rating
    resume.feedback_text = payload.feedback_text
    db.commit()
    db.refresh(resume)
    return resume


@router.get("/dashboard/summary", response_model=schemas.DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return {
        "name": current_user.name,
        "profession": current_user.profession,
        "interest": current_user.interest,
        "email": current_user.email,
        "total_skills": len(current_user.skills),
        "total_projects": len(current_user.projects),
        "total_achievements": len(current_user.achievements),
        "total_education": len(current_user.education),
        "total_experience": len(current_user.experience),
        "total_resumes_generated": len(current_user.resumes),
        "has_huggingface_key": bool(current_user.huggingface_api_key),
    }


# ─── Resume Parsing & Bulk Import Endpoints ───────────────────

@router.post("/resume/upload", response_model=schemas.ParsedResumeResponse)
async def upload_and_parse_resume(
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    
    text = extract_text(content, file.filename)
    if not text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract text from file. Please ensure it is a valid PDF, DOCX, or text file.",
        )
    
    parsed_data = parse_resume_text_to_json(text)
    return parsed_data


@router.post("/resume/parse-text", response_model=schemas.ParsedResumeResponse)
def parse_resume_pasted_text(
    payload: schemas.ResumeParseTextRequest,
    current_user: models.User = Depends(get_current_user),
):
    parsed_data = parse_resume_text_to_json(payload.text)
    return parsed_data


@router.post("/resume/import-parsed")
def import_parsed_resume(
    payload: schemas.ParsedResumeImportRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    imported_skills = 0
    imported_exp = 0
    imported_edu = 0
    imported_proj = 0
    imported_achievements = 0

    # 1. Skills
    existing_skills = {s.name.lower() for s in current_user.skills}
    if payload.skills:
        for skill_name in payload.skills:
            clean_name = skill_name.strip()
            if clean_name and clean_name.lower() not in existing_skills:
                db_skill = models.Skill(
                    user_id=current_user.id,
                    name=clean_name,
                    category="Technical",
                    proficiency="Intermediate"
                )
                db.add(db_skill)
                existing_skills.add(clean_name.lower())
                imported_skills += 1

    # 2. Work Experience
    if payload.experience:
        for exp in payload.experience:
            company = exp.get("company", "Company").strip()
            role = exp.get("role", "Software Engineer").strip()
            if company and role:
                db_exp = models.Experience(
                    user_id=current_user.id,
                    company=company,
                    role=role,
                    description=exp.get("description", "").strip(),
                    start_date=exp.get("dates", exp.get("start_date", "")).strip(),
                    end_date=exp.get("end_date", "").strip(),
                    is_current=False
                )
                db.add(db_exp)
                imported_exp += 1

    # 3. Education
    if payload.education:
        for edu in payload.education:
            inst = edu.get("institution", "University").strip()
            degree = edu.get("degree", "Degree").strip()
            if inst or degree:
                db_edu = models.Education(
                    user_id=current_user.id,
                    institution=inst or "University",
                    degree=degree or "Degree",
                    start_year="",
                    end_year=str(edu.get("year", edu.get("end_year", ""))).strip(),
                    gpa=str(edu.get("marks", edu.get("gpa", ""))).strip()
                )
                db.add(db_edu)
                imported_edu += 1

    # 4. Projects
    if payload.projects:
        for proj in payload.projects:
            title = proj.get("title", proj.get("name", "Project")).strip()
            if title:
                db_proj = models.Project(
                    user_id=current_user.id,
                    title=title,
                    description=proj.get("description", "").strip(),
                    technologies=proj.get("tech_stack", proj.get("technologies", "")).strip()
                )
                db.add(db_proj)
                imported_proj += 1

    # 5. Achievements
    if payload.achievements:
        for ach in payload.achievements:
            title = ach.get("title", "Achievement").strip()
            if title:
                db_ach = models.Achievement(
                    user_id=current_user.id,
                    title=title,
                    description=ach.get("description", "").strip(),
                    date=ach.get("date", "").strip()
                )
                db.add(db_ach)
                imported_achievements += 1

    # 6. Uncategorized / Other Info as Achievements
    if payload.other_info:
        for item in payload.other_info:
            item_clean = item.strip()
            if item_clean:
                db_ach = models.Achievement(
                    user_id=current_user.id,
                    title=item_clean[:100],
                    description=item_clean,
                    date=""
                )
                db.add(db_ach)
                imported_achievements += 1

    db.commit()
    
    return {
        "message": "Resume data imported into Master Profile successfully!",
        "imported_counts": {
            "skills": imported_skills,
            "experience": imported_exp,
            "education": imported_edu,
            "projects": imported_proj,
            "achievements": imported_achievements
        }
    }


# ─── GitHub & LinkedIn Scraping Endpoints ─────────────────────

@router.post("/import/github")
def import_github_profile(
    payload: schemas.GitHubImportRequest,
    current_user: models.User = Depends(get_current_user),
):
    try:
        data = scrape_github_profile(payload.github_username)
        return data
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scrape GitHub profile: {e!s}")


@router.post("/import/linkedin")
def import_linkedin_profile(
    payload: schemas.LinkedInImportRequest,
    current_user: models.User = Depends(get_current_user),
):
    data = scrape_linkedin_profile(payload.linkedin_url)
    return data


