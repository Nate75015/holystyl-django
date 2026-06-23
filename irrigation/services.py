"""Moteur DTI (score d'efficience énergétique de l'irrigation).

Reproduction fidèle de `calculateDtiScore` (server/routers.ts).
"""

from dataclasses import dataclass, field


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
