"""Routage racine Holystyl."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from billing.webhook import stripe_webhook
from core.views import service_worker

urlpatterns = [
    path("sw.js", service_worker, name="service-worker"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("api/stripe/webhook/", stripe_webhook, name="stripe-webhook"),
    path("api/", include("config.api_urls")),
    path("", include("exploitations.urls")),
    path("", include("parcelles.urls")),
    path("", include("agronomie.urls")),
    path("", include("iot.urls")),
    path("", include("irrigation.urls")),
    path("", include("ia.urls")),
    path("", include("notifications.urls")),
    path("", include("equipe.urls")),
    path("", include("planning.urls")),
    path("", include("operations.urls")),
    path("", include("analyses.urls")),
    path("", include("finances.urls")),
    path("", include("administration.urls")),
    path("", include("core.urls")),
    path("", include("public.urls")),  # home "" en dernier
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
