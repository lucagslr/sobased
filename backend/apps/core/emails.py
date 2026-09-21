"""Transactional e-mails: one HTML template + one text template per message.

Templates live in backend/templates/emails/<name>.html and <name>.txt and
extend emails/base.*. Rendering happens here, sending happens in Celery.
"""

from django.conf import settings
from django.template.loader import render_to_string

from .tasks import send_email


def send_templated_email(*, to: str, subject: str, template: str, context: dict):
    context = {"site_url": settings.SITE_URL, **context}
    text = render_to_string(f"emails/{template}.txt", context)
    html = render_to_string(f"emails/{template}.html", context)
    send_email.delay(to=to, subject=subject, text=text, html=html)
