"""Middleware multi-tenant : attache l'exploitation courante à la requête.

La résolution passe par l'espace actif (`core.espaces`) : un employé ou un
bailleur n'est pas propriétaire de l'exploitation qu'il consulte, chercher un
`owner=user` ne suffit donc pas.

Reste défensif : tant qu'aucun rattachement n'existe (compte fraîchement créé,
avant l'onboarding), `request.exploitation` vaut None et `request.espace` aussi.
"""

from django.core.exceptions import PermissionDenied
from django.utils.translation import gettext as _

from . import espaces as espaces_service

#: Routes que tout espace doit garder, quel que soit son périmètre : se
#: déconnecter, changer d'espace, changer de langue ou de thème.
ROUTES_TECHNIQUES = frozenset({
    "accounts:logout",
    "dashboard:basculer",
    "core:set_language",
    "set_language",
})


class CurrentExploitationMiddleware:
    """Rend `request.espace` et `request.exploitation` disponibles partout.

    Résolus directement, et non via `SimpleLazyObject` : un objet paresseux
    enveloppant None ne répond pas à `is None`, ce qui en fait un piège pour
    tout le code appelant. La résolution tient en trois requêtes indexées, et
    zéro pour un visiteur anonyme.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.espace = espaces_service.espace_courant(request)
        request.exploitation = espaces_service.exploitation_de(request)
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        """Ferme les espaces externes à tout ce qui ne leur est pas ouvert.

        Le filtrage de navigation masque des entrées ; ici on refuse. La règle
        ne vaut que pour les espaces marqués fermés (`espaces.EST_FERME`) :
        pour eux, la liste autorisée fait loi, une vue oubliée reste inaccessible
        plutôt que de fuiter. Les espaces internes gardent le comportement
        historique — leurs vues sensibles se protègent une à une avec
        `@espace_requis`.
        """
        espace = getattr(request, "espace", None)
        if not espaces_service.est_ferme(espace):
            return None

        resolution = getattr(request, "resolver_match", None)
        if resolution is None:
            return None
        autorisees = espaces_service.nav_autorisee(espace) or set()
        ouvertes = autorisees | espaces_service.ROUTES_COMMUNES | ROUTES_TECHNIQUES
        if resolution.view_name in ouvertes:
            return None
        raise PermissionDenied(
            _("Cette page n'est pas accessible depuis l'espace %(espace)s.")
            % {"espace": espaces_service.libelle(espace)}
        )
