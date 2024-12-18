from django.urls import path
from .views import (
    JWTAuthenticationView, JWTRefreshView, JWTTestConnectionView,
    ProfileMeView, LanguageSettingsView, UploadUserProfilePictureView
)


urlpatterns = [
    path('token/', JWTAuthenticationView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', JWTRefreshView.as_view(), name='token_refresh'),
    path('hello/there/', JWTTestConnectionView.as_view(), name='test_connection'),
    path('users/me/', ProfileMeView.as_view(), name='profile_me'),
    path('users/settings/languages/', LanguageSettingsView.as_view(), name='language_settings'),
    path('users/settings/profile-picture/', UploadUserProfilePictureView.as_view(), name='upload_profile_picture'),
]
