"""Vues web opérations : parc matériel."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from client.models import Partenaire
from exploitations.models import Exploitation

from .marques import MARQUE_AUTRE, marques_par_famille
from .materiel import (CHOIX_GROUPES, FAMILLE_PAR_TYPE, TYPES_PAR_FAMILLE, Famille,
                       TypeMateriel, famille_de)
from .models import Machine


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").replace(" ", "").strip())
    except (TypeError, ValueError):
        return default


def _to_int(value):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _to_date(value):
    """Une date d'`<input type="date">`, ou rien si le champ est vide ou illisible."""
    return parse_date((value or "").strip()) or None


def _marque(request):
    """La marque retenue : celle de la liste, ou celle saisie si « Autre marque… ».

    La sentinelle n'est qu'un signal d'interface, elle ne descend jamais en base.
    """
    choisie = (request.POST.get("brand") or "").strip()
    if choisie in ("", MARQUE_AUTRE):
        return (request.POST.get("brand_autre") or "").strip()[:100]
    return choisie[:100]


def _detention(request, exploitation):
    """Le mode de détention, et le tiers propriétaire s'il y en a un.

    Le propriétaire est cherché parmi les relations de cette exploitation :
    un POST forgé ne peut pas rattacher l'engin à la CUMA du voisin.
    """
    detention = request.POST.get("detention") or Machine.Detention.PROPRE
    if detention not in Machine.Detention.values:
        detention = Machine.Detention.PROPRE

    proprietaire = None
    if detention != Machine.Detention.PROPRE:
        pk = _to_int(request.POST.get("proprietaire"))
        if pk is not None:
            proprietaire = Partenaire.objects.filter(pk=pk, exploitation=exploitation).first()
    return detention, proprietaire


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


def _par_famille(machines):
    """Range les machines par famille, dans l'ordre du vocabulaire.

    Un parc mélange le tracteur, la herse et la station météo ; les afficher
    à la file n'aiderait personne. Les familles vides ne s'affichent pas.
    """
    groupes = {famille: [] for famille in TYPES_PAR_FAMILLE}
    for machine in machines:
        groupes[famille_de(machine.type)].append(machine)
    return [(Famille(f).label, lot) for f, lot in groupes.items() if lot]


@login_required
def parc_materiel(request):
    exploitation = _exploitation(request)
    machines = (
        Machine.objects.filter(exploitation=exploitation)
        if exploitation else Machine.objects.none()
    )
    return render(request, "operations/parc_materiel.html", {
        "machines": machines,
        "familles": _par_famille(machines),
        "choix_types": CHOIX_GROUPES,
        "statuts": Machine.Status.choices,
        # Les marques suggérées suivent le type choisi : la page les filtre
        # côté navigateur, d'où ces deux tables passées en JSON.
        "detentions": Machine.Detention.choices,
        # Les relations de la ferme, pour désigner la CUMA, le loueur ou l'ETA.
        "partenaires": [
            {"id": p.pk, "nom": p.nom, "type": p.type_partenaire}
            for p in Partenaire.objects.filter(exploitation=exploitation)
        ] if exploitation else [],
        "marques_par_famille": marques_par_famille(),
        "famille_par_type": {t.value: FAMILLE_PAR_TYPE[t].value for t in TypeMateriel},
        "page_title": _("Parc matériel"),
    })


@login_required
@require_POST
def machine_create(request):
    exploitation = _exploitation(request)
    nom = (request.POST.get("name") or "").strip()
    type_materiel = request.POST.get("type") or ""
    statut = request.POST.get("status") or Machine.Status.OPERATIONAL

    if exploitation and nom and type_materiel in TypeMateriel.values:
        if statut not in Machine.Status.values:
            statut = Machine.Status.OPERATIONAL
        detention, proprietaire = _detention(request, exploitation)
        Machine.objects.create(
            exploitation=exploitation,
            name=nom[:255],
            type=type_materiel,
            brand=_marque(request),
            model=(request.POST.get("model") or "").strip()[:100],
            serial_number=(request.POST.get("serial_number") or "").strip()[:100],
            purchase_date=_to_date(request.POST.get("purchase_date")),
            total_hours=_to_float(request.POST.get("total_hours"), 0) or 0,
            status=statut,
            detention=detention,
            proprietaire=proprietaire,
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("operations:parc_materiel")


@login_required
@require_POST
def machine_delete(request, pk):
    exploitation = _exploitation(request)
    get_object_or_404(Machine, pk=pk, exploitation=exploitation).delete()
    return redirect("operations:parc_materiel")
