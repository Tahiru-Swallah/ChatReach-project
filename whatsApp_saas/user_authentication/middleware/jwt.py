from django.utils.deprecation import MiddlewareMixin
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken, AccessToken
from django.conf import settings


class JWTAuthenticationMiddleware(MiddlewareMixin):
    """
    Middleware to authenticate user using JWT from either
    the Authorization header or access_token cookie.
    Auto-refreshes expired access tokens if a valid refresh_token is present.
    """

    def process_request(self, request):
        # If already logged in via Django session, don't override
        if request.user.is_authenticated:
            return

        jwt_authenticator = JWTAuthentication()
        raw_token = None

        # Try to get token from Authorization header
        header = jwt_authenticator.get_header(request)
        if header:
            raw_token = jwt_authenticator.get_raw_token(header)

        # If no token in header, try from cookies
        if raw_token is None:
            raw_token = request.COOKIES.get("access_token")

        if raw_token is None:
            request.user = AnonymousUser()
            return

        try:
            # Try validating access token
            validated_token = jwt_authenticator.get_validated_token(raw_token)
            user = jwt_authenticator.get_user(validated_token)
            request.user = user
            request._cached_user = user
        except (AuthenticationFailed, InvalidToken, TokenError):
            # Access token invalid or expired → try refresh
            refresh_token = request.COOKIES.get("refresh_token")
            if refresh_token:
                try:
                    refresh = RefreshToken(refresh_token)
                    new_access = str(refresh.access_token)

                    # Update request.user with new token
                    validated_token = jwt_authenticator.get_validated_token(new_access)
                    user = jwt_authenticator.get_user(validated_token)
                    request.user = user
                    request._cached_user = user

                    # Attach new access_token to request (so views know)
                    request.new_access_token = new_access

                except (InvalidToken, TokenError):
                    # Refresh also invalid → log out user
                    request.user = AnonymousUser()
            else:
                request.user = AnonymousUser()

    def process_response(self, request, response):
        """
        If a new access token was generated during the request,
        set it back in the response cookies.
        """
        if hasattr(request, "new_access_token"):
            response.set_cookie(
                "access_token",
                request.new_access_token,
                httponly=True,
                secure=settings.SECURE_COOKIE,   # 🔐 True if HTTPS
                samesite="Lax",
                max_age=3600,   # 1 hour
            )
        return response
