from rest_framework.authentication import SessionAuthentication


class SessionAuthentication401(SessionAuthentication):
    """Session authentication that answers 401 (not 403) when nobody is signed in.

    DRF only sends 401 if the authenticator provides a WWW-Authenticate value.
    The front relies on the difference: 401 = "sign in again",
    403 = "signed in but not allowed".
    """

    def authenticate_header(self, request):
        return "Session"
