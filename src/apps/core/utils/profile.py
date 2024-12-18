from apps.authentication.models import User
from api.settings import STATIC_URL


class MediaUtil:

    @staticmethod
    def to_media_url(url: str):
        if url is None:
            return None
        return '/media/' + url.replace(STATIC_URL, "")


class ProfileUtil:

    @staticmethod
    def get_user_profile_picture_url(user: User):
        if user.profile_picture is None:
            return None

        url = None

        try:

            url = user.profile_picture.url
        except Exception:
            pass

        return MediaUtil.to_media_url(url)
