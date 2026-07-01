"""
Thin wrapper around boto3 for task attachment storage.

Why S3 instead of storing files in the DB or on the app server's disk:
- EC2/ECS instances are ephemeral (autoscaling, redeploys wipe local disk).
- S3 is durable, cheap, and scales independently of the API server.
- We never proxy file bytes through FastAPI for downloads; we hand back a
  short-lived presigned URL and let the client talk to S3 directly.
"""
import uuid

import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, UploadFile

from app.config import settings

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )
    return _s3_client


def build_object_key(task_id: int, filename: str) -> str:
    # Prefix by task_id so a task's files are grouped, and add a uuid to
    # avoid collisions/overwrites when two people upload "invoice.pdf".
    unique_name = f"{uuid.uuid4().hex}-{filename}"
    return f"tasks/{task_id}/{unique_name}"


def upload_file(task_id: int, file: UploadFile) -> str:
    key = build_object_key(task_id, file.filename)
    client = get_s3_client()
    try:
        client.upload_fileobj(
            file.file,
            settings.s3_bucket_name,
            key,
            ExtraArgs={"ContentType": file.content_type or "application/octet-stream"},
        )
    except ClientError as e:
        raise HTTPException(status_code=502, detail=f"S3 upload failed: {e}")
    return key


def generate_presigned_download_url(s3_key: str, expires_in: int = 300) -> str:
    client = get_s3_client()
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket_name, "Key": s3_key},
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        raise HTTPException(status_code=502, detail=f"Could not generate download URL: {e}")


def delete_file(s3_key: str) -> None:
    client = get_s3_client()
    try:
        client.delete_object(Bucket=settings.s3_bucket_name, Key=s3_key)
    except ClientError:
        # Non-fatal: DB row deletion should still succeed even if the S3
        # object was already removed manually.
        pass
