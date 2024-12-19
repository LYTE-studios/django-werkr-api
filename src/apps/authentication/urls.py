from django.urls import path

from .views import (
    JWTAuthenticationView, JWTRefreshView, JWTTestConnectionView,
    ProfileMeView, LanguageSettingsView, UploadUserProfilePictureView,
    PasswordResetRequestView, VerifyCodeView, ResetPasswordView,
    WorkerRegisterView, StatisticsView, WorkerDetailView,
    WorkersListView, AcceptWorkerView,
    CreateCustomerView, CustomersListView, CustomerDetailView,
    CustomerSearchTermView
)

urlpatterns = [
    path('token/', JWTAuthenticationView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', JWTRefreshView.as_view(), name='token_refresh'),
    path('hello/there/', JWTTestConnectionView.as_view(), name='test_connection'),
    path('users/me/', ProfileMeView.as_view(), name='profile_me'),
    path('users/settings/languages/', LanguageSettingsView.as_view(), name='language_settings'),
    path('users/settings/profile-picture/', UploadUserProfilePictureView.as_view(), name='upload_profile_picture'),
    path('password_reset/', PasswordResetRequestView.as_view(), name="password_reset"),
    path('password_reset/verify/', VerifyCodeView.as_view(), name="password_reset_verify"),
    path('password_reset/reset/', ResetPasswordView.as_view(), name="password_reset_reset"),

    # Workers
    path('workers/register', WorkerRegisterView.as_view()),
    path('workers/statistics/me', StatisticsView.as_view()),
    path('workers/details/<str:id>', WorkerDetailView.as_view()),
    path('workers', WorkersListView.as_view()),
    path('accept/workers/<str:id>', AcceptWorkerView.as_view()),
    path('workers/<str:sort_term>/<str:algorithm>/<int:count>/<int:page>', WorkersListView.as_view()),
    path('workers/<int:count>/<int:page>', WorkersListView.as_view()),
    path('workers/<int:count>/<int:page>/<str:search_term>', WorkersListView.as_view()),
    path('<str:state>/workers/<str:sort_term>/<str:algorithm>/<int:count>/<int:page>', WorkersListView.as_view()),
    path('<str:state>/workers/<int:count>/<int:page>', WorkersListView.as_view()),
    path('<str:state>/workers/<int:count>/<int:page>/<str:search_term>', WorkersListView.as_view()),

    # Customers
    path('customers/create', CreateCustomerView.as_view()),
    path('customers', CustomersListView.as_view()),
    path('customers/<str:sort_term>/<str:algorithm>/<int:count>/<int:page>', CustomersListView.as_view()),
    path('customers/<int:count>/<int:page>', CustomersListView.as_view()),
    path('customers/<int:count>/<int:page>/<str:search_term>', CustomersListView.as_view()),
    path('customers/details/<str:id>', CustomerDetailView.as_view()),
    path('customers/<str:search_term>', CustomerSearchTermView.as_view()),
]
