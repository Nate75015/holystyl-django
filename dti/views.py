"""Écrans des diagnostics reçus de Cultiveau.

L'essentiel de la chaîne est automatique. Reste un geste que personne ne peut
automatiser : décider de quelle exploitation relève un diagnostic dont le SIRET
n'est connu de personne. C'est l'objet de ces écrans.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation

from .importation import rattacher
from .models import DtiImport


def _exploitations_de(user):
    return Exploitation.objects.filter(owner=user).order_by("name")


@login_required
def liste(request):
    """Diagnostics reçus, les dossiers en attente d'abord.

    Un import en quarantaine n'est pas une erreur mais une question posée à un
    humain : il est donc mis en tête, pas relégué dans un journal.
    """
    imports = (DtiImport.objects
               .select_related("exploitation")
               .order_by("statut", "-recu_le"))
    quarantaine = [i for i in imports if i.en_quarantaine]
    traites = [i for i in imports if not i.en_quarantaine]
    return render(request, "dti/liste.html", {
        "quarantaine": quarantaine,
        "traites": traites[:50],
    })


@login_required
def detail(request, pk):
    """Aperçu d'un diagnostic avant rattachement.

    On montre ce que le payload contient réellement — nombre de parcelles, de
    ressources, d'équipements — plutôt que de demander à l'opérateur de
    rattacher à l'aveugle un dossier identifié par un seul numéro.
    """
    dti_import = get_object_or_404(DtiImport.objects.select_related("exploitation"), pk=pk)
    contenu = dti_import.payload.get("dti") or {}
    indicateurs = dti_import.payload.get("indicateurs") or {}

    apercu = [
        (_("parcelles"), len(contenu.get("parcelles") or [])),
        (_("ressources en eau"), len(contenu.get("ressources_eau") or [])),
        (_("canalisations"), len(contenu.get("canalisations") or [])),
        (_("équipements"), len(contenu.get("equipements") or [])),
        (_("médias"), len(dti_import.payload.get("medias") or [])),
    ]
    exploitation_source = contenu.get("exploitation") or {}

    return render(request, "dti/detail.html", {
        "import": dti_import,
        "apercu": apercu,
        "indicateurs": indicateurs,
        "source": exploitation_source,
        "exploitations": _exploitations_de(request.user),
    })


@login_required
@require_POST
def rattachement(request, pk):
    """Lie un diagnostic à une exploitation, puis lance l'import."""
    dti_import = get_object_or_404(DtiImport, pk=pk)
    exploitation = get_object_or_404(
        Exploitation, pk=request.POST.get("exploitation"), owner=request.user)

    if not dti_import.en_quarantaine:
        messages.warning(request, _("Ce diagnostic est déjà rattaché."))
        return redirect("dti:detail", pk=pk)

    try:
        rapport = rattacher(dti_import, exploitation)
    except Exception as exc:
        # Le rattachement est le geste d'un opérateur : l'échec doit lui
        # revenir en clair, pas se perdre dans un journal.
        dti_import.refresh_from_db()
        dti_import.statut = DtiImport.Statut.ERREUR
        dti_import.erreur = f"{type(exc).__name__}: {exc}"
        dti_import.save(update_fields=["statut", "erreur", "updated_at"])
        messages.error(request, _("L'import a échoué : %(erreur)s") % {"erreur": exc})
        return redirect("dti:detail", pk=pk)

    total = sum(v for v in rapport.values() if isinstance(v, int))
    messages.success(request, _(
        "Diagnostic rattaché à %(nom)s — %(total)s objet(s) importé(s).")
        % {"nom": exploitation.name, "total": total})
    return redirect("dti:detail", pk=pk)
