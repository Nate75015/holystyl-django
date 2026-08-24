"""Tableaux de bord — un par espace (chef d'entreprise, employé, bailleur).

Une app sans modèle : un tableau de bord ne possède aucune donnée, il agrège
celles des domaines. D'où la règle qui tient tout ce module : **on appelle des
services, jamais l'ORM d'une autre app**. Sinon chaque changement de schéma
dans irrigation, iot ou equipe casserait les trois écrans d'un coup.

L'exploitation vient de `request.exploitation`, résolue par
`core.middleware.CurrentExploitationMiddleware` selon l'espace courant : un
employé et un bailleur ne sont pas propriétaires de celle qu'ils consultent.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from core import espaces as espaces_service
from core.decorators import espace_requis


def _courbe(objets, champ_date, champ_valeur, format_date, token, repli, label):
    """Met une série d'objets à la forme attendue par `partials/area_chart.html`.

    `token` est un token CSS : la courbe suit alors le thème (le canvas ne sait
    pas résoudre `var(...)`, c'est `holystyl-viz.js` qui le lit). `repli` est la
    couleur utilisée si le token est introuvable.
    """
    if not objets:
        return None
    return {
        "labels": [getattr(o, champ_date).strftime(format_date) for o in objets],
        "data": [round(getattr(o, champ_valeur), 1) for o in objets],
        "color_token": token,
        "color": repli,
        "label": label,
    }


@login_required
@espace_requis(espaces_service.EXPLOITANT, sans_espace=True)
def exploitant(request):
    """Écran Pulse : jauge DTI, météo, alertes et graphiques de l'exploitation."""
    from equipe.services import compte_membres
    from exploitations.services import compute_kpis
    from iot.services import alertes_ouvertes
    from irrigation.services import dernier_dti, serie_compteur_eau, serie_dti
    from meteo.services import villes_avec_meteo

    exploitation = request.exploitation

    return render(
        request,
        "dashboard/exploitant.html",
        {
            "page_title": "Tableau de bord",
            "exploitation": exploitation,
            "needs_onboarding": exploitation is None,
            "kpis": compute_kpis(exploitation),
            "dti": dernier_dti(exploitation),
            "dti_chart": _courbe(
                serie_dti(exploitation), "calculated_at", "score_numeric",
                "%d/%m", "--action", "#0891b2", "Score DTI",
            ),
            "water_chart": _courbe(
                serie_compteur_eau(exploitation), "reading_date", "volume_m3",
                "%d/%m", "--success", "#22c55e", "Volume eau (m³)",
            ),
            "alerts": alertes_ouvertes(exploitation),
            "meteo_villes": villes_avec_meteo(exploitation),
            "etp_count": compte_membres(exploitation),
        },
    )


@login_required
@espace_requis(espaces_service.EMPLOYE)
def employe(request):
    """Tableau de bord d'un membre d'équipe : ses tâches et son planning."""
    from equipe.services import membre_de, taches_du_membre

    membre = membre_de(request.user)

    return render(
        request,
        "dashboard/employe.html",
        {
            "page_title": "Mon espace",
            "exploitation": request.exploitation,
            "membre": membre,
            "taches": taches_du_membre(membre),
        },
    )


@login_required
@espace_requis(espaces_service.BAILLEUR)
def bailleur(request):
    """Tableau de bord d'un bailleur : les baux qu'il a consentis."""
    from client.services import partenaire_de
    from contrat.services import baux_du_bailleur, totaux_baux

    partenaire = partenaire_de(request.user, espaces_service.BAILLEUR)
    baux = baux_du_bailleur(partenaire)
    surface_totale, loyer_total = totaux_baux(baux)

    return render(
        request,
        "dashboard/bailleur.html",
        {
            "page_title": "Espace bailleur",
            "exploitation": request.exploitation,
            "partenaire": partenaire,
            "baux": baux,
            "surface_totale": surface_totale,
            "loyer_total": loyer_total,
        },
    )


@login_required
def index(request):
    """Aiguillage : renvoie vers le tableau de bord de l'espace courant.

    C'est la cible de `core:dashboard`, conservée pour ne casser aucun lien
    existant (`{% url %}` dans les templates, nav de la sidebar).
    """
    destinations = {
        espaces_service.EXPLOITANT: "dashboard:exploitant",
        espaces_service.EMPLOYE: "dashboard:employe",
        espaces_service.BAILLEUR: "dashboard:bailleur",
        # Le comptable travaille sur les comptes : son point de chute est le bilan.
        espaces_service.COMPTABLE: "finances:bilan_economique",
        # Le client n'a pas de tableau de bord : ses documents en tiennent lieu.
        espaces_service.CLIENT: "client:espace",
    }
    # Sans espace (compte fraîchement créé), l'écran exploitant porte déjà
    # l'invite d'onboarding : c'est le bon point de chute.
    return redirect(destinations.get(request.espace, "dashboard:exploitant"))


@login_required
@require_POST
def basculer(request):
    """Change l'espace actif, puis renvoie sur son tableau de bord.

    En POST : c'est un changement d'état de session, un GET le rendrait
    déclenchable depuis un lien ou un préchargement. Un espace refusé est
    silencieusement ignoré — l'aiguillage renverra sur l'espace courant.
    """
    espaces_service.definir_espace(request, request.POST.get("espace", ""))
    return redirect("core:dashboard")
