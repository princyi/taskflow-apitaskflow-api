# TaskFlow API

A REST API for team task management, built with **FastAPI** and **PostgreSQL**,
featuring JWT authentication, relational data modeling, and AWS S3 file storage,
deployed on AWS RDS + EC2.

## Main task

This project gives teams a backend to manage projects and tasks together —
with secure accounts, structured relational data, and file attachments
stored properly in the cloud instead of on the server. Specifically, it
handles:

1. **User management** — register/log in securely (JWT + hashed passwords)
2. **Project organization** — each user creates and owns projects
3. **Task tracking** — tasks live inside projects, with status, priority,
   due dates, and an assignee
4. **File attachments** — attach files to a task, stored in AWS S3
5. **Access control** — only the right people can view or edit a given
   project or task

## What it does

- Users register and log in (JWT auth, bcrypt-hashed passwords)
- Users own **projects**, and create **tasks** inside them
- Tasks have status, priority, due dates, and an optional assignee
- Tasks can have **file attachments**, stored in **S3** (not on the server disk)
- Authorization is enforced: only a project's owner can edit/delete it; only
  the owner or a task's assignee can touch that task

## Tech stack & why

| Layer | Choice | Why |
|---|---|---|
| API framework | FastAPI | async, automatic OpenAPI docs, Pydantic validation |
| Database | PostgreSQL | relational data (users → projects → tasks → attachments) |
| ORM / migrations | SQLAlchemy + Alembic | schema changes are versioned, not ad hoc `create_all()` |
| Auth | JWT (python-jose) + bcrypt (passlib) | stateless auth, standard OAuth2 password flow |
| File storage | AWS S3 | server is stateless/ephemeral; files must live outside it |
| Hosting | AWS EC2 or Elastic Beanstalk + RDS | classic, transparent deployment model — good for learning before serverless |

## Project structure

```
app/
  main.py              # FastAPI app, router registration
  config.py            # env-driven settings (pydantic-settings)
  database.py          # SQLAlchemy engine/session
  models.py            # User, Project, Task, Attachment
  schemas.py           # Pydantic request/response models
  auth.py              # password hashing, JWT create/verify
  dependencies.py      # get_current_user, ownership checks
  routers/
    auth.py            # /auth/register, /auth/login
    users.py           # /users/me
    projects.py        # /projects CRUD
    tasks.py           # /tasks CRUD + /tasks/{id}/attachments (S3)
  services/
    s3.py              # boto3 wrapper: upload, presigned download URL, delete
alembic/                # DB migrations
tests/                  # pytest + TestClient, in-memory SQLite
docker-compose.yml      # local Postgres + API for development
Dockerfile
```

## Running locally

**Option A — Docker (recommended):**

```bash
cp .env.example .env
# fill in AWS_* values if you want to test attachment uploads; DB works out of the box
docker compose up --build
```

API will be at `http://localhost:8000/docs`.

**Option B — bare metal:**

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # point DATABASE_URL at a local Postgres you're running

alembic upgrade head
uvicorn app.main:app --reload
```

## Running tests

```bash
pip install pytest httpx
pytest tests/ -v
```

Tests use an in-memory SQLite DB via dependency override, so they don't need
a real Postgres or AWS connection. Attachment endpoints (which call S3) are
not covered here — see `tests/test_main.py` for notes on mocking S3 with
`moto` if you extend this.

## Deploying to AWS

This is written as a learning path — do it in order.

### 1. RDS (PostgreSQL)

1. AWS Console → RDS → **Create database** → PostgreSQL → Free tier (or
   `db.t3.micro` for a real dev instance).
2. Set a master username/password, DB name `taskflow`.
3. Under **Connectivity**, put it in the same VPC you'll use for EC2, and
   for a first pass, "Publicly accessible: No" once you're connecting from
   an EC2 instance in the same VPC (keep the DB off the public internet).
4. Security group: allow inbound port `5432` **only** from your EC2
   instance's security group, not `0.0.0.0/0`.
5. Once available, copy the endpoint hostname into `DATABASE_URL` in your
   production env config.

### 2. S3 (attachments)

1. S3 → **Create bucket**, e.g. `taskflow-attachments-yourname` (bucket
   names are globally unique).
2. Block all public access — the app uses **presigned URLs** for downloads,
   so the bucket itself never needs to be public.
3. Create an IAM user (or better, an IAM role attached to the EC2
   instance/EB environment) with a policy scoped to just this bucket:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::taskflow-attachments-yourname/*"
    }
  ]
}
```

Prefer an **IAM role attached to the compute instance** over long-lived
access keys in `.env` — boto3 picks up role credentials automatically, so
in production you can leave `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`
unset entirely.

### 3. Compute — two options

**Elastic Beanstalk (simplest for intermediate level):**

```bash
pip install awsebcli --break-system-packages
eb init -p docker taskflow-api
eb create taskflow-env
eb setenv DATABASE_URL=... SECRET_KEY=... S3_BUCKET_NAME=... AWS_REGION=us-east-1
```

EB provisions the EC2 instance(s), load balancer, and health checks for
you, and reads your `Dockerfile` directly. Attach the IAM role from step 2
to the EB environment's instance profile.

**Plain EC2 (more manual, more transparent):**

1. Launch an EC2 instance (Amazon Linux 2023, `t3.micro`), attach the IAM
   role from step 2.
2. Security group: allow inbound `80`/`443` from anywhere, `22` from your IP.
3. Install Docker, `git clone` this repo, put your production `.env` on the
   instance (or better, pull secrets from AWS Secrets Manager at boot).
4. `docker compose up -d --build` (pointing `DATABASE_URL` at your RDS
   endpoint instead of the local `db` service).
5. Put an Application Load Balancer + ACM certificate in front of it for
   HTTPS, and point Route 53 at the ALB if you have a domain.

### 4. Migrations in production

Run `alembic upgrade head` as a **release step**, not automatically on
every container start in a multi-instance deployment (two instances
racing to migrate at once is a classic bug). For EB, this can be a
`.platform/hooks/postdeploy` script; for EC2/ECS, a one-off task before
the new version goes live.

## Extending this project (good next steps)

- Swap JWT for AWS Cognito to offload auth entirely
- Move to ECS Fargate + RDS for a more production-shaped, autoscaling setup
- Add SQS + a worker to send email notifications on task assignment
- Add CloudWatch alarms on the ALB/RDS for basic observability
- Add rate limiting (e.g. `slowapi`) in front of `/auth/login`
