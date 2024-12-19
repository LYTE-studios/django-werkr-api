from django.urls import path
from .views import (
    JobView,
    CreateJobView,
    UpcomingJobsView,
    AllUpcomingJobsView,
    HistoryJobsView,
    GetJobsBasedOnUserView,
    TimeRegistrationView,
    SignTimeRegistrationView,
    ActiveJobList,
    DoneJobList,
    DraftJobList,
    ApplicationView,
    ApproveApplicationView,
    DenyApplicationView,
    MyApplicationsView,
    ApplicationsListView,
)


urlpatterns = [
    # Jobs
    path('jobs/details/<str:id>/', JobView.as_view()),
    path('jobs/create/', CreateJobView.as_view()),
    path('jobs/upcoming/', UpcomingJobsView.as_view()),
    path('jobs/upcoming/all/', AllUpcomingJobsView.as_view()),
    path('jobs/upcoming/all/<int:start>/<int:end>/', AllUpcomingJobsView.as_view()),
    path('jobs/history/', HistoryJobsView.as_view()),
    path('jobs/history/<int:start>/<int:end>/', HistoryJobsView.as_view()),
    path('jobs/get/', GetJobsBasedOnUserView.as_view()),
    path('jobs/timeregistration/', TimeRegistrationView.as_view()),
    path('jobs/timeregistration/<str:user_id>/', TimeRegistrationView.as_view()),
    path('jobs/timeregistration/sign/', SignTimeRegistrationView.as_view()),
    path('jobs/active/', ActiveJobList.as_view()),
    path('jobs/done/', DoneJobList.as_view()),
    path('jobs/done/<int:start>/<int:end>/', DoneJobList.as_view()),
    path('jobs/drafts/', DraftJobList.as_view()),

    path('applications/details/<str:id>/', ApplicationView.as_view()),
    path('applications/details/<str:id>/approve/', ApproveApplicationView.as_view()),
    path('applications/details/<str:id>/deny/', DenyApplicationView.as_view()),
    path('applications/me/', MyApplicationsView.as_view()),
    path('applications/', ApplicationsListView.as_view()),
    path('applications/<str:job_id>/', ApplicationsListView.as_view()),
]

