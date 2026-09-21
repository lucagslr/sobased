"""Settings shared by every environment. dev.py, prod.py and test.py override."""

from pathlib import Path

from config.env import env, env_bool, env_int, env_list

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost")

# Public URL of the site (no trailing slash). Drives e-mail links, CSRF trusted
# origins and whether cookies are flagged Secure.
SITE_URL = env("SITE_URL", "http://localhost:8080").rstrip("/")
SITE_IS_HTTPS = SITE_URL.startswith("https://")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "django_filters",
    # Project apps, in dependency order (see docs/PLAN.md §1).
    "apps.core",
    "apps.accounts",
    "apps.workspaces",
    "apps.projects",
    "apps.tasks",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "sobased"),
        "USER": env("POSTGRES_USER", "sobased"),
        "PASSWORD": env("POSTGRES_PASSWORD", ""),
        "HOST": env("POSTGRES_HOST", "postgres"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Authentication ---------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    # Kept only so Django can still verify (and upgrade) a hash created elsewhere.
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
_VALIDATORS = "django.contrib.auth.password_validation."
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": _VALIDATORS + "UserAttributeSimilarityValidator"},
    {"NAME": _VALIDATORS + "MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": _VALIDATORS + "CommonPasswordValidator"},
    {"NAME": _VALIDATORS + "NumericPasswordValidator"},
]
# Password-reset links stay valid for 24 hours.
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24
# E-mail verification links stay valid for 3 days.
EMAIL_VERIFICATION_MAX_AGE = 60 * 60 * 24 * 3
# true: anyone can sign up. false: only through an invitation link (phase 2).
REGISTRATION_OPEN = env_bool("REGISTRATION_OPEN", True)
# Hook used by sign-up to honour invitation links without apps.accounts
# importing apps.projects: token -> invited e-mail, or None.
INVITATION_EMAIL_RESOLVER = "apps.projects.services.resolve_invitation_email"
# Failed logins tolerated per username per hour before a temporary lock.
LOGIN_MAX_FAILURES_PER_HOUR = 10

# --- Sessions, cookies, CSRF -------------------------------------------------
# Same-origin SPA: the session cookie is HttpOnly; the CSRF cookie is readable
# by the front, which echoes it in the X-CSRFToken header.
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = SITE_IS_HTTPS
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = SITE_IS_HTTPS
CSRF_TRUSTED_ORIGINS = [SITE_URL]
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

# Caddy terminates TLS and forwards the original scheme and host.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# --- Internationalisation ----------------------------------------------------
# The interface is French only; datetimes are stored in UTC and rendered in the
# user's own timezone by the front.
LANGUAGE_CODE = "fr"
TIME_ZONE = "Europe/Zurich"
USE_I18N = True
USE_TZ = True

# --- Redis: cache (db 1) and Celery broker (db 0) ------------------------------
REDIS_URL = env("REDIS_URL", "redis://redis:6379").rstrip("/")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": f"{REDIS_URL}/1",
    }
}

CELERY_BROKER_URL = f"{REDIS_URL}/0"
CELERY_TASK_IGNORE_RESULT = True
CELERY_TIMEZONE = "UTC"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
# Periodic tasks are declared here, phase by phase (no database scheduler).
CELERY_BEAT_SCHEDULE = {
    # Extends the 90-day window of every recurring task series (SPEC §7).
    "materialise-task-series": {
        "task": "apps.tasks.tasks.materialise_all_series",
        "schedule": 60 * 60 * 24,
    },
}

# --- Files ---------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = env("STATIC_ROOT", str(BASE_DIR / "staticfiles"))
# No MEDIA_URL route exists: uploads are only ever served through
# apps.core.files.protected_file_response() after a permission check.
MEDIA_ROOT = env("MEDIA_ROOT", "/data/media")
MEDIA_URL = "/media-is-never-served-directly/"
# True when a reverse proxy (Caddy) understands X-Accel-Redirect.
PROTECTED_MEDIA_ACCEL = env_bool("PROTECTED_MEDIA_ACCEL", True)
MAX_UPLOAD_MB = env_int("MAX_UPLOAD_MB", 500)
AVATAR_MAX_MB = 10
# Large uploads are streamed to temporary files, never held in memory.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# --- E-mail ----------------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", "")
EMAIL_PORT = env_int("EMAIL_PORT", 587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "SOBASED <no-reply@localhost>")
# Without SMTP configured, e-mails are printed to the container logs.
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)

# --- Django REST Framework ---------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.core.authentication.SessionAuthentication401",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Scoped throttles, stored in Redis. See SPECIFICATIONS.md §12.
    "DEFAULT_THROTTLE_RATES": {
        "login": "5/min",
        "register": "5/hour",
        "password_reset": "5/hour",
        "verify_email": "5/hour",
        "user_search": "30/min",
        "invitation_lookup": "30/min",
    },
    # One proxy (Caddy) sits in front: trust the last X-Forwarded-For entry.
    "NUM_PROXIES": 1,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SOBASED API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    "COMPONENT_SPLIT_REQUEST": True,
    "POSTPROCESSING_HOOKS": [
        "drf_spectacular.hooks.postprocess_schema_enums",
        "apps.core.schema.mark_response_fields_required",
    ],
    # Readable, stable enum names in the generated TypeScript types.
    "ENUM_NAME_OVERRIDES": {
        "RoleEnum": "apps.projects.models.Role.choices",
        "GrantableRoleEnum": "apps.projects.serializers.GRANTABLE_ROLES",
        "ProjectStatusEnum": "apps.projects.models.PROJECT_STATUS_CHOICES",
        "TaskStatusEnum": "apps.tasks.models.TASK_STATUS_CHOICES",
    },
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
