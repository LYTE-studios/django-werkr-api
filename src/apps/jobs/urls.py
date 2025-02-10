from django.urls import path

from .views import (
    DirectionsView,
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
    path("jobs/details/<str:id>", JobView.as_view(), name="job-details"),
    path("jobs/create", CreateJobView.as_view(), name="create-job"),
    path("jobs/upcoming", UpcomingJobsView.as_view(), name="upcoming-jobs"),
    path("jobs/upcoming/all", AllUpcomingJobsView.as_view(), name="all-upcoming-jobs"),
    path("jobs/upcoming/all/<int:start>/<int:end>", AllUpcomingJobsView.as_view()),
    path("jobs/history", HistoryJobsView.as_view(), name="history-jobs"),
    path("jobs/history/<int:start>/<int:end>", HistoryJobsView.as_view()),
    path("jobs/get", GetJobsBasedOnUserView.as_view(), name="get-jobs-based-on-user"),
    path("jobs/timeregistration/<str:job_id>", TimeRegistrationView.as_view()),
    path(
        "jobs/timeregistration/sign",
        SignTimeRegistrationView.as_view(),
        name="sign-time-registration",
    ),
    path("jobs/active", ActiveJobList.as_view(), name="active-job-list"),
    path("jobs/done", DoneJobList.as_view(), name="done-job-list"),
    path("jobs/done/<int:start>/<int:end>", DoneJobList.as_view()),
    path("jobs/drafts", DraftJobList.as_view(), name="draft-job-list"),
    path(
        "applications/details/<str:id>",
        ApplicationView.as_view(),
        name="application-details",
    ),
    path(
        "applications/details/<str:id>/approve",
        ApproveApplicationView.as_view(),
        name="approve-application",
    ),
    path(
        "applications/details/<str:id>/deny",
        DenyApplicationView.as_view(),
        name="deny-application",
    ),
    path("applications/me", MyApplicationsView.as_view(), name="my-applications"),
    path("applications", ApplicationsListView.as_view()),
    path(
        "applications/<str:job_id>",
        ApplicationsListView.as_view(),
        name="applications-list",
    ),
    path(
        "directions/<int:from_lat>/<int:from_lon>/<int:to_lat>/<int:to_lon>",
        DirectionsView.as_view(),
        name="directions-view",
    ),
]
