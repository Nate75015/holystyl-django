from django.urls import path

from . import views

app_name = "iot"

urlpatterns = [
    path("regie/", views.regie, name="regie"),
    path("capteurs/", views.capteurs, name="capteurs"),
]
