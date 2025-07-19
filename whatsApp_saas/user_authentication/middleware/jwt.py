from django.utils.deprecation import MiddlewareMixin
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth.models import AnonymousUser
import logging

logger = logging.getLogger(__name__)

class JWTAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        logger.debug("🔍 JWTAuthenticationMiddleware running...")

        jwt_authenticator = JWTAuthentication()
        raw_token = None

        # Check Authorization header
        header = jwt_authenticator.get_header(request)
        if header:
            raw_token = jwt_authenticator.get_raw_token(header)
            logger.debug(f"🪪 Found token in header: {raw_token}")

        # Fallback to access_token cookie
        if raw_token is None:
            raw_token = request.COOKIES.get('access_token')
            logger.debug(f"🍪 Found token in cookie: {raw_token}")

        if raw_token:
            try:
                validated_token = jwt_authenticator.get_validated_token(raw_token)
                user = jwt_authenticator.get_user(validated_token)
                logger.debug(f"✅ Authenticated user: {user}")
                request.user = user
                request._cached_user = user
                return
            except AuthenticationFailed as e:
                logger.warning(f"❌ Token invalid: {str(e)}")

        logger.debug("🙈 No valid token, setting user to AnonymousUser")
        request.user = AnonymousUser()
        request._cached_user = AnonymousUser()
