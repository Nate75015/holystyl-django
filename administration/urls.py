from django.urls import path

from . import views

app_name = "administration"

urlpatterns = [
    path("admin-panel/", views.admin_panel, name="admin_panel"),
]
