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
)


urlpatterns = [
    # Jobs
    path('details/<str:id>', JobView.as_view()),
    path('create', CreateJobView.as_view()),
    path('upcoming', UpcomingJobsView.as_view()),
    path('upcoming/all', AllUpcomingJobsView.as_view()),
    path('upcoming/all/<int:start>/<int:end>', AllUpcomingJobsView.as_view()),
    path('history', HistoryJobsView.as_view()),
    path('history/<int:start>/<int:end>', HistoryJobsView.as_view()),
    path('get', GetJobsBasedOnUserView.as_view()),
    path('timeregistration', TimeRegistrationView.as_view()),
    path('timeregistration/<str:user_id>', TimeRegistrationView.as_view()),
    path('timeregistration/sign', SignTimeRegistrationView.as_view()),
    path('active', ActiveJobList.as_view()),
    path('done', DoneJobList.as_view()),
    path('done/<int:start>/<int:end>', DoneJobList.as_view()),
    path('drafts', DraftJobList.as_view()),
]

