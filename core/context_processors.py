"""Variables injectées dans tous les templates (navigation, branding)."""

from django.conf import settings
from django.utils.translation import gettext_lazy as _


def layout(request):
    """Structure de navigation de la sidebar + branding.

    Reflète les modules de l'app React (cf. MIGRATION_PLAN §2). Les liens dont
    la route n'existe pas encore (tranches suivantes) valent `None` et sont
    rendus désactivés.
    """
    nav_primary = [
        {"label": _("Pulse"), "url_name": "core:dashboard", "icon": "activity"},
        {"label": _("Parcelles"), "url_name": "parcelles:list", "icon": "map"},
        {"label": _("Irrigation"), "url_name": None, "icon": "droplet"},
        {"label": _("Capteurs"), "url_name": None, "icon": "radio"},
        {"label": _("Assistant"), "url_name": None, "icon": "sparkles"},
    ]
    nav_sections = [
        {
            "label": _("Cultures & Terrain"),
            "items": [
                {"label": _("Parcelles"), "url_name": "parcelles:list"},
                {"label": _("Cultures & Kc"), "url_name": "agronomie:cultures_kc"},
                {"label": _("Types de sol"), "url_name": "agronomie:types_sol"},
                {"label": _("Saisons"), "url_name": "agronomie:saisons"},
            ],
        },
        {
            "label": _("Mon compte"),
            "items": [
                {"label": _("Mon exploitation"), "url_name": "exploitations:settings"},
            ],
        },
    ]
    return {
        "APP_NAME": getattr(settings, "APP_NAME", "Holystyl"),
        "nav_primary": nav_primary,
        "nav_sections": nav_sections,
    }
