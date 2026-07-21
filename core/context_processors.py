"""Variables injectées dans tous les templates (navigation, branding)."""

import os
import unicodedata

from django.conf import settings
from django.utils.translation import gettext_lazy as _


def _sort_key(label):
    """Clé de tri alphabétique insensible aux accents/casse, dans la langue active."""
    text = unicodedata.normalize("NFKD", str(label))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.casefold()


def _css_version():
    """En dev, mtime de app.css → cache-buster pour éviter le hard-refresh.
    En prod (DEBUG=False), on renvoie "" : le manifest hashé gère déjà le cache."""
    if not settings.DEBUG:
        return ""
    for base in settings.STATICFILES_DIRS or []:
        path = os.path.join(base, "css", "app.css")
        try:
            return str(int(os.path.getmtime(path)))
        except OSError:
            continue
    return ""


def layout(request):
    """Navigation de la sidebar (sections) + accès rapides mobiles + branding."""
    nav_primary = [
        {"label": _("Accueil"), "url_name": "core:dashboard"},
        {"label": _("Parcelles"), "url_name": "parcelles:list"},
        {"label": _("Irrigation"), "url_name": "irrigation:irrigation"},
        {"label": _("Planning"), "url_name": "planning:planning"},
        {"label": _("Assistant"), "url_name": "ia:assistant"},
    ]

    nav_sections = [
        {
            "label": _("Accueil"), "key": "accueil",
            "items": [
                {"label": _("Tableau de bord"), "url_name": "core:dashboard", "icon": "dashboard"},
                {"label": _("Assistant IA"), "url_name": "ia:assistant", "icon": "support_agent"},
            ],
        },
        {
            "label": _("Communication"), "key": "communication",
            "items": [
                {"label": _("Notifications"), "url_name": "notifications:center", "icon": "notifications"},
                {"label": _("Messagerie"), "url_name": "messagerie:inbox", "icon": "chat"},
                {"label": _("Mail"), "url_name": "mail:outbox", "icon": "mail"},
                {"label": _("Réseau"), "url_name": "reseaux:reseaux", "icon": "hub"},
                {"label": _("Pétition"), "url_name": "petition:liste", "icon": "draw"},
            ],
        },
        {
            "label": _("Cultures & Terrain"), "key": "cultures",
            "items": [
                {"label": _("Mes Parcelles"), "url_name": "parcelles:list", "icon": "map"},
                {"label": _("Météo"), "url_name": "meteo:index", "icon": "wb_sunny"},
                {"label": _("Cultures"), "url_name": "agronomie:cultures", "icon": "grass"},
                {"label": _("Types de sol"), "url_name": "agronomie:types_sol", "icon": "terrain"},
                {"label": _("Fertigation"), "url_name": "agronomie:fertigation", "icon": "opacity"},
                {"label": _("Interventions"), "url_name": "interventions:interventions", "icon": "build"},
                {"label": _("Analyses de sol"), "url_name": "analyse_sol:analyses_sol", "icon": "biotech"},
                {"label": _("Irrigation"), "url_name": "irrigation:irrigation", "icon": "water_drop"},
                {"label": _("DTI — Diagnostic technique d'irrigation"), "url_name": "irrigation:dti", "icon": "electric_bolt"},
                {"label": _("Régie SCADA"), "url_name": "iot:regie", "icon": "tune"},
                {"label": _("Capteurs"), "url_name": "iot:capteurs", "icon": "sensors"},
            ],
        },
        {
            "label": _("Protection"), "key": "protection",
            "items": [
                {"label": _("Bassinage"), "url_name": "irrigation:bassinage", "icon": "shower"},
                {"label": _("Anti-gel"), "url_name": "irrigation:antigel", "icon": "ac_unit"},
            ],
        },
        {
            "label": _("Économie"), "key": "economie",
            "items": [
                {"label": _("Saisons"), "url_name": "agronomie:saisons", "icon": "calendar_month"},
                {"label": _("Charges"), "url_name": "finances:charges", "icon": "payments"},
                {"label": _("Bilan économique"), "url_name": "finances:bilan_economique", "icon": "insights"},
                {"label": _("Facturation"), "url_name": "finances:facturation", "icon": "receipt_long"},
                {"label": _("PAC"), "url_name": "pac:pac", "icon": "account_balance"},
                {"label": _("Parc matériel"), "url_name": "operations:parc_materiel", "icon": "agriculture"},
            ],
        },
        {
            "label": _("Environnement"), "key": "environnement",
            "items": [
                {"label": _("Biodiversité"), "url_name": "environnement:biodiversite", "icon": "eco"},
                {"label": _("Bilan eau"), "url_name": "environnement:bilan_eau", "icon": "water_drop"},
                {"label": _("Bilan azoté"), "url_name": "environnement:bilan_azote", "icon": "science"},
                {"label": _("Empreinte carbone"), "url_name": "environnement:empreinte_carbone", "icon": "cloud"},
                {"label": _("Rapport environnemental"), "url_name": "environnement:rapport", "icon": "assessment"},
                {"label": _("Santé végétale"), "url_name": "environnement:sante_vegetale", "icon": "local_florist"},
                {"label": _("Taxonomie EU"), "url_name": "environnement:taxonomie", "icon": "fact_check"},
            ],
        },
        {
            "label": _("RH"), "key": "rh",
            "items": [
                {"label": _("Planning"), "url_name": "planning:planning", "icon": "event"},
                {"label": _("Équipe"), "url_name": "equipe:equipe", "icon": "groups"},
                {"label": _("Tâches"), "url_name": "equipe:taches", "icon": "checklist"},
            ],
        },
        {
            "label": _("Contrat"), "key": "contrat",
            "items": [
                {"label": _("Contrats"), "url_name": "contrat:contrats", "icon": "description"},
                {"label": _("Baux"), "url_name": "contrat:baux", "icon": "agriculture"},
                {"label": _("Patrimoine"), "url_name": "contrat:actes", "icon": "history_edu"},
                {"label": _("Assurance"), "url_name": "contrat:assurances", "icon": "shield"},
                {"label": _("Mutualité Sociale Agricole"), "url_name": "contrat:msa", "icon": "health_and_safety"},
            ],
        },
        {
            "label": _("Mon compte"), "key": "compte",
            "items": [
                {"label": _("Mon exploitation"), "url_name": "exploitations:settings", "icon": "home_work"},
                {"label": _("Identités"), "url_name": "exploitations:section_identite", "icon": "badge"},
                {"label": _("Juridique"), "url_name": "exploitations:section_juridique", "icon": "gavel"},
                {"label": _("Contact"), "url_name": "exploitations:contact", "icon": "call"},
                {"label": _("Localisation"), "url_name": "exploitations:section_localisation", "icon": "place"},
                {"label": _("Caractéristiques agricoles"), "url_name": "exploitations:section_caracteristiques", "icon": "agriculture"},
                {"label": _("Eau"), "url_name": "exploitations:section_eau", "icon": "water_drop"},
                {"label": _("Certificats et labels"), "url_name": "exploitations:section_certifications", "icon": "verified"},
                {"label": _("Sociétés liées"), "url_name": "exploitations:societes", "icon": "domain"},
            ],
        },
    ]

    # Sections triées par ordre alphabétique (selon le libellé dans la langue active)
    nav_sections.sort(key=lambda section: _sort_key(section["label"]))
    # Items de chaque sous-section triés par ordre alphabétique
    for section in nav_sections:
        section["items"].sort(key=lambda item: _sort_key(item["label"]))

    # Section + item contenant la page courante (le panneau volant reste ouvert dessus)
    current = getattr(getattr(request, "resolver_match", None), "view_name", None)
    current_ns = current.split(":")[0] if current else ""

    all_items = [(section, item) for section in nav_sections for item in section["items"]]
    ns_counts = {}
    for section, item in all_items:
        ns = item["url_name"].split(":")[0]
        ns_counts[ns] = ns_counts.get(ns, 0) + 1

    active_section, active_url_name = "", ""
    # 1) correspondance exacte du nom de vue
    for section, item in all_items:
        if item["url_name"] == current:
            active_section, active_url_name = section["key"], item["url_name"]
            break
    # 2) repli par namespace (sous-pages : detail, create…) si le namespace est unique dans la nav
    if not active_url_name and current_ns and ns_counts.get(current_ns) == 1:
        for section, item in all_items:
            if item["url_name"].split(":")[0] == current_ns:
                active_section, active_url_name = section["key"], item["url_name"]
                break

    # Compteur de notifications non lues (badge sur la cloche du header)
    unread_notifications = 0
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        unread_notifications = user.notifications.filter(read=False).count()

    # Section ouverte par défaut dans le panneau latéral (jamais vide → toujours visible)
    default_section = active_section or (nav_sections[0]["key"] if nav_sections else "")

    return {
        "APP_NAME": getattr(settings, "APP_NAME", "Holystyl"),
        "nav_primary": nav_primary,
        "nav_sections": nav_sections,
        "active_section": active_section,
        "active_url_name": active_url_name,
        "default_section": default_section,
        "unread_notifications": unread_notifications,
        "css_version": _css_version(),
    }
