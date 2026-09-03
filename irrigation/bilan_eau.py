"""Le bilan d'eau d'une exploitation : volumes, quota, coût, répartition.

Ce calcul vivait dans `environnement`, où il ouvrait une page à part. Il a
rejoint `irrigation`, qui possède les sessions dont il tire tout : le bilan
n'est pas un sujet d'environnement à côté du diagnostic, c'est l'autre moitié
de la même question — ce que l'eau coûte, et ce que l'installation en fait.
"""

from collections import defaultdict

from parcelles.models import Parcelle

from .models import IrrigationSession

#: Repères par défaut quand l'exploitation ne les a pas renseignés.
QUOTA_PAR_DEFAUT_M3 = 45000.0
PRIX_EAU_PAR_DEFAUT_M3 = 0.08


def donnees(exploitation):
    """Tout ce qu'il faut pour afficher le bilan, prêt pour le gabarit."""
    sessions = (
        list(IrrigationSession.objects.filter(exploitation=exploitation)
             .select_related("parcelle"))
        if exploitation else []
    )
    total_m3 = sum(s.volume_delivered_m3 or 0 for s in sessions)
    quota = (exploitation.water_quota_m3
             if exploitation and exploitation.water_quota_m3 else QUOTA_PAR_DEFAUT_M3)
    prix_m3 = (exploitation.prix_eau_m3
               if exploitation and exploitation.prix_eau_m3 is not None
               else PRIX_EAU_PAR_DEFAUT_M3)

    # Consommation mensuelle, tous secteurs confondus.
    mensuel = defaultdict(float)
    for s in sessions:
        if s.start_time and s.volume_delivered_m3:
            mensuel[s.start_time.strftime("%Y-%m")] += s.volume_delivered_m3
    mois = sorted(mensuel)

    # Consommation quotidienne, un graphique par parcelle — y compris celles
    # qui n'ont rien consommé : leur absence de courbe est une information.
    parcelles = list(Parcelle.objects.filter(exploitation=exploitation)) if exploitation else []
    quotidien = defaultdict(lambda: defaultdict(float))
    for s in sessions:
        if s.parcelle_id and s.start_time and s.volume_delivered_m3:
            quotidien[s.parcelle_id][s.start_time.strftime("%Y-%m-%d")] += s.volume_delivered_m3

    graphiques = []
    for p in parcelles:
        jours = quotidien.get(p.pk, {})
        ordonnes = sorted(jours)
        graphiques.append({
            "nom": p.name,
            "total": round(sum(jours.values()), 1),
            "labels": [f"{d[8:10]}/{d[5:7]}" for d in ordonnes],
            "data": [round(jours[d], 1) for d in ordonnes],
        })
    graphiques.sort(key=lambda g: g["total"], reverse=True)

    return {
        "sessions": sessions,
        "total_m3": round(total_m3, 1),
        "nb_sessions": len(sessions),
        "quota": quota,
        "quota_display": f"{int(quota):,}".replace(",", " "),
        "pct_quota": round(total_m3 / quota * 100, 1) if quota else 0,
        "cout": round(total_m3 * prix_m3),
        "prix_m3": prix_m3,
        "monthly_chart": {
            "labels": [f"{m[5:7]}/{m[:4]}" for m in mois],
            "data": [round(mensuel[m], 1) for m in mois],
        },
        "parcelle_charts": graphiques,
        "has_parcelles": bool(parcelles),
    }
