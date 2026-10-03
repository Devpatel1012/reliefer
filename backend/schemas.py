from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_serializer,
)

# ─── Auth / User ───────────────────────────────────────────

class UserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    age: int = Field(..., ge=16, le=120)
    interest: str = Field(..., min_length=2, max_length=100)
    profession: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class UserUpdate(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=100)
    age: int | None = Field(None, ge=16, le=120)
    interest: str | None = Field(None, min_length=2, max_length=100)
    profession: str | None = Field(None, min_length=2, max_length=100)


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
    huggingface_api_key: str | None = None

    @field_serializer("huggingface_api_key")
    def serialize_api_key(self, v: str | None, _info) -> str | None:
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
    category: str | None = None
    proficiency: str | None = None


class SkillCreate(SkillBase):
    pass


class SkillUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    proficiency: str | None = None


class SkillResponse(SkillBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ─── Projects ───────────────────────────────────────────────

class ProjectBase(BaseModel):
    title: str
    description: str | None = None
    technologies: str | None = None
    link: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    technologies: str | None = None
    link: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ProjectResponse(ProjectBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ─── Achievements ───────────────────────────────────────────

class AchievementBase(BaseModel):
    title: str
    description: str | None = None
    date: str | None = None


class AchievementCreate(AchievementBase):
    pass


class AchievementUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    date: str | None = None


class AchievementResponse(AchievementBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ─── Education ──────────────────────────────────────────────

class EducationBase(BaseModel):
    institution: str
    degree: str
    field_of_study: str | None = None
    start_year: str | None = None
    end_year: str | None = None
    gpa: str | None = None


class EducationCreate(EducationBase):
    pass


class EducationUpdate(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field_of_study: str | None = None
    start_year: str | None = None
    end_year: str | None = None
    gpa: str | None = None


class EducationResponse(EducationBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


# ─── Experience ─────────────────────────────────────────────

class ExperienceBase(BaseModel):
    company: str
    role: str
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool = False


class ExperienceCreate(ExperienceBase):
    pass


class ExperienceUpdate(BaseModel):
    company: str | None = None
    role: str | None = None
    description: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool | None = None


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
    name: str | None = None
    content: str | None = None
    is_default: bool | None = None


class ResumeTemplateResponse(ResumeTemplateBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─── Job Description Analysis / Resume Generation ────────────

class JDAnalyzeRequest(BaseModel):
    job_description: str | None = None
    job_url: str | None = None


class JDAnalyzeResponse(BaseModel):
    keywords: list[str]
    job_description_used: str


class ResumeGenerateRequest(BaseModel):
    job_title: str | None = None
    job_description: str | None = None
    job_url: str | None = None
    template_id: int | None = None
    model: str | None = None  # override Hugging Face model id


class GeneratedResumeResponse(BaseModel):
    id: int
    job_title: str | None = None
    job_description: str
    extracted_keywords: str | None = None
    content: str
    version: int
    share_token: str | None = None
    rating: int | None = None
    feedback_text: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ResumeFeedbackRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    feedback_text: str | None = Field(None, max_length=1000)


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
    skills: list[str] = []
    experience: list[dict] = []
    education: list[dict] = []
    projects: list[dict] = []
    achievements: list[dict] = []
    other_info: list[str] = []
    raw_text: str | None = None


class ParsedResumeImportRequest(BaseModel):
    skills: list[str] | None = []
    experience: list[dict] | None = []
    education: list[dict] | None = []
    projects: list[dict] | None = []
    achievements: list[dict] | None = []
    other_info: list[str] | None = []


# ─── External Profile Scraping ────────────────────────────────

class GitHubImportRequest(BaseModel):
    github_username: str = Field(..., min_length=1, max_length=100)


class LinkedInImportRequest(BaseModel):
    linkedin_url: str = Field(..., min_length=3, max_length=300)


