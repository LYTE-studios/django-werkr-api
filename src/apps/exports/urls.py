from .views import ExportsView
from django.urls import path


urlpatterns = [
    # Exports
    path("", ExportsView.as_view()),
    path(
        "/<str:sort_term>/<str:algorithm>/<int:count>/<int:page>", ExportsView.as_view()
    ),
    path("/<int:count>/<int:page>", ExportsView.as_view()),
    path("/<int:count>/<int:page>/<str:search_term>", ExportsView.as_view()),
]
