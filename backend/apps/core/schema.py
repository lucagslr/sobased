"""drf-spectacular glue: teaches the OpenAPI generator about our authenticator."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionAuthentication401Scheme(OpenApiAuthenticationExtension):
    target_class = "apps.core.authentication.SessionAuthentication401"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "sessionid"}


def mark_response_fields_required(result, generator, request, public):
    """Postprocessing hook: in RESPONSE components every property is required.

    DRF always serialises every field, but drf-spectacular only lists as
    "required" the fields that are required on input. Without this, the
    generated TypeScript types make half of each response optional.
    Request components (names ending in "Request") are left untouched.
    """
    for name, component in result.get("components", {}).get("schemas", {}).items():
        if name.endswith("Request") or "properties" not in component:
            continue
        component["required"] = sorted(component["properties"])
    return result
