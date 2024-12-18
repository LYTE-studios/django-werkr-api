from django.urls import path
from .views import JWTAuthenticationView, JWTRefreshView, JWTTestConnectionView

urlpatterns = [
    path('token/', JWTAuthenticationView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', JWTRefreshView.as_view(), name='token_refresh'),
    path('hello/there/', JWTTestConnectionView.as_view(), name='test_connection'),
]