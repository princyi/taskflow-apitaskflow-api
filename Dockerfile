FROM python:3.12-slim

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Run migrations then start the server. In a real pipeline you'd usually
# run migrations as a separate release step (e.g. an ECS one-off task)
# rather than on every container start, but this keeps the scaffold simple.
CMD alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000
