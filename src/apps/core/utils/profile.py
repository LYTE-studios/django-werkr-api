from apps.authentication.models import User
from api.settings import STATIC_URL


class MediaUtil:

    @staticmethod
    def to_media_url(url: str):
        if url is None:
            return None
        return '/media/' + url.replace(STATIC_URL, "")

