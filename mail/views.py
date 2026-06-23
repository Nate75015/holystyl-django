"""Vues Mail : historique des envois + composition/envoi SMTP."""

import re

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import EmailMessage
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from equipe.models import TeamMember
from exploitations.models import Exploitation

from .models import Email


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


def _parse_addresses(raw):
    """Découpe une saisie libre (virgules, points-virgules, retours) en adresses."""
    parts = [p.strip() for p in re.split(r"[,;\n]+", raw or "") if p.strip()]
    valid, invalid = [], []
    for p in parts:
        try:
            validate_email(p)
            valid.append(p)
        except ValidationError:
            invalid.append(p)
    return valid, invalid


@login_required
def outbox(request):
    emails = Email.objects.filter(sender=request.user)
    return render(request, "mail/outbox.html", {"emails": emails, "page_title": _("Mail")})


@login_required
def detail(request, pk):
    email = get_object_or_404(Email, pk=pk, sender=request.user)
    return render(request, "mail/detail.html", {"email": email, "page_title": email.subject})


@login_required
def compose(request):
    # Carnet d'adresses : e-mails des membres d'équipe de l'exploitation
    exploitation = _exploitation(request)
    contacts = []
    if exploitation:
        contacts = list(
            TeamMember.objects.filter(exploitation=exploitation)
            .exclude(email="")
            .values_list("name", "email")
        )

    if request.method == "POST":
        to_raw = request.POST.get("to", "")
        cc_raw = request.POST.get("cc", "")
        subject = (request.POST.get("subject") or "").strip()
        body = request.POST.get("body") or ""
        files = request.FILES.getlist("fichiers")

        to_list, to_invalid = _parse_addresses(to_raw)
        cc_list, cc_invalid = _parse_addresses(cc_raw)
        invalid = to_invalid + cc_invalid

        errors = []
        if not to_list:
            errors.append(_("Indiquez au moins un destinataire valide."))
        if invalid:
            errors.append(_("Adresses invalides ignorées : %(list)s") % {"list": ", ".join(invalid)})
        if not subject:
            errors.append(_("L'objet est obligatoire."))

        # On bloque seulement s'il manque destinataire ou objet ; les adresses
        # invalides sont signalées mais n'empêchent pas l'envoi aux valides.
        if not to_list or not subject:
            return render(request, "mail/compose.html", {
                "errors": errors, "contacts": contacts, "page_title": _("Nouveau mail"),
                "form": {"to": to_raw, "cc": cc_raw, "subject": subject, "body": body},
            })

        msg = EmailMessage(
            subject=subject,
            body=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            to=to_list,
            cc=cc_list or None,
            reply_to=[request.user.email] if request.user.email else None,
        )
        attach_names = []
        for f in files:
            msg.attach(f.name, f.read(), f.content_type)
            attach_names.append(f.name)

        status, error = Email.Status.SENT, ""
        try:
            msg.send(fail_silently=False)
        except Exception as exc:  # noqa: BLE001 — on journalise toute erreur SMTP
            status, error = Email.Status.FAILED, str(exc)

        Email.objects.create(
            exploitation=exploitation, sender=request.user,
            to=", ".join(to_list), cc=", ".join(cc_list),
            subject=subject, body=body, attachments=attach_names,
            status=status, error=error,
        )
        return redirect("mail:outbox")

    prefill = request.GET.get("to", "")
    return render(request, "mail/compose.html", {
        "contacts": contacts, "page_title": _("Nouveau mail"),
        "form": {"to": prefill, "cc": "", "subject": "", "body": ""},
    })
