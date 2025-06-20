from django.urls import path

from .views import (
    DimonaListView,
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
    ReverseGeocodeView,
    GeocodeView,
    AutocompleteView,
    WorkersForJobView,
    AdminStatisticsView,
    ExportsView,
    CustomerJobHistoryView,
    WasherJobHistoryView,
    TagView,
    TagListView,
)

urlpatterns = [
    # Jobs
    path('jobs/details/<str:id>', JobView.as_view(), name="job-details"),
    path('jobs/create', CreateJobView.as_view(), name="create-job"),
    path('jobs/upcoming', UpcomingJobsView.as_view(), name="upcoming-jobs"),
    path('jobs/upcoming/all', AllUpcomingJobsView.as_view(), name="all-upcoming-jobs"),
    path('jobs/upcoming/all/<int:start>/<int:end>', AllUpcomingJobsView.as_view()),
    path('jobs/history', HistoryJobsView.as_view(), name="history-jobs"),
    path('jobs/history/<int:start>/<int:end>', HistoryJobsView.as_view()),
    path('jobs/get', GetJobsBasedOnUserView.as_view(), name="get-jobs-based-on-user"),
    path('jobs/timeregistration/<str:job_id>', TimeRegistrationView.as_view()),
    path('jobs/timeregistration/<str:job_id>/<str:user_id>', TimeRegistrationView.as_view()),
    path('jobs/timeregistration/sign', SignTimeRegistrationView.as_view(), name="sign-time-registration"),
    path('jobs/active', ActiveJobList.as_view(), name="active-job-list"),
    path('jobs/done', DoneJobList.as_view(), name="done-job-list"),
    path('jobs/done/<int:start>/<int:end>', DoneJobList.as_view()),
    path('jobs/drafts', DraftJobList.as_view(), name="draft-job-list"),
    path("jobs/<str:id>/workers", WorkersForJobView.as_view()),
    path('history/customers/<str:customer_id>', CustomerJobHistoryView.as_view(), name="customer-job-history"),
    path('history/customers/<str:customer_id>/<int:count>/<int:page>', CustomerJobHistoryView.as_view()),
    path('history/washers/<str:worker_id>', WasherJobHistoryView.as_view(), name="washer-job-history"),
    path('history/washers/<str:worker_id>/<int:count>/<int:page>', WasherJobHistoryView.as_view()),

    path("statistics/overview/<int:start>/<int:end>", AdminStatisticsView.as_view()),

    path('applications/details/<str:id>', ApplicationView.as_view(), name="application-details"),
    path('applications/details/<str:id>/approve', ApproveApplicationView.as_view(), name="approve-application"),
    path('applications/details/<str:id>/deny', DenyApplicationView.as_view(), name="deny-application"),
    path('applications/me', MyApplicationsView.as_view(), name="my-applications"),
    path('applications', ApplicationsListView.as_view()),
    path('applications/<str:job_id>', ApplicationsListView.as_view(), name="applications-list"),

    path('directions/<str:from_lat>/<str:from_lon>/<str:to_lat>/<str:to_lon>', DirectionsView.as_view(), name="directions-view"),
    path('reverse_geocode/<str:query>', ReverseGeocodeView.as_view(), name="reverse_geocode"),
    path('geocode/<str:query>', GeocodeView.as_view(), name="geocode"),
    path('autocomplete/<str:query>', AutocompleteView.as_view(), name="autocomplete"),
    
    path('dimonas/<int:count>/<int:page>', DimonaListView.as_view(), name="dimonas-list"),

    path("exports", ExportsView.as_view()),
    path(
        "exports/<str:sort_term>/<str:algorithm>/<int:count>/<int:page>",
        ExportsView.as_view(),
    ),
    path("exports/<int:count>/<int:page>", ExportsView.as_view()),
    path("exports/<int:count>/<int:page>/<str:search_term>", ExportsView.as_view()),

    # Tags
    path('tags', TagListView.as_view(), name='tag-list'),
    path('tags/<str:id>', TagView.as_view(), name='tag-detail'),
]

