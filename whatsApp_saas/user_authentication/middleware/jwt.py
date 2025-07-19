from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import AnonymousUser

class JWTAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        jwt_authenticator = JWTAuthentication()

        raw_token = None

        # Try Authorization header
        header = jwt_authenticator.get_header(request)
        if header:
            raw_token = jwt_authenticator.get_raw_token(header)

        # Fallback to cookie
        if raw_token is None:
            raw_token = request.COOKIES.get('access_token')

        if raw_token:
            try:
                validated_token = jwt_authenticator.get_validated_token(raw_token)
                user = jwt_authenticator.get_user(validated_token)
                request.user = user
                request._cached_user = user
                return
            except AuthenticationFailed:
                pass  # Invalid token — fall back to AnonymousUser

        # Always set request.user to something
        if not hasattr(request, 'user'):
            request.user = AnonymousUser()
            request._cached_user = AnonymousUser()
