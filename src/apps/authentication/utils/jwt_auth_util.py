from datetime import datetime

from django.contrib.auth import authenticate
from django.contrib.auth.models import Group
from rest_framework.request import HttpRequest
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

User = get_user_model()

from apps.core.assumptions import *

from .authentication_util import AuthenticationUtil
from .encryption_util import EncryptionUtil
from apps.core.utils.formatters import FormattingUtil
from apps.core.utils.wire_names import k_access_token, k_refresh_token, k_session_expiry


class JWTAuthUtil:
    k_token = "Authorization"

    @staticmethod
    def check_for_authentication(request: HttpRequest):
        """
        Check a users credentials
        """

        app_type = AuthenticationUtil.check_client_secret(request)

        if app_type is None:
            return None

        auth_token = request.headers.get(JWTAuthUtil.k_token, None)

        if not auth_token:
            return None

        try:
            # This will raise an error if the token is invalid
            token = AccessToken(auth_token)

            # Here, instead of checking if the token is active (because that's
            # implicitly done when we initialize AccessToken), we're checking its payload.
            if "user_id" in token:
                return token
            else:
                return None

        except (InvalidToken, TokenError):
            return None

    @staticmethod
    def authenticate(email, password, group: Group):
        """
        Function for authenticating a user and returning a JWT token
        """

        # Get the user
        try:
            user = User.objects.get(email=email, groups__id__contains=group.id)
        except User.DoesNotExist:
            return None

        session_expiry = 0

        if group.name == CMS_GROUP_NAME:
            admin_profile = user.admin_profile
            if admin_profile.session_duration is not None:
                session_expiry = (
                    FormattingUtil.to_timestamp(datetime.utcnow())
                    + admin_profile.session_duration
                )

        if group.name == WORKERS_GROUP_NAME:
            worker = user.worker_profile

            if not worker.accepted:
                return None

        # Check if the user is a superuser
        if user.is_superuser:
            # Check the credentials using the django auth system
            if not authenticate(username=user.username, password=password):
                return None
        else:
            if user.salt is None:
                return None
            # Check the users credentials
            if not EncryptionUtil.check_value(password, user.salt, user.password):
                return None

        # Get the refresh token
        refresh = RefreshToken.for_user(user)

        # Return the tokens
        return {
            k_access_token: str(refresh.access_token),
            k_refresh_token: str(refresh),
            k_session_expiry: session_expiry,
        }
