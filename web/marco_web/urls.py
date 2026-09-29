from django.urls import include, path
from django.views.generic.base import RedirectView


urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/favicon.svg", permanent=False)),
    path("", include("workbench.urls")),
]
