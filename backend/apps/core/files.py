"""Serving uploaded files safely.

Uploads are never reachable through a public URL. A view checks the
permissions first, then calls protected_file_response():

- behind Caddy (PROTECTED_MEDIA_ACCEL=True) Django answers with an
  X-Accel-Redirect header and Caddy streams the file, Range requests included;
- otherwise (tests, bare runserver) Django streams the file itself.

S3 storage (short-lived pre-signed redirect) is added with the files app.
"""

from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, HttpResponse


def protected_file_response(
    field_file,
    *,
    content_type: str,
    filename: str | None = None,
    inline: bool = True,
    cache_control: str = "private, no-store",
):
    """Build the response for a FieldFile the caller is allowed to read."""
    if settings.PROTECTED_MEDIA_ACCEL:
        response = HttpResponse(content_type=content_type)
        # Path relative to MEDIA_ROOT; Caddy resolves it under /srv/media.
        response["X-Accel-Redirect"] = "/" + quote(field_file.name)
    else:
        response = FileResponse(field_file.open("rb"), content_type=content_type)

    disposition = "inline" if inline else "attachment"
    if filename:
        disposition += f"; filename*=UTF-8''{quote(filename)}"
    response["Content-Disposition"] = disposition
    response["Cache-Control"] = cache_control
    response["X-Content-Type-Options"] = "nosniff"
    return response
