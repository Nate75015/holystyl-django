"""Lecture des indices satellite NDVI / NDWI par parcelle.

NDVI = (PIR − Rouge)/(PIR + Rouge) : vigueur du couvert végétal.
NDWI = (Vert − PIR)/(Vert + PIR)   : teneur en eau / stress hydrique.

Les seuils et les messages reprennent la méthode déjà éprouvée sur le DTI ;
seules les couleurs passent aux tokens de l'interface (--success, --warning,
--danger) pour rester cohérentes avec le reste de l'application.
"""

from django.utils.translation import gettext_lazy as _

_COULEURS = {
    "danger": "var(--danger)",
    "warning": "var(--warning)",
    "success": "var(--success)",
    "muted": "var(--text-muted)",
}


def _niveau(libelle, couleur, message):
    return {"level": libelle, "color": _COULEURS[couleur], "msg": message}


def lire_ndvi(valeur):
    """Niveau de vigueur végétale correspondant à un NDVI moyen."""
    if valeur is None:
        return _niveau(_("—"), "muted", _("Non mesuré."))
    if valeur < 0.2:
        return _niveau(_("Sol nu / très faible"), "danger",
                       _("Couvert végétal quasi absent (sol nu, semis, sénescence)."))
    if valeur < 0.4:
        return _niveau(_("Faible"), "warning",
                       _("Végétation clairsemée ou début de cycle."))
    if valeur < 0.6:
        return _niveau(_("Modérée"), "warning",
                       _("Développement correct, marge de progression."))
    if valeur < 0.8:
        return _niveau(_("Bonne"), "success",
                       _("Couvert dense et vigoureux, photosynthèse active."))
    return _niveau(_("Très dense"), "success", _("Végétation à son maximum de vigueur."))


def lire_ndwi(valeur):
    """Niveau de teneur en eau correspondant à un NDWI moyen."""
    if valeur is None:
        return _niveau(_("—"), "muted", _("Non mesuré."))
    if valeur < -0.3:
        return _niveau(_("Stress hydrique marqué"), "danger",
                       _("Teneur en eau faible : risque de déficit hydrique."))
    if valeur < -0.1:
        return _niveau(_("Assez sec"), "warning",
                       _("Teneur en eau modérée à surveiller."))
    if valeur < 0.1:
        return _niveau(_("Correct"), "success", _("Bilan hydrique équilibré."))
    return _niveau(_("Humide"), "success",
                   _("Bonne teneur en eau (ou présence d'eau libre)."))


def interpreter(mesure):
    """Lecture des deux indices d'une mesure (niveau, couleur, message)."""
    if mesure is None:
        return None
    return {
        "ndvi": lire_ndvi(mesure.ndvi_mean),
        "ndwi": lire_ndwi(mesure.ndwi_mean),
    }


def _stats(valeurs):
    """Min, max, dernier et tendance d'une série d'un indice.

    Le min/max porte sur toute la série (et non sur une seule image) : c'est ce
    qui permet de rapprocher une baisse de vigueur d'un événement daté. La
    tendance compare le dernier point à la moyenne des précédents, avec un seuil
    de 0,03 pour ignorer le bruit du capteur.
    """
    valeurs = [v for v in valeurs if v is not None]
    if not valeurs:
        return None
    tendance = "stable"
    if len(valeurs) >= 2:
        reference = sum(valeurs[:-1]) / len(valeurs[:-1])
        ecart = valeurs[-1] - reference
        tendance = "hausse" if ecart > 0.03 else "baisse" if ecart < -0.03 else "stable"
    return {
        "min": round(min(valeurs), 2),
        "max": round(max(valeurs), 2),
        "dernier": round(valeurs[-1], 2),
        "tendance": tendance,
        "n": len(valeurs),
    }


def serie(historique):
    """Statistiques temporelles d'une série de mesures (ancien → récent)."""
    if not historique:
        return None
    return {
        "ndvi": _stats([h["ndvi"] for h in historique]),
        "ndwi": _stats([h["ndwi"] for h in historique]),
        "date_debut": historique[0]["date"],
        "date_fin": historique[-1]["date"],
    }


def lignes_par_parcelle(parcelles):
    """Une ligne d'affichage par parcelle : dernière mesure, lecture, série."""
    lignes = []
    for parcelle in parcelles:
        mesures = list(parcelle.ndvi_data.all())  # ordonnées du plus récent au plus ancien
        derniere = mesures[0] if mesures else None
        historique = [
            {"date": m.acquisition_date, "ndvi": m.ndvi_mean, "ndwi": m.ndwi_mean}
            for m in reversed(mesures) if m.acquisition_date
        ]
        lignes.append({
            "parcelle": parcelle,
            "derniere": derniere,
            "lecture": interpreter(derniere),
            "serie": serie(historique),
            "nb_passages": len(mesures),
        })
    return lignes
