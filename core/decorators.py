"""Contrôle d'accès par espace.

Le filtrage de `core.context_processors.layout` masque les entrées de nav d'un
espace à l'autre, mais masquer n'est pas interdire : l'URL reste tapable. Ce
décorateur est ce qui interdit réellement.
"""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _

from . import espaces as espaces_service


def _libelles(cles):
    """« Chef d'entreprise ou Bailleur » — pour le message de refus."""
    noms = [str(e["label"]) for e in espaces_service.ESPACES if e["cle"] in cles]
    if len(noms) <= 1:
        return noms[0] if noms else ""
    return f"{', '.join(noms[:-1])} {_('ou')} {noms[-1]}"


def espace_requis(*autorises, sans_espace=False):
    """Restreint une vue aux espaces donnés.

    Le contrôle porte sur l'espace **actif**, pas sur les droits : un compte
    relevant à la fois de « chef d'entreprise » et « employé » n'accède aux
    pages RH que depuis le premier. C'est voulu — `request.exploitation` est
    résolue selon l'espace actif, servir une page hors de son espace donnerait
    un écran incohérent.

    `sans_espace=True` laisse aussi passer les comptes qui n'ont encore aucun
    rattachement (`request.espace is None`), c'est-à-dire ceux qui n'ont pas
    fait l'onboarding : sans quoi ils seraient enfermés dehors par la page même
    qui doit les accueillir.

    Les espaces sont validés à l'import : une faute de frappe casse au
    démarrage, pas au premier accès à la vue.
    """
    if not autorises:
        raise ValueError("espace_requis attend au moins un espace")
    inconnus = sorted(set(autorises) - set(espaces_service.ORDRE))
    if inconnus:
        raise ValueError(f"espace(s) inconnu(s) : {', '.join(inconnus)}")

    def decorateur(vue):
        @wraps(vue)
        def _vue(request, *args, **kwargs):
            user = getattr(request, "user", None)
            if user is None or not user.is_authenticated:
                # Même comportement que @login_required : on renvoie vers la
                # connexion plutôt que de répondre 403 à un simple visiteur.
                return redirect_to_login(request.get_full_path())

            espace = getattr(request, "espace", None)
            if espace in autorises or (espace is None and sans_espace):
                return vue(request, *args, **kwargs)

            raise PermissionDenied(
                _("Cette page appartient à l'espace %(requis)s.") % {"requis": _libelles(autorises)}
            )

        return _vue

    return decorateur
