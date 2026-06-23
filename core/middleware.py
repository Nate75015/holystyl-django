"""Middleware multi-tenant : attache l'exploitation courante à la requête.

L'app `exploitations` n'existe qu'à partir de la Tranche 1. Ce middleware est
posé dès le socle de façon défensive : tant que le modèle Exploitation n'est pas
disponible (ou qu'aucune exploitation n'est rattachée à l'utilisateur), il pose
`request.exploitation = None`. La résolution réelle sera complétée en Tranche 1.
"""

from django.utils.functional import SimpleLazyObject


def _resolve_exploitation(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return None
    try:
        from exploitations.models import Exploitation  # noqa: WPS433 (import tardif voulu)
    except (ImportError, LookupError):
        return None
    return Exploitation.objects.filter(owner=user).first()


class CurrentExploitationMiddleware:
    """Rend `request.exploitation` disponible partout (résolu paresseusement)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.exploitation = SimpleLazyObject(lambda: _resolve_exploitation(request))
        return self.get_response(request)
