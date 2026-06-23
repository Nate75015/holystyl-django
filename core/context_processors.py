"""Variables injectées dans tous les templates (navigation, branding)."""

from django.conf import settings
from django.utils.translation import gettext_lazy as _


def layout(request):
    """Structure de navigation de la sidebar + branding.

    La navigation reflète les modules de l'app React (cf. MIGRATION_PLAN §2).
    Les liens dont la route n'existe pas encore (tranches suivantes) pointent
    vers "#" et seront activés au fur et à mesure.
    """
    nav_primary = [
        {"label": _("Pulse"), "url_name": "core:dashboard", "icon": "activity"},
        {"label": _("Parcelles"), "url_name": None, "icon": "map"},
        {"label": _("Irrigation"), "url_name": None, "icon": "droplet"},
        {"label": _("Capteurs"), "url_name": None, "icon": "radio"},
        {"label": _("Assistant"), "url_name": None, "icon": "sparkles"},
    ]
    nav_sections = [
        {"label": _("Cultures & Terrain"), "items": [_("Parcelles"), _("Cultures & Kc"), _("Types de sol")]},
        {"label": _("Protection"), "items": [_("Anti-gel"), _("Santé végétale"), _("Protection")]},
        {"label": _("Économie"), "items": [_("Charges"), _("Bilan économique"), _("Facturation")]},
        {"label": _("Environnement"), "items": [_("Bilan eau"), _("Empreinte carbone"), _("Durabilité")]},
        {"label": _("Planning & Équipe"), "items": [_("Planning"), _("Équipe"), _("Tâches")]},
    ]
    return {
        "APP_NAME": getattr(settings, "APP_NAME", "Holystyl"),
        "nav_primary": nav_primary,
        "nav_sections": nav_sections,
    }
