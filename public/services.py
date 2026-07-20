"""Agent commercial « Alex » et lead magnet."""

from django.core.mail import send_mail
from django.utils import timezone

from ia import llm

from .models import LeadCapture

ALEX_SYSTEM = (
    "Tu t'appelles Alex, l'avatar commercial de Holystyl, plateforme de pilotage "
    "d'irrigation de précision pour agriculteurs. Style : chaleureux, concret, jamais "
    "insistant. Démarche : découverte des besoins → reformulation (effet miroir) → "
    "bénéfices Holystyl (économies d'eau/énergie, score DTI, conformité subventions, "
    "assistant IA). Réponses courtes. Si l'agriculteur est intéressé, propose d'envoyer "
    "une présentation par email."
)

ALEX_NOT_CONFIGURED = (
    "Bonjour, je suis Alex 🌱 L'assistant commercial n'est pas encore connecté. "
    "Laissez-nous votre email et nous revenons vers vous."
)


def alex_chat(messages: list[dict]) -> str:
    if not llm.is_configured():
        return ALEX_NOT_CONFIGURED
    convo = [{"role": "system", "content": ALEX_SYSTEM}] + messages
    return llm.generate_text(convo)


def capture_lead(email: str, source: str = "guide_analyses") -> LeadCapture:
    lead = LeadCapture.objects.create(email=email, source=source, guide_sent_at=timezone.now())
    send_mail(
        "Votre guide Holystyl — Lire ses analyses de sol",
        "Merci pour votre intérêt ! Vous trouverez votre guide en pièce jointe. "
        "— L'équipe Holystyl",
        None,
        [email],
        fail_silently=True,
    )
    return lead
