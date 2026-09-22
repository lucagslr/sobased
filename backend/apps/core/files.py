"""Serving uploaded files safely.

Uploads are never reachable through a public URL. A view checks the
permissions first, then calls protected_file_response():

- behind Caddy (PROTECTED_MEDIA_ACCEL=True) Django answers with an
  X-Accel-Redirect header and Caddy streams the file, Range requests included;
- with S3-compatible storage (STORAGE_BACKEND=s3) Django redirects to a
  pre-signed URL that expires after SIGNED_URL_SECONDS (60 s by default);
- otherwise (tests, bare runserver) Django streams the file itself.
"""

from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, HttpResponse, HttpResponseRedirect


def _is_remote(field_file) -> bool:
    """A storage without a local path (S3) has no `path`."""
    try:
        field_file.path
    except NotImplementedError:
        return True
    return False


def protected_file_response(
    field_file,
    *,
    content_type: str,
    filename: str | None = None,
    inline: bool = True,
    cache_control: str = "private, no-store",
):
    """Build the response for a FieldFile the caller is allowed to read."""
    disposition = "inline" if inline else "attachment"
    if filename:
        disposition += f"; filename*=UTF-8''{quote(filename)}"

    if _is_remote(field_file):
        # django-storages signs the URL; the response headers are set on the
        # object itself (see STORAGES in settings), the redirect is one-shot.
        url = field_file.storage.url(
            field_file.name,
            parameters={
                "ResponseContentType": content_type,
                "ResponseContentDisposition": disposition,
            },
            expire=settings.SIGNED_URL_SECONDS,
        )
        response = HttpResponseRedirect(url)
        response["Cache-Control"] = "private, no-store"
        return response

    if settings.PROTECTED_MEDIA_ACCEL:
        response = HttpResponse(content_type=content_type)
        # Path relative to MEDIA_ROOT; Caddy resolves it under /srv/media.
        response["X-Accel-Redirect"] = "/" + quote(field_file.name)
    else:
        response = FileResponse(field_file.open("rb"), content_type=content_type)

    response["Content-Disposition"] = disposition
    response["Cache-Control"] = cache_control
    response["X-Content-Type-Options"] = "nosniff"
    return response
