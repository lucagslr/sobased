"""drf-spectacular glue: teaches the OpenAPI generator about our authenticator."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class SessionAuthentication401Scheme(OpenApiAuthenticationExtension):
    target_class = "apps.core.authentication.SessionAuthentication401"
    name = "cookieAuth"

    def get_security_definition(self, auto_schema):
        return {"type": "apiKey", "in": "cookie", "name": "sessionid"}
