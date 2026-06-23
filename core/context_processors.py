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
        {"label": _("Tableau de bord"), "url_name": "core:dashboard", "icon": "activity"},
        {"label": _("Parcelles"), "url_name": "parcelles:list", "icon": "map"},
        {"label": _("Irrigation"), "url_name": "irrigation:irrigation", "icon": "droplet"},
        {"label": _("Capteurs"), "url_name": "iot:capteurs", "icon": "radio"},
        {"label": _("Assistant"), "url_name": "ia:assistant", "icon": "sparkles"},
    ]
    nav_sections = [
        {
            "label": _("Pilotage hydrique"),
            "items": [
                {"label": _("Régie SCADA"), "url_name": "iot:regie"},
                {"label": _("Irrigation"), "url_name": "irrigation:irrigation"},
                {"label": _("Bassinage"), "url_name": "irrigation:bassinage"},
                {"label": _("Capteurs"), "url_name": "iot:capteurs"},
            ],
        },
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
            "label": _("Opérations & Analyses"),
            "items": [
                {"label": _("Parc matériel"), "url_name": "operations:parc_materiel"},
                {"label": _("Interventions"), "url_name": "operations:interventions"},
                {"label": _("Laboratoire"), "url_name": "analyses:laboratoire"},
                {"label": _("Analyses de sol"), "url_name": "analyses:analyses_sol"},
            ],
        },
        {
            "label": _("Économie"),
            "items": [
                {"label": _("Charges"), "url_name": "finances:charges"},
                {"label": _("Bilan économique"), "url_name": "finances:bilan_economique"},
                {"label": _("Facturation"), "url_name": "finances:facturation"},
            ],
        },
        {
            "label": _("Planning & Équipe"),
            "items": [
                {"label": _("Planning"), "url_name": "planning:planning"},
                {"label": _("Mes tâches"), "url_name": "equipe:mes_taches"},
                {"label": _("Équipe"), "url_name": "equipe:equipe"},
                {"label": _("Tâches"), "url_name": "equipe:taches"},
            ],
        },
        {
            "label": _("Assistant & alertes"),
            "items": [
                {"label": _("Assistant IA"), "url_name": "ia:assistant"},
                {"label": _("Notifications"), "url_name": "notifications:center"},
            ],
        },
        {
            "label": _("Mon compte"),
            "items": [
                {"label": _("Mon exploitation"), "url_name": "exploitations:settings"},
                {"label": _("Activer un code"), "url_name": "public:activer"},
                {"label": _("Administration"), "url_name": "administration:admin_panel"},
            ],
        },
    ]
    return {
        "APP_NAME": getattr(settings, "APP_NAME", "Holystyl"),
        "nav_primary": nav_primary,
        "nav_sections": nav_sections,
    }
