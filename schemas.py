from datetime import datetime
from pydantic import BaseModel, EmailStr, ConfigDict

from app.models import TaskStatus, TaskPriority


# ---------- Auth ----------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------- User ----------

class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Project ----------

class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectOut(BaseModel):
    id: int
    name: str
    description: str | None
    owner_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Task ----------

class TaskCreate(BaseModel):
    title: str
    description: str | None = None
    priority: TaskPriority = TaskPriority.medium
    due_date: datetime | None = None
    assignee_id: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    due_date: datetime | None = None
    assignee_id: int | None = None


class TaskOut(BaseModel):
    id: int
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    due_date: datetime | None
    project_id: int
    assignee_id: int | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------- Attachment ----------

class AttachmentOut(BaseModel):
    id: int
    task_id: int
    filename: str
    content_type: str | None
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AttachmentDownloadOut(BaseModel):
    filename: str
    download_url: str
    expires_in_seconds: int
