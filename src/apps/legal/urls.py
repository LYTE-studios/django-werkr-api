from django.urls import path
from .views import DownloadContractView, DimonaDeclarationsView, DimonaDeclarationDetailView

urlpatterns = [
    path('download_contract/<uuid:id>', DownloadContractView.as_view(), name='download_contract'),
    path('dimona/declarations/', DimonaDeclarationsView.as_view(), name='dimona_declarations'),
    path('dimona/declarations/<str:dimona_id>/', DimonaDeclarationDetailView.as_view(), name='dimona_declaration_detail'),
]
