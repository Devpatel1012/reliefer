from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

import models
import schemas
from database import get_db
from dependencies import get_current_user

router = APIRouter(prefix="/education", tags=["Education"])


@router.get("/", response_model=List[schemas.EducationResponse])
def list_education(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.Education).filter(models.Education.user_id == current_user.id).all()


@router.post("/", response_model=schemas.EducationResponse, status_code=status.HTTP_201_CREATED)
def create_education(
    education: schemas.EducationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_education = models.Education(**education.model_dump(), user_id=current_user.id)
    db.add(db_education)
    db.commit()
    db.refresh(db_education)
    return db_education


def _get_owned_education(education_id: int, db: Session, current_user: models.User) -> models.Education:
    education = (
        db.query(models.Education)
        .filter(models.Education.id == education_id, models.Education.user_id == current_user.id)
        .first()
    )
    if not education:
        raise HTTPException(status_code=404, detail="Education entry not found")
    return education


@router.put("/{education_id}", response_model=schemas.EducationResponse)
def update_education(
    education_id: int,
    payload: schemas.EducationUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    education = _get_owned_education(education_id, db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(education, field, value)
    db.commit()
    db.refresh(education)
    return education


@router.delete("/{education_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_education(
    education_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    education = _get_owned_education(education_id, db, current_user)
    db.delete(education)
    db.commit()
    return None
