from django.contrib import admin
from django.urls import path
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

from api.routes import api


@api.get("/", summary="API Root", tags=["Home"], include_in_schema=False)
def root(request):
    return {"message": "Welcome to Speedpay API! See the docs at docs/"}


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", api.urls),
    path(
        "favicon.ico",
        serve,
        {"path": "favicon.ico", "document_root": settings.BASE_DIR},
    ),
    path("", RedirectView.as_view(url="api/docs/", permanent=False)),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
