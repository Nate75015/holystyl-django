from django.urls import path

from . import views

app_name = "irrigation"

urlpatterns = [
    path("irrigation/", views.irrigation, name="irrigation"),
    path("bassinage/", views.bassinage, name="bassinage"),
]
