"""Middleware multi-tenant : attache l'exploitation courante à la requête.

La résolution passe par l'espace actif (`core.espaces`) : un employé ou un
bailleur n'est pas propriétaire de l'exploitation qu'il consulte, chercher un
`owner=user` ne suffit donc pas.

Reste défensif : tant qu'aucun rattachement n'existe (compte fraîchement créé,
avant l'onboarding), `request.exploitation` vaut None et `request.espace` aussi.
"""

from . import espaces as espaces_service


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
