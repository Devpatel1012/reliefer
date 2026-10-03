
import models
import schemas
from database import get_db
from dependencies import get_current_user
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

router = APIRouter(prefix="/templates", tags=["Resume Templates"])


@router.get("/", response_model=list[schemas.ResumeTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    return (
        db.query(models.ResumeTemplate)
        .filter(models.ResumeTemplate.user_id == current_user.id)
        .all()
    )


@router.post("/", response_model=schemas.ResumeTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(
    template: schemas.ResumeTemplateCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if template.is_default:
        # Only one default template per user
        db.query(models.ResumeTemplate).filter(
            models.ResumeTemplate.user_id == current_user.id
        ).update({"is_default": False})

    db_template = models.ResumeTemplate(**template.model_dump(), user_id=current_user.id)
    db.add(db_template)
    db.commit()
    db.refresh(db_template)
    return db_template


def _get_owned_template(
    template_id: int, db: Session, current_user: models.User
) -> models.ResumeTemplate:
    template = (
        db.query(models.ResumeTemplate)
        .filter(
            models.ResumeTemplate.id == template_id,
            models.ResumeTemplate.user_id == current_user.id,
        )
        .first()
    )
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/{template_id}", response_model=schemas.ResumeTemplateResponse)
def update_template(
    template_id: int,
    payload: schemas.ResumeTemplateUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    template = _get_owned_template(template_id, db, current_user)

    if payload.is_default:
        db.query(models.ResumeTemplate).filter(
            models.ResumeTemplate.user_id == current_user.id
        ).update({"is_default": False})

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return template


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    template = _get_owned_template(template_id, db, current_user)
    db.delete(template)
    db.commit()
