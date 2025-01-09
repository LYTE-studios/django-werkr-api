from django.urls import path
from .views import DownloadContractView

urlpatterns = [
    path('download_contract/<uuid:id>/', DownloadContractView.as_view(), name='download_contract'),
]
