# One image, two targets: `dev` (runserver, dev tools) and `prod` (gunicorn, non-root).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# Uploaded files live outside the code directory, on a volume shared with Caddy.
RUN mkdir -p /data/media
COPY requirements/ requirements/

FROM base AS dev
RUN pip install -r requirements/dev.txt -c requirements/constraints.txt
COPY . .
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

FROM base AS prod
RUN pip install -r requirements/prod.txt -c requirements/constraints.txt
COPY . .
RUN useradd --uid 1000 --create-home app && chown -R app:app /data/media
USER app
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--worker-class", "gthread", "--workers", "2", "--threads", "4", "--timeout", "120"]
