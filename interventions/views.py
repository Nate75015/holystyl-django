"""Vues web interventions : journal des opérations culturales."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from parcelles.models import Parcelle

from .models import Intervention


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def interventions(request):
    exploitation = _exploitation(request)
    items = (
        Intervention.objects.filter(exploitation=exploitation).select_related("parcelle")
        if exploitation
        else Intervention.objects.none()
    )
    counts = {"irrigation": 0, "traitement": 0, "fertilisation": 0, "recolte": 0}
    data = []
    for it in items:
        if it.intervention_type in counts:
            counts[it.intervention_type] += 1
        data.append({
            "type": it.intervention_type,
            "typeLabel": it.get_intervention_type_display(),
            "title": it.title or it.get_intervention_type_display(),
            "date": it.start_time.strftime("%d/%m/%Y %H:%M") if it.start_time else "",
            "parcelle": it.parcelle.name if it.parcelle else "",
            "status": it.get_status_display(),
        })
    parcelles = Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none()
    return render(request, "interventions/interventions.html", {
        "interventions_json": data,
        "counts": counts,
        "total": len(data),
        "parcelles": parcelles,
        "types": Intervention.Type.choices,
        "statuses": Intervention.Status.choices,
        "page_title": _("Interventions"),
    })


@login_required
@require_POST
def intervention_create(request):
    exploitation = _exploitation(request)
    itype = request.POST.get("intervention_type")
    if exploitation and itype:
        start = parse_datetime(request.POST.get("start_time") or "") or timezone.now()
        if timezone.is_naive(start):
            start = timezone.make_aware(start)
        parcelle = Parcelle.objects.filter(pk=request.POST.get("parcelle"), exploitation=exploitation).first()
        Intervention.objects.create(
            exploitation=exploitation,
            parcelle=parcelle,
            user=request.user,
            intervention_type=itype,
            title=(request.POST.get("title") or "").strip(),
            status=request.POST.get("status") or Intervention.Status.PLANIFIEE,
            start_time=start,
            product=(request.POST.get("product") or "").strip(),
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("interventions:interventions")
