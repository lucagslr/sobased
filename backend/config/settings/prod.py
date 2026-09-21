"""Production settings.

TLS, the HTTP -> HTTPS redirect and the security headers (HSTS, CSP...) are
handled by Caddy, in front of Django. The matching Django checks are silenced
on purpose rather than duplicated here.
"""

from .base import *

DEBUG = False
SECURE_CONTENT_TYPE_NOSNIFF = True
# Production is HTTPS only, whatever SITE_URL says.
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SILENCED_SYSTEM_CHECKS = [
    "security.W004",  # HSTS: set by Caddy
    "security.W008",  # SSL redirect: done by Caddy
]
