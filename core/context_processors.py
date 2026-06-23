"""Variables injectées dans tous les templates (navigation, branding)."""

from django.conf import settings
from django.utils.translation import gettext_lazy as _


def layout(request):
    """Navigation de la sidebar (sections) + accès rapides mobiles + branding.

    Les pages sont regroupées en sections métier. Les liens dont la route
    n'existe pas encore valent `None` (rendus désactivés).
    """
    # Accès rapides de la barre mobile (bas d'écran)
    nav_primary = [
        {"label": _("Accueil"), "url_name": "core:dashboard"},
        {"label": _("Parcelles"), "url_name": "parcelles:list"},
        {"label": _("Irrigation"), "url_name": "irrigation:irrigation"},
        {"label": _("Planning"), "url_name": "planning:planning"},
        {"label": _("Assistant"), "url_name": "ia:assistant"},
    ]

    nav_sections = [
        {
            "label": _("Accueil"),
            "key": "accueil",
            "items": [
                {"label": _("Tableau de bord"), "url_name": "core:dashboard"},
                {"label": _("Assistant IA"), "url_name": "ia:assistant"},
                {"label": _("Notifications"), "url_name": "notifications:center"},
            ],
        },
        {
            "label": _("Cultures & Terrain"),
            "key": "cultures",
            "items": [
                {"label": _("Parcelles"), "url_name": "parcelles:list"},
                {"label": _("Cultures & Kc"), "url_name": "agronomie:cultures_kc"},
                {"label": _("Types de sol"), "url_name": "agronomie:types_sol"},
                {"label": _("Saisons"), "url_name": "agronomie:saisons"},
                {"label": _("Irrigation"), "url_name": "irrigation:irrigation"},
                {"label": _("Régie SCADA"), "url_name": "iot:regie"},
                {"label": _("Capteurs"), "url_name": "iot:capteurs"},
            ],
        },
        {
            "label": _("Protection"),
            "key": "protection",
            "items": [
                {"label": _("Bassinage anti-gel"), "url_name": "irrigation:bassinage"},
                {"label": _("Interventions"), "url_name": "operations:interventions"},
            ],
        },
        {
            "label": _("Économie"),
            "key": "economie",
            "items": [
                {"label": _("Charges"), "url_name": "finances:charges"},
                {"label": _("Bilan économique"), "url_name": "finances:bilan_economique"},
                {"label": _("Facturation"), "url_name": "finances:facturation"},
                {"label": _("Parc matériel"), "url_name": "operations:parc_materiel"},
            ],
        },
        {
            "label": _("Environnement"),
            "key": "environnement",
            "items": [
                {"label": _("Laboratoire"), "url_name": "analyses:laboratoire"},
                {"label": _("Analyses de sol"), "url_name": "analyses:analyses_sol"},
            ],
        },
        {
            "label": _("RH"),
            "key": "rh",
            "items": [
                {"label": _("Planning"), "url_name": "planning:planning"},
                {"label": _("Équipe"), "url_name": "equipe:equipe"},
                {"label": _("Tâches"), "url_name": "equipe:taches"},
                {"label": _("Mes tâches"), "url_name": "equipe:mes_taches"},
            ],
        },
        {
            "label": _("Mon compte"),
            "key": "compte",
            "items": [
                {"label": _("Mon exploitation"), "url_name": "exploitations:settings"},
                {"label": _("Activer un code"), "url_name": "public:activer"},
                {"label": _("Administration"), "url_name": "administration:admin_panel"},
            ],
        },
    ]

    # Section contenant la page courante → le panneau volant reste ouvert dessus
    current = getattr(getattr(request, "resolver_match", None), "view_name", None)
    active_section = ""
    for section in nav_sections:
        if any(item["url_name"] == current for item in section["items"]):
            active_section = section["key"]
            break

    return {
        "APP_NAME": getattr(settings, "APP_NAME", "Holystyl"),
        "nav_primary": nav_primary,
        "nav_sections": nav_sections,
        "active_section": active_section,
    }
