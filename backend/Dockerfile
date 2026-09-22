# One image, two targets: `dev` (runserver, dev tools) and `prod` (gunicorn, non-root).
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app
# WeasyPrint (PDF exports) renders through Pango; DejaVu is the font the
# reports use. ffmpeg: waveforms, MP3 streams, video thumbnails (files app).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
        libffi8 libjpeg62-turbo libopenjp2-7 shared-mime-info fonts-dejavu-core \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*
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
