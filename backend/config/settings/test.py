"""Test settings: no Redis, no SMTP, no proxy, fast password hashing."""

from .base import *

DEBUG = False
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
SESSION_ENGINE = "django.contrib.sessions.backends.db"
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
# Tasks run inline so tests can assert on their effects (e-mails in mail.outbox).
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
# Argon2 is deliberately slow; tests do not need that.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
MEDIA_ROOT = "/tmp/sobased-test-media"
# Without Caddy in front, files are streamed by Django itself.
PROTECTED_MEDIA_ACCEL = False
# A fixed, valid Fernet key: share URLs must round-trip in tests.
FERNET_KEY = "b2xEbIwAHf7KJv-jf6qtpvlPZKdV6KaRFjkDcHb1ZlA="
