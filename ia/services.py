"""Logique de l'assistant IA : contexte, chat, extraction d'intentions, rapport.

Reproduit le comportement du routeur `ai` tRPC (server/routers.ts) :
- chat conversationnel contextualisé,
- executeIntent → création directe d'entités (function calling),
- generateReport → rapport quotidien.

Les intentions dont l'entité n'est pas encore migrée (intervention, charge,
revenu, entretien — Tranches 5/6) sont reconnues mais renvoient un message
« module à venir » au lieu d'échouer ou d'inventer.
"""

from __future__ import annotations

from datetime import date

from django.utils import timezone

from irrigation.models import IrrigationSession
from irrigation.services import calculate_dti_score
from parcelles.models import Parcelle

from . import gemini
from .models import AiConversation, DailyReport

ASSISTANT_NOT_CONFIGURED = (
    "L'assistant IA n'est pas encore configuré (clé Gemini manquante). "
    "Renseignez GEMINI_API_KEY pour l'activer."
)

INTENT_ENUM = [
    "creer_parcelle",
    "creer_intervention",
    "creer_session_irrigation",
    "creer_charge",
    "creer_revenu",
    "creer_entretien",
    "question",
]

# Intentions dont l'entité Django existe déjà
_IMPLEMENTED = {"creer_parcelle", "creer_session_irrigation", "creer_intervention", "question"}


def build_context(exploitation) -> dict:
    if exploitation is None:
        return {"parcelles": "aucune"}
    parcelles = exploitation.parcelles.all()
    return {
        "parcelles": ", ".join(f"{p.name} (id:{p.id}, culture:{p.culture or '—'})" for p in parcelles) or "aucune",
    }


def _intent_system_prompt(ctx: dict) -> str:
    return f"""Tu es l'assistant IA de Holystyl, copilote agricole intelligent pour l'exploitation.
Ton rôle : comprendre les demandes de l'agriculteur et créer directement les enregistrements.

CONTEXTE (données réelles, utilise les IDs exacts) :
- Parcelles : {ctx.get('parcelles', 'aucune')}

INTENTIONS SUPPORTÉES : {', '.join(INTENT_ENUM)}.

RÈGLES :
- Si une information clé manque, pose UNE question ciblée et mets needs_more_info=true.
- Identifie la parcelle par son nom OU sa culture.
- Pour les montants, extrais le nombre. Pour les dates, utilise aujourd'hui si non précisé.
- Sois concis et chaleureux.

Réponds UNIQUEMENT en JSON avec ce schéma :
{{"response": "texte", "intent": "<une des intentions>", "needs_more_info": false,
  "data": {{"name": "", "areaHa": 0, "culture": "", "parcelleId": 0, "volumeDeliveredM3": 0}}}}"""


def _resolve_parcelle(exploitation, data) -> Parcelle | None:
    pid = data.get("parcelleId")
    if pid:
        p = Parcelle.objects.filter(exploitation=exploitation, id=pid).first()
        if p:
            return p
    name = data.get("parcelleName") or data.get("name")
    if name:
        return Parcelle.objects.filter(exploitation=exploitation, name__icontains=name).first()
    return None


def chat(exploitation, user, message: str, history: list[dict] | None = None) -> str:
    """Réponse conversationnelle (persistée dans l'historique)."""
    AiConversation.objects.create(exploitation=exploitation, user=user, role="user", content=message)
    if not gemini.is_configured():
        AiConversation.objects.create(
            exploitation=exploitation, user=user, role="assistant", content=ASSISTANT_NOT_CONFIGURED
        )
        return ASSISTANT_NOT_CONFIGURED

    ctx = build_context(exploitation)
    messages = [{"role": "system", "content": f"Tu es l'assistant Holystyl. Parcelles : {ctx['parcelles']}."}]
    messages += history or []
    messages.append({"role": "user", "content": message})
    answer = gemini.generate_text(messages)
    AiConversation.objects.create(exploitation=exploitation, user=user, role="assistant", content=answer)
    return answer


def execute_intent(exploitation, user, message: str, history: list[dict] | None = None) -> dict:
    """Extrait l'intention et crée l'entité correspondante quand c'est possible."""
    if not gemini.is_configured():
        return {"response": ASSISTANT_NOT_CONFIGURED, "intent": "question", "created": False}

    messages = [{"role": "system", "content": _intent_system_prompt(build_context(exploitation))}]
    messages += history or []
    messages.append({"role": "user", "content": message})
    parsed = gemini.generate_json(messages)

    intent = parsed.get("intent", "question")
    data = parsed.get("data") or {}
    response = parsed.get("response", "")
    result = {"response": response, "intent": intent, "created": False, "entity": None}

    if parsed.get("needs_more_info") or intent == "question":
        return result

    if intent == "creer_parcelle":
        parcelle = Parcelle.objects.create(
            exploitation=exploitation,
            name=data.get("name") or "Nouvelle parcelle",
            area=data.get("areaHa"),
            culture=data.get("culture", ""),
            variety=data.get("variety", ""),
            commune=data.get("commune", ""),
        )
        result.update(created=True, entity={"type": "parcelle", "id": parcelle.id, "name": parcelle.name})

    elif intent == "creer_session_irrigation":
        parcelle = _resolve_parcelle(exploitation, data)
        session = IrrigationSession.objects.create(
            exploitation=exploitation,
            parcelle=parcelle,
            start_time=timezone.now(),
            volume_delivered_m3=data.get("volumeDeliveredM3"),
            triggered_by=IrrigationSession.TriggeredBy.AI,
        )
        result.update(created=True, entity={"type": "irrigation_session", "id": session.id})

    elif intent == "creer_intervention":
        from operations.models import Intervention

        parcelle = _resolve_parcelle(exploitation, data)
        itype = data.get("interventionType") or "autre"
        valid_types = {c.value for c in Intervention.Type}
        intervention = Intervention.objects.create(
            exploitation=exploitation,
            parcelle=parcelle,
            user=user,
            intervention_type=itype if itype in valid_types else "autre",
            title=data.get("title", ""),
            start_time=timezone.now(),
            product=data.get("product", ""),
            dose=str(data.get("dose", "")),
            notes=data.get("notes", ""),
            source=Intervention.Source.AI,
        )
        result.update(created=True, entity={"type": "intervention", "id": intervention.id})

    elif intent in INTENT_ENUM:
        # Intention reconnue mais module pas encore migré (Tranche 6 : charge/revenu/entretien)
        result["response"] = (
            response or f"J'ai compris « {intent} », mais ce module sera disponible dans une prochaine version."
        )

    if response or result["created"]:
        AiConversation.objects.create(
            exploitation=exploitation, user=user, role="assistant",
            content=result["response"], extracted_action=parsed,
        )
    return result


def generate_daily_report(exploitation, report_date: date | None = None) -> DailyReport:
    """Génère et persiste le rapport quotidien (DTI + recommandations)."""
    report_date = report_date or timezone.localdate()
    latest_dti = exploitation.dti_scores.first()
    kwh = latest_dti.kwh_per_m3 if latest_dti else 0.24
    dti = calculate_dti_score(kwh or 0.24)

    summary = ""
    if gemini.is_configured():
        summary = gemini.generate_text([
            {"role": "system", "content": "Tu es un expert en irrigation agricole. Rédige un résumé quotidien concis."},
            {"role": "user", "content": f"Score DTI {dti.score} ({kwh} kWh/m³). Rédige un point du jour."},
        ])

    return DailyReport.objects.create(
        exploitation=exploitation,
        report_date=report_date,
        summary=summary,
        dti_score=dti.score,
        kwh_per_m3=kwh,
        alerts_count=exploitation.alerts.filter(acknowledged=False).count(),
        recommendations=dti.recommendations,
    )
