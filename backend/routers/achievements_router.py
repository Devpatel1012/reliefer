
import models
import schemas
from database import get_db
from dependencies import get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/achievements", tags=["Achievements"])


@router.get("/", response_model=list[schemas.AchievementResponse])
def list_achievements(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.Achievement)
        .filter(models.Achievement.user_id == current_user.id)
        .all()
    )


@router.post("/", response_model=schemas.AchievementResponse, status_code=status.HTTP_201_CREATED)
def create_achievement(
    achievement: schemas.AchievementCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    db_achievement = models.Achievement(**achievement.model_dump(), user_id=current_user.id)
    db.add(db_achievement)
    db.commit()
    db.refresh(db_achievement)
    return db_achievement


def _get_owned_achievement(
    achievement_id: int, db: Session, current_user: models.User
) -> models.Achievement:
    achievement = (
        db.query(models.Achievement)
        .filter(
            models.Achievement.id == achievement_id,
            models.Achievement.user_id == current_user.id,
        )
        .first()
    )
    if not achievement:
        raise HTTPException(status_code=404, detail="Achievement not found")
    return achievement


@router.put("/{achievement_id}", response_model=schemas.AchievementResponse)
def update_achievement(
    achievement_id: int,
    payload: schemas.AchievementUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    achievement = _get_owned_achievement(achievement_id, db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(achievement, field, value)
    db.commit()
    db.refresh(achievement)
    return achievement


@router.delete("/{achievement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_achievement(
    achievement_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    achievement = _get_owned_achievement(achievement_id, db, current_user)
    db.delete(achievement)
    db.commit()
