from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.dependencies import (
    get_current_user,
    get_project_or_404,
    get_task_or_404,
    ensure_project_owner,
)
from app.services import s3

router = APIRouter(tags=["tasks"])

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


def _ensure_task_access(task: models.Task, current_user: models.User) -> models.Project:
    """A task can be touched by the project's owner or the task's assignee."""
    project = task.project
    if project.owner_id != current_user.id and task.assignee_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this task")
    return project


# ---------- Tasks nested under a project ----------

@router.post("/projects/{project_id}/tasks", response_model=schemas.TaskOut, status_code=201)
def create_task(
    project_id: int,
    task_in: schemas.TaskCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, db)
    ensure_project_owner(project, current_user)

    task = models.Task(**task_in.model_dump(), project_id=project.id)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.get("/projects/{project_id}/tasks", response_model=list[schemas.TaskOut])
def list_project_tasks(
    project_id: int,
    status_filter: models.TaskStatus | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    project = get_project_or_404(project_id, db)
    ensure_project_owner(project, current_user)

    query = db.query(models.Task).filter(models.Task.project_id == project_id)
    if status_filter:
        query = query.filter(models.Task.status == status_filter)

    return query.order_by(models.Task.created_at.desc()).offset(skip).limit(limit).all()


# ---------- Individual task ----------

@router.get("/tasks/{task_id}", response_model=schemas.TaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = get_task_or_404(task_id, db)
    _ensure_task_access(task, current_user)
    return task


@router.put("/tasks/{task_id}", response_model=schemas.TaskOut)
def update_task(
    task_id: int,
    task_in: schemas.TaskUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = get_task_or_404(task_id, db)
    _ensure_task_access(task, current_user)

    for field, value in task_in.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)
    return task


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = get_task_or_404(task_id, db)
    project = task.project
    ensure_project_owner(project, current_user)  # only the owner can delete
    db.delete(task)
    db.commit()
    return None


# ---------- Attachments (S3) ----------

@router.post("/tasks/{task_id}/attachments", response_model=schemas.AttachmentOut, status_code=201)
def upload_attachment(
    task_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = get_task_or_404(task_id, db)
    _ensure_task_access(task, current_user)

    file.file.seek(0, 2)  # seek to end
    size = file.file.tell()
    file.file.seek(0)
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 10 MB limit")

    s3_key = s3.upload_file(task_id, file)

    attachment = models.Attachment(
        task_id=task_id,
        filename=file.filename,
        s3_key=s3_key,
        content_type=file.content_type,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


@router.get("/tasks/{task_id}/attachments", response_model=list[schemas.AttachmentOut])
def list_attachments(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = get_task_or_404(task_id, db)
    _ensure_task_access(task, current_user)
    return task.attachments


@router.get(
    "/tasks/{task_id}/attachments/{attachment_id}/download",
    response_model=schemas.AttachmentDownloadOut,
)
def download_attachment(
    task_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    task = get_task_or_404(task_id, db)
    _ensure_task_access(task, current_user)

    attachment = (
        db.query(models.Attachment)
        .filter(models.Attachment.id == attachment_id, models.Attachment.task_id == task_id)
        .first()
    )
    if attachment is None:
        raise HTTPException(status_code=404, detail="Attachment not found")

    expires_in = 300
    url = s3.generate_presigned_download_url(attachment.s3_key, expires_in=expires_in)
    return schemas.AttachmentDownloadOut(
        filename=attachment.filename, download_url=url, expires_in_seconds=expires_in
    )
