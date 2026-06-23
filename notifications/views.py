"""Vue web : centre de notifications."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils.translation import gettext as _

from .models import Notification, NotificationRule


@login_required
def center(request):
    return render(
        request,
        "notifications/center.html",
        {
            "notifications": Notification.objects.filter(user=request.user)[:100],
            "rules": NotificationRule.objects.filter(user=request.user),
            "page_title": _("Notifications"),
        },
    )
