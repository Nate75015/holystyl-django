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
from django.utils import timezone
from django.utils.translation import gettext as _
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
@espace_requis(espaces_service.EMPLOYE, ou_profil_declare=True)
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
            "consigne": espaces_service.CONSIGNE_RATTACHEMENT[espaces_service.EMPLOYE],
            "taches": taches_du_membre(membre),
        },
    )


@login_required
@espace_requis(espaces_service.BAILLEUR, ou_profil_declare=True)
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
            "consigne": espaces_service.CONSIGNE_RATTACHEMENT[espaces_service.BAILLEUR],
            "baux": baux,
            "surface_totale": surface_totale,
            "loyer_total": loyer_total,
        },
    )


@login_required
@espace_requis(espaces_service.COMPTABLE, ou_profil_declare=True)
def comptable(request):
    """Tableau de bord d'un comptable : l'exercice de l'exploitation qu'il suit.

    Il regarde des flux, pas des parcelles : ce qui a été facturé, ce qui reste
    à encaisser, la TVA collectée et les charges de l'exercice. Les montants
    viennent des mêmes sources que le bilan — on ne recalcule pas une seconde
    vérité à côté.
    """
    from client.services import partenaire_de
    from finances.models import Charge, Devis, Facture
    from finances.services import compute_bilan

    exploitation = request.exploitation
    annee = timezone.localdate().year
    factures = Facture.objects.filter(exploitation=exploitation, date_emission__year=annee)

    encaisse = sum(f.montant_ttc for f in factures if f.statut == Facture.Statut.PAYEE)
    attente = sum(f.montant_ttc for f in factures if f.statut == Facture.Statut.EN_ATTENTE)
    retard = [f for f in factures if f.statut == Facture.Statut.EN_RETARD]

    # Les charges par poste : c'est la ventilation qu'un comptable saisit.
    charges = Charge.objects.filter(exploitation=exploitation, date__year=annee)
    par_poste = {}
    for charge in charges:
        par_poste[charge.get_categorie_display()] = par_poste.get(charge.get_categorie_display(), 0) + charge.montant
    postes = sorted(par_poste.items(), key=lambda kv: -kv[1])[:6]

    return render(request, "dashboard/comptable.html", {
        "page_title": _("Espace comptable"),
        "partenaire": partenaire_de(request.user, espaces_service.COMPTABLE),
        "consigne": espaces_service.CONSIGNE_RATTACHEMENT[espaces_service.COMPTABLE],
        "exploitation": exploitation,
        "annee": annee,
        "bilan": compute_bilan(exploitation, annee),
        "facture_total": round(sum(f.montant_ttc for f in factures), 2),
        "facture_encaisse": round(encaisse, 2),
        "facture_attente": round(attente, 2),
        "factures_en_retard": retard,
        "tva_collectee": round(sum(f.montant_tva for f in factures), 2),
        "postes": postes,
        # Un devis signé mais pas encore facturé, c'est du produit à venir.
        "devis_a_facturer": [d for d in Devis.objects.filter(exploitation=exploitation) if d.convertible],
        "dernieres_factures": factures.order_by("-date_emission")[:8],
    })


@login_required
def index(request):
    """Aiguillage : renvoie vers le tableau de bord de l'espace courant.

    C'est la cible de `core:dashboard`, conservée pour ne casser aucun lien
    existant (`{% url %}` dans les templates, nav de la sidebar).
    """
    if request.espace:
        return redirect(espaces_service.tableau_de_bord(request.espace))

    # Aucun rattachement : le compte n'a pas été invité. On lui demande qui il
    # est plutôt que de supposer un chef d'entreprise — et s'il l'a déjà dit,
    # on l'envoie sur le tableau de bord de ce profil, qui l'accueille vide et
    # lui indique ce qui manque.
    profil = getattr(request.user, "profil_souhaite", "")
    if not profil:
        return redirect("accounts:choix_profil")
    return redirect(espaces_service.tableau_de_bord(profil))


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
