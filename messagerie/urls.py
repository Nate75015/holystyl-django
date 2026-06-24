from django.urls import path

from . import views

app_name = "messagerie"

urlpatterns = [
    path("messagerie/", views.inbox, name="inbox"),
    path("messagerie/nouvelle/", views.new, name="new"),
    path("messagerie/avec/<int:user_id>/", views.start, name="start"),
    path("messagerie/reformuler/", views.reformulate, name="reformulate"),
    path("messagerie/<int:pk>/", views.detail, name="detail"),
    path("messagerie/<int:pk>/fil/", views.thread, name="thread"),
    path("messagerie/<int:pk>/envoyer/", views.send, name="send"),
]
