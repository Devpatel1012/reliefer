from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_serializer, field_validator


# ─── Auth / User ───────────────────────────────────────────

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=16, le=120)
    interest: str = Field(..., min_length=2, max_length=100)
    profession: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    age: Optional[int] = Field(None, ge=16, le=120)
    interest: Optional[str] = Field(None, min_length=2, max_length=100)
    profession: Optional[str] = Field(None, min_length=2, max_length=100)


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    age: int
    interest: str
    profession: str
    email: EmailStr
    is_active: bool
    huggingface_api_key: Optional[str] = None

    @field_serializer("huggingface_api_key")
    def serialize_api_key(self, v: Optional[str], _info) -> Optional[str]:
        if v and str(v).strip():
            return "***configured***"
        return None

    model_config = ConfigDict(from_attributes=True)


class LoginResponse(BaseModel):
    message: str
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str
    email: EmailStr
    profession: str
    interest: str
    age: int


class ApiKeyUpdate(BaseModel):
    huggingface_api_key: str = Field(..., min_length=5, max_length=256)



# ─── Skills ─────────────────────────────────────────────────

class SkillBase(BaseModel):
    name: str
    category: Optional[str] = None
    proficiency: Optional[str] = None


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    proficiency: Optional[str] = None


class SkillResponse(SkillBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ─── Projects ───────────────────────────────────────────────

class ProjectBase(BaseModel):
    title: str
    description: Optional[str] = None
    technologies: Optional[str] = None
    link: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    technologies: Optional[str] = None
    link: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ProjectResponse(ProjectBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ─── Achievements ───────────────────────────────────────────

class AchievementBase(BaseModel):
    title: str
    description: Optional[str] = None
    date: Optional[str] = None


class AchievementCreate(AchievementBase):
    pass


class AchievementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None


class AchievementResponse(AchievementBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ─── Education ──────────────────────────────────────────────

class EducationBase(BaseModel):
    institution: str
    degree: str
    field_of_study: Optional[str] = None
    start_year: Optional[str] = None
    end_year: Optional[str] = None
    gpa: Optional[str] = None


class EducationCreate(EducationBase):
    pass


class EducationUpdate(BaseModel):
    institution: Optional[str] = None
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[str] = None
    end_year: Optional[str] = None
    gpa: Optional[str] = None


class EducationResponse(EducationBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ─── Experience ─────────────────────────────────────────────

class ExperienceBase(BaseModel):
    company: str
    role: str
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False


class ExperienceCreate(ExperienceBase):
    pass


class ExperienceUpdate(BaseModel):
    company: Optional[str] = None
    role: Optional[str] = None
    description: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = None


class ExperienceResponse(ExperienceBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ─── Resume Templates ───────────────────────────────────────

class ResumeTemplateBase(BaseModel):
    name: str
    content: str
    is_default: bool = False


class ResumeTemplateCreate(ResumeTemplateBase):
    pass


class ResumeTemplateUpdate(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    is_default: Optional[bool] = None


class ResumeTemplateResponse(ResumeTemplateBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Job Description Analysis / Resume Generation ────────────

class JDAnalyzeRequest(BaseModel):
    job_description: Optional[str] = None
    job_url: Optional[str] = None


class JDAnalyzeResponse(BaseModel):
    keywords: List[str]
    job_description_used: str


class ResumeGenerateRequest(BaseModel):
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    job_url: Optional[str] = None
    template_id: Optional[int] = None
    model: Optional[str] = None  # override Hugging Face model id


class GeneratedResumeResponse(BaseModel):
    id: int
    job_title: Optional[str] = None
    job_description: str
    extracted_keywords: Optional[str] = None
    content: str
    version: int
    share_token: Optional[str] = None
    rating: Optional[int] = None
    feedback_text: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeFeedbackRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback_text: Optional[str] = Field(None, max_length=1000)


class ResumeShareResponse(BaseModel):
    share_token: str
    share_url: str


class DashboardSummary(BaseModel):
    name: str
    profession: str
    interest: str
    email: EmailStr
    total_skills: int
    total_projects: int
    total_achievements: int
    total_education: int
    total_experience: int
    total_resumes_generated: int
    has_huggingface_key: bool


# ─── Resume Parsing & Bulk Import ─────────────────────────────

class ResumeParseTextRequest(BaseModel):
    text: str = Field(..., min_length=10)


class ParsedResumeResponse(BaseModel):
    skills: List[str] = []
    experience: List[dict] = []
    education: List[dict] = []
    projects: List[dict] = []
    achievements: List[dict] = []
    other_info: List[str] = []
    raw_text: Optional[str] = None


class ParsedResumeImportRequest(BaseModel):
    skills: Optional[List[str]] = []
    experience: Optional[List[dict]] = []
    education: Optional[List[dict]] = []
    projects: Optional[List[dict]] = []
    achievements: Optional[List[dict]] = []
    other_info: Optional[List[str]] = []


# ─── External Profile Scraping ────────────────────────────────

class GitHubImportRequest(BaseModel):
    github_username: str = Field(..., min_length=1, max_length=100)


class LinkedInImportRequest(BaseModel):
    linkedin_url: str = Field(..., min_length=3, max_length=300)


