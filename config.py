"""
Centralized app configuration.

Uses pydantic-settings so every value can be overridden by an environment
variable (or a local .env file) without touching code. This is the pattern
you want for AWS deployments: in production you set real env vars (e.g. via
Elastic Beanstalk config, ECS task definition, or EC2 user-data) instead of
shipping a .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://taskflow:taskflow@localhost:5432/taskflow"

    # Auth
    secret_key: str = "dev-secret-change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # AWS
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_region: str = "us-east-1"
    s3_bucket_name: str = "taskflow-attachments"

    environment: str = "development"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
