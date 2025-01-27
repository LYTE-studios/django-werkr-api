from django.contrib.auth import get_user_model

User = get_user_model()

from .media_util import MediaUtil


class ProfileUtil:

    @staticmethod
    def get_user_profile_picture_url(user: User):
        if not user.is_authenticated or user.profile_picture is None:
            return None

        url = None

        try:
            url = user.profile_picture.url
        except Exception:
            pass

        return MediaUtil.to_media_url(url)
