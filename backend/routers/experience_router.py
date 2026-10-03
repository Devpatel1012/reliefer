
import models
import schemas
from database import get_db
from dependencies import get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/experience", tags=["Experience"])


@router.get("/", response_model=list[schemas.ExperienceResponse])
def list_experience(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return db.query(models.Experience).filter(models.Experience.user_id == current_user.id).all()


@router.post("/", response_model=schemas.ExperienceResponse, status_code=status.HTTP_201_CREATED)
def create_experience(
    experience: schemas.ExperienceCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_experience = models.Experience(**experience.model_dump(), user_id=current_user.id)
    db.add(db_experience)
    db.commit()
    db.refresh(db_experience)
    return db_experience


def _get_owned_experience(
    experience_id: int, db: Session, current_user: models.User
) -> models.Experience:
    experience = (
        db.query(models.Experience)
        .filter(
            models.Experience.id == experience_id,
            models.Experience.user_id == current_user.id,
        )
        .first()
    )
    if not experience:
        raise HTTPException(status_code=404, detail="Experience entry not found")
    return experience


@router.put("/{experience_id}", response_model=schemas.ExperienceResponse)
def update_experience(
    experience_id: int,
    payload: schemas.ExperienceUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    experience = _get_owned_experience(experience_id, db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(experience, field, value)
    db.commit()
    db.refresh(experience)
    return experience


@router.delete("/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(
    experience_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    experience = _get_owned_experience(experience_id, db, current_user)
    db.delete(experience)
    db.commit()
