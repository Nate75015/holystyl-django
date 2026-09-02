"""L'espace public des offres d'emploi.

Ces vues sont ouvertes : aucun compte n'est requis pour consulter une offre ni
pour y répondre. C'est le seul endroit de l'application où un anonyme dépose un
fichier, d'où le contrôle serré du CV — extension, taille, et rien d'autre.

Elles posent `layout_nu`, sur lequel `base.html` bascule : ces pages sont une
vitrine et le restent pour tout le monde. Un agriculteur connecté qui ouvre une
offre voit la même page qu'un candidat, sans son tableau de bord autour.
"""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from notifications.services import notify

from .models import Candidature, OffreEmploi

#: Ce qu'on accepte comme CV. La liste est courte à dessein : un recrutement
#: agricole se fait avec un PDF ou un document bureautique, pas une archive.
EXTENSIONS_CV = {".pdf", ".doc", ".docx", ".odt", ".rtf", ".jpg", ".jpeg", ".png"}

#: 5 Mo : de quoi passer un CV scanné, pas de quoi servir d'hébergement.
TAILLE_MAX_CV = 5 * 1024 * 1024


def _offres_visibles():
    """Les offres en ligne, les plus récentes d'abord."""
    aujourdhui = timezone.localdate()
    return (OffreEmploi.objects
            .filter(statut=OffreEmploi.Statut.PUBLIEE)
            .exclude(expire_le__lt=aujourdhui)
            .select_related("exploitation")
            .order_by("-publiee_le", "-created_at"))


def emplois(request):
    """La liste publique des offres, toutes exploitations confondues."""
    lot = list(_offres_visibles())
    recherche = (request.GET.get("q") or "").strip()
    if recherche:
        aiguille = recherche.lower()
        lot = [o for o in lot
               if aiguille in o.titre.lower()
               or aiguille in o.lieu.lower()
               or aiguille in o.exploitation.name.lower()]
    return render(request, "equipe/emplois.html", {
        "offres": lot,
        "recherche": recherche,
        "layout_nu": True,
        "page_title": _("Offres d'emploi agricoles"),
    })


def emploi_detail(request, slug):
    """Une offre et son formulaire de candidature."""
    offre = get_object_or_404(
        OffreEmploi.objects.select_related("exploitation"), slug=slug)
    if not offre.est_visible:
        # Une offre retirée ne disparaît pas en 404 : le lien a pu être
        # partagé, on explique plutôt qu'on ne recrute plus.
        return render(request, "equipe/emploi_close.html",
                      {"offre": offre, "layout_nu": True, "page_title": offre.titre},
                      status=410)
    return render(request, "equipe/emploi_detail.html", {
        "offre": offre,
        "layout_nu": True,
        "page_title": offre.titre,
    })


def _cv_valide(fichier):
    """(ok, message) — un CV accepté est court et d'un format attendu."""
    import os

    if fichier is None:
        return True, ""
    if fichier.size > TAILLE_MAX_CV:
        return False, _("Le CV ne doit pas dépasser 5 Mo.")
    extension = os.path.splitext(fichier.name)[1].lower()
    if extension not in EXTENSIONS_CV:
        return False, _("Format de CV non accepté : PDF, Word, OpenDocument ou image.")
    return True, ""


@require_POST
def candidater(request, slug):
    """Dépose une candidature sur une offre en ligne."""
    offre = get_object_or_404(OffreEmploi, slug=slug)
    if not offre.est_visible:
        return redirect("equipe:emploi_detail", slug=slug)

    nom = (request.POST.get("nom") or "").strip()
    email = (request.POST.get("email") or "").strip()
    if not (nom and email):
        messages.error(request, _("Indiquez au moins votre nom et votre email."))
        return redirect("equipe:emploi_detail", slug=slug)

    cv = request.FILES.get("cv")
    ok, souci = _cv_valide(cv)
    if not ok:
        messages.error(request, souci)
        return redirect("equipe:emploi_detail", slug=slug)

    candidature = Candidature.objects.create(
        offre=offre, nom=nom[:255], email=email,
        telephone=(request.POST.get("telephone") or "").strip()[:30],
        message=(request.POST.get("message") or "").strip()[:5000],
        cv=cv or "")

    proprietaire = getattr(offre.exploitation, "owner", None)
    if proprietaire:
        notify(proprietaire, type="candidature",
               title=_("Nouvelle candidature"),
               message=_("%(qui)s a répondu à « %(offre)s ».") % {
                   "qui": candidature.nom, "offre": offre.titre})
    messages.success(request, _("Votre candidature est envoyée. Bonne chance !"))
    return redirect("equipe:emploi_detail", slug=slug)
