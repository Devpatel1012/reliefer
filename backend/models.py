from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    interest = Column(String, nullable=False)
    profession = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)

    # Crucial for Reliefer's architecture
    huggingface_api_key = Column(String, nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    skills = relationship("Skill", back_populates="owner", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    achievements = relationship("Achievement", back_populates="owner", cascade="all, delete-orphan")
    education = relationship("Education", back_populates="owner", cascade="all, delete-orphan")
    experience = relationship("Experience", back_populates="owner", cascade="all, delete-orphan")
    templates = relationship("ResumeTemplate", back_populates="owner", cascade="all, delete-orphan")
    resumes = relationship("GeneratedResume", back_populates="owner", cascade="all, delete-orphan")


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    category = Column(String, nullable=True)  # e.g. "Technical", "Soft Skill", "Tool"
    proficiency = Column(String, nullable=True)  # e.g. "Beginner", "Intermediate", "Advanced"

    owner = relationship("User", back_populates="skills")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    technologies = Column(String, nullable=True)  # comma-separated for simplicity
    link = Column(String, nullable=True)
    start_date = Column(String, nullable=True)  # stored as free text (e.g. "Jan 2025")
    end_date = Column(String, nullable=True)

    owner = relationship("User", back_populates="projects")


class Achievement(Base):
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    date = Column(String, nullable=True)

    owner = relationship("User", back_populates="achievements")


class Education(Base):
    __tablename__ = "education"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    institution = Column(String, nullable=False)
    degree = Column(String, nullable=False)
    field_of_study = Column(String, nullable=True)
    start_year = Column(String, nullable=True)
    end_year = Column(String, nullable=True)
    gpa = Column(String, nullable=True)

    owner = relationship("User", back_populates="education")


class Experience(Base):
    __tablename__ = "experience"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    company = Column(String, nullable=False)
    role = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    is_current = Column(Boolean, default=False)

    owner = relationship("User", back_populates="experience")


class ResumeTemplate(Base):
    __tablename__ = "resume_templates"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    # HTML/markdown-like layout with {{placeholders}} the generator fills in
    content = Column(Text, nullable=False)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="templates")


class GeneratedResume(Base):
    __tablename__ = "generated_resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    template_id = Column(Integer, ForeignKey("resume_templates.id"), nullable=True)

    job_title = Column(String, nullable=True)
    job_description = Column(Text, nullable=False)
    extracted_keywords = Column(Text, nullable=True)  # comma-separated

    content = Column(Text, nullable=False)  # the AI-generated resume text/HTML
    version = Column(Integer, default=1)
    share_token = Column(String, unique=True, index=True, nullable=True)
    rating = Column(Integer, nullable=True)
    feedback_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    owner = relationship("User", back_populates="resumes")
