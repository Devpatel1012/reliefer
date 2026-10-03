from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import get_current_user

router = APIRouter(prefix="/skills", tags=["Skills"])


@router.get("/", response_model=List[schemas.SkillResponse])
def list_skills(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.Skill).filter(models.Skill.user_id == current_user.id).all()


@router.post("/", response_model=schemas.SkillResponse, status_code=status.HTTP_201_CREATED)
def create_skill(
    skill: schemas.SkillCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_skill = models.Skill(**skill.model_dump(), user_id=current_user.id)
    db.add(db_skill)
    db.commit()
    db.refresh(db_skill)
    return db_skill


def _get_owned_skill(skill_id: int, db: Session, current_user: models.User) -> models.Skill:
    skill = (
        db.query(models.Skill)
        .filter(models.Skill.id == skill_id, models.Skill.user_id == current_user.id)
        .first()
    )
    if not skill:
        raise HTTPException(status_code=404, detail="Skill not found")
    return skill


@router.put("/{skill_id}", response_model=schemas.SkillResponse)
def update_skill(
    skill_id: int,
    payload: schemas.SkillUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    skill = _get_owned_skill(skill_id, db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(skill, field, value)
    db.commit()
    db.refresh(skill)
    return skill


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(
    skill_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    skill = _get_owned_skill(skill_id, db, current_user)
    db.delete(skill)
    db.commit()
    return None
