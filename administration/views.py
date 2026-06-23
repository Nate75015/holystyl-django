"""Vue web : espace Admin (configuration SMTP & emails)."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .models import SmtpConfig


@login_required
def admin_panel(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    cfg = SmtpConfig.objects.filter(exploitation=exploitation).first()

    if request.method == "POST" and exploitation:
        SmtpConfig.objects.update_or_create(
            exploitation=exploitation,
            defaults={
                "host": request.POST.get("host", ""),
                "port": int(request.POST.get("port") or 587),
                "secure": request.POST.get("secure") == "on",
                "user": request.POST.get("user", ""),
                "password": request.POST.get("password", ""),
                "from_name": request.POST.get("from_name", "Holystyl"),
                "from_email": request.POST.get("from_email", ""),
                "enabled": request.POST.get("enabled", "on") == "on",
            },
        )
        messages.success(request, _("Configuration SMTP enregistrée."))
        return redirect("administration:admin_panel")

    return render(request, "administration/admin.html", {"cfg": cfg, "page_title": _("Administration")})
