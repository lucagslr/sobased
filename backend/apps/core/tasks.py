from celery import shared_task
from django.core.mail import EmailMultiAlternatives


@shared_task(autoretry_for=(Exception,), retry_backoff=60, max_retries=5)
def send_email(*, to: str, subject: str, text: str, html: str):
    """Send one e-mail (text + HTML). Retried with backoff if SMTP fails."""
    message = EmailMultiAlternatives(subject=subject, body=text, to=[to])
    message.attach_alternative(html, "text/html")
    message.send()
