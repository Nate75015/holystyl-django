"""Moteur DTI (score d'efficience énergétique de l'irrigation).

Reproduction fidèle de `calculateDtiScore` (server/routers.ts).
"""

from dataclasses import dataclass, field

#: Coefficient cultural par défaut (mi-saison, à défaut d'un Kc par culture).
DEFAULT_KC = 0.85


@dataclass
class EtcResult:
    etp: float
    kc: float
    etc: float            # besoin brut ETc = ETP × Kc (mm/j)
    pluie: float          # pluie efficace (mm), soustraite directement
    besoin_net: float     # ETc − pluie (mm)
    surface_ha: float
    volume_m3: float      # besoin net × surface × 10 (1 mm sur 1 ha = 10 m³)
    status: str           # 'ok' | 'surveiller'
    status_label: str


def calculate_etc(etp, surface_ha=0.0, pluie=0.0, kc=DEFAULT_KC):
    """Besoin en eau d'irrigation : ETc = ETP × Kc, besoin net = ETc − pluie efficace."""
    etp = etp or 0.0
    surface_ha = surface_ha or 0.0
    etc = etp * kc
    besoin_net = max(0.0, etc - (pluie or 0.0))
    volume_m3 = besoin_net * surface_ha * 10
    if besoin_net <= 0.5:
        status, label = "ok", "Sol pourvu — pas d'irrigation nécessaire"
    else:
        status, label = "surveiller", "Surveiller — irrigation à prévoir"
    return EtcResult(
        etp=round(etp, 2), kc=kc, etc=round(etc, 2), pluie=round(pluie or 0.0, 2),
        besoin_net=round(besoin_net, 2), surface_ha=round(surface_ha, 2),
        volume_m3=round(volume_m3), status=status, status_label=label,
    )


@dataclass
class DtiResult:
    score: str
    numeric: int
    recommendations: list[str] = field(default_factory=list)


def calculate_dti_score(kwh_per_m3: float, uniformity: float = 90) -> DtiResult:
    if kwh_per_m3 < 0.25:
        score = "A"
        numeric = round(85 + (0.25 - kwh_per_m3) * 200)
    elif kwh_per_m3 < 0.35:
        score = "B"
        numeric = round(65 + (0.35 - kwh_per_m3) * 200)
    elif kwh_per_m3 < 0.50:
        score = "C"
        numeric = round(40 + (0.50 - kwh_per_m3) * 167)
    else:
        score = "D"
        numeric = round(max(5, 40 - (kwh_per_m3 - 0.50) * 100))

    recommendations: list[str] = []
    if kwh_per_m3 >= 0.30:
        recommendations.append(
            f"Réduire la pression pour atteindre l'objectif 0.30 kWh/m³ (actuel : {kwh_per_m3:.3f})"
        )
    if uniformity < 85:
        recommendations.append(
            f"Uniformité {uniformity}% insuffisante — vérifier asperseurs et pression bout de réseau"
        )
    if score == "A":
        recommendations.append(f"Excellent DTI {score} — maintenir les paramètres actuels")
    elif score == "B":
        recommendations.append(f"DTI {score} — optimisation possible, régler débit pour gagner 0.02 kWh/m³")
    else:
        recommendations.append(f"DTI {score} critique — diagnostic complet pompe recommandé")
        recommendations.append("Adapter le volume irrigué au bilan hydrique réel pour éviter le sur-arrosage")

    return DtiResult(score=score, numeric=min(100, numeric), recommendations=recommendations)
