# src/api/urls.py
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

# Schema view for Swagger documentation
schema_view = get_schema_view(
    openapi.Info(
        title="Werkr API",
        default_version='v1',
        description="API documentation for Werkr",
        terms_of_service="https://www.lytestudios.be",
        contact=openapi.Contact(email="hello@lytestudios.be"),
        license=openapi.License(name="Private License"),
    ),
    public=True,
    permission_classes=[permissions.AllowAny],
)

# API URLs
api_v1_patterns = [
    path('auth/', include('apps.authentication.urls')),
    path('', include('apps.jobs.urls')),
]

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API versions
    path('api/v1/', include(api_v1_patterns)),
    
    # Swagger documentation
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.MEDIA_ROOT)
