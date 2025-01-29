from django.urls import path

from .views import (
    JWTAuthenticationView, JWTRefreshView, JWTTestConnectionView,
    ProfileMeView, LanguageSettingsView, UploadUserProfilePictureView,
    PasswordResetRequestView, ValidateRegistrationView, VerifyCodeView, ResetPasswordView,
    WorkerRegisterView, StatisticsView, WorkerDetailView,
    WorkersListView, AcceptWorkerView,
    CreateCustomerView, CustomersListView, CustomerDetailView,
    CustomerSearchTermView, DashboardFlowView, WorkerProfileDetailView
)

urlpatterns = [
    path('token', JWTAuthenticationView.as_view(), name='token_obtain_pair'),
    path('token/refresh', JWTRefreshView.as_view(), name='token_refresh'),
    path('hello/there', JWTTestConnectionView.as_view(), name='test_connection'),
    path('users/me', ProfileMeView.as_view(), name='profile_me'),
    path('users/settings/languages', LanguageSettingsView.as_view(), name='language_settings'),
    path('users/settings/profile-picture', UploadUserProfilePictureView.as_view(), name='upload_profile_picture'),
    path('password_reset', PasswordResetRequestView.as_view(), name="password_reset"),
    path('password_reset/verify', VerifyCodeView.as_view(), name="password_reset_verify"),
    path('password_reset/reset', ResetPasswordView.as_view(), name="password_reset_reset"),
    path('registration/verify', ValidateRegistrationView.as_view(), name="validate_registration"),

    # Workers
    path('workers/onboarding', DashboardFlowView.as_view(), name="onboarding_flow"),
    path('workers/register', WorkerRegisterView.as_view(), name="worker_register"),
    path('workers/statistics/me', StatisticsView.as_view(), name="statistics_view"),
    path('workers/details/<str:id>', WorkerDetailView.as_view(), name="worker_detail"),
    path('workers', WorkersListView.as_view(), name="workers_list"),
    path('accept/workers/<str:id>', AcceptWorkerView.as_view(), name="accept_worker"),
    path('workers/<str:sort_term>/<str:algorithm>/<int:count>/<int:page>', WorkersListView.as_view()),
    path('workers/<int:count>/<int:page>', WorkersListView.as_view()),
    path('workers/<int:count>/<int:page>/<str:search_term>', WorkersListView.as_view()),
    path('<str:state>/workers/<str:sort_term>/<str:algorithm>/<int:count>/<int:page>', WorkersListView.as_view()),
    path('<str:state>/workers/<int:count>/<int:page>', WorkersListView.as_view()),
    path('<str:state>/workers/<int:count>/<int:page>/<str:search_term>', WorkersListView.as_view()),
    path('admin/workers/profile/<str:user_id>', WorkerProfileDetailView.as_view(), name='worker_profile_detail'),

    # Customers
    path('customers/create', CreateCustomerView.as_view(), name="create_customer"),
    path('customers', CustomersListView.as_view(), name="customers_list"),
    path('customers/<str:sort_term>/<str:algorithm>/<int:count>/<int:page>', CustomersListView.as_view()),
    path('customers/<int:count>/<int:page>', CustomersListView.as_view()),
    path('customers/<int:count>/<int:page>/<str:search_term>', CustomersListView.as_view()),
    path('customers/details/<str:id>', CustomerDetailView.as_view(), name="customer_detail"),
    path('customers/<str:search_term>', CustomerSearchTermView.as_view(), name="customer_search_term"),
]
