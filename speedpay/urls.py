from functools import partial

from django.contrib import admin
from django.urls import path
from django.views.generic.base import RedirectView
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve

from ninja.openapi.views import openapi_view

from api.routes import api


@api.get("/", summary="API Root", tags=["Home"], include_in_schema=False)
def root(request):
    return {"message": "Welcome to Speedpay API! See the docs at docs/"}


urlpatterns = [
    path("admin/", admin.site.urls),
    path("v1/", api.urls),
    path(
        "favicon.ico",
        serve,
        {"path": "favicon.ico", "document_root": settings.BASE_DIR},
    ),
    path("api/docs/", RedirectView.as_view(url="/docs", permanent=False)),
    path("docs/", partial(openapi_view, api=api), name="openapi-view"),
    path("", RedirectView.as_view(url="docs/", permanent=False)),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
