from fastapi import FastAPI

from app.routers import auth, users, projects, tasks

app = FastAPI(
    title="TaskFlow API",
    description="Intermediate-level project/task management API — FastAPI + PostgreSQL + AWS S3",
    version="1.0.0",
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(tasks.router)


@app.get("/health", tags=["health"])
def health_check():
    """Used by load balancers / ECS / EB health checks in production."""
    return {"status": "ok"}
