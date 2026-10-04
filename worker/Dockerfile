# Celery worker + beat share the API code base (tasks live in apps/api/app/tasks.py).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /srv/api
COPY apps/api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api/ .
CMD ["celery", "-A", "app.celery_app", "worker", "-B", "--loglevel=INFO"]
