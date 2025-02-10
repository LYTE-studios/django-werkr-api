from django.contrib.auth.models import Group
from django.http import HttpRequest

from apps.authentication.models.custom_group import CustomGroup


class AuthenticationUtil:
    """
    Util for authentication services.
    """

    k_client = "Client"

    @staticmethod
    def check_client_secret(request: HttpRequest):
        """
        Searches the request headers for the client secret.

        Returns AppType if valid.
        Returns None if invalid.
        """

        # Catches the secret
        try:
            client_secret = request.headers[AuthenticationUtil.k_client]

        except KeyError:
            return None

        if client_secret is None:
            return None

        try:
            # Returns the app type
            return CustomGroup.objects.get(group_secret=client_secret).group
        except CustomGroup.DoesNotExist:
            return None
