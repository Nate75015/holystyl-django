"""Invitation d'un membre d'équipe à ouvrir son espace employé.

L'espace employé se déduit d'un `TeamMember.user` renseigné (voir
`core.espaces`). Inviter un membre, c'est donc lui donner le moyen de rattacher
un compte à sa fiche — rien de plus.

Le jeton n'est pas stocké : il est **signé** et porte l'identifiant du membre
avec son email. Trois conséquences voulues, gratuites :

* changer l'email d'un membre périme les liens déjà envoyés ;
* aucune table à purger, la péremption est dans la signature (`DUREE`) ;
* renvoyer une invitation n'invalide pas la précédente — c'est le même jeton.
"""

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import TeamMember

#: Sel de signature : un jeton d'invitation ne peut pas servir ailleurs.
SEL = "equipe.invitation"

#: Durée de validité du lien (7 jours).
DUREE = 7 * 24 * 3600


def jeton(membre: TeamMember) -> str:
    """Le jeton signé identifiant `membre` et l'email invité."""
    return signing.dumps({"membre": membre.pk, "email": membre.email.lower()}, salt=SEL)


def membre_du_jeton(token: str) -> TeamMember | None:
    """Le membre désigné par `token`, ou None si le lien est invalide ou périmé.

    Invalide aussi quand l'email du membre a changé depuis l'envoi : le lien
    était adressé à une personne, pas à une fiche.
    """
    try:
        donnees = signing.loads(token, salt=SEL, max_age=DUREE)
    except signing.BadSignature:
        return None
    membre = TeamMember.objects.filter(pk=donnees.get("membre"), is_active=True).first()
    if membre is None or membre.email.lower() != donnees.get("email"):
        return None
    return membre


def lien(membre: TeamMember, request) -> str:
    """L'URL absolue d'acceptation, telle qu'elle part dans l'email."""
    return request.build_absolute_uri(reverse("equipe:invitation", args=[jeton(membre)]))


def envoyer(membre: TeamMember, request) -> str:
    """Envoie l'invitation et horodate l'envoi. Renvoie le lien envoyé.

    `fail_silently=False` : l'invitation est un geste explicite de l'exploitant,
    un envoi qui échoue doit lui être dit, pas avalé — contrairement aux rappels
    de tâches automatiques.
    """
    url = lien(membre, request)
    exploitation = membre.exploitation.name
    app = getattr(settings, "APP_NAME", "Isidor")
    send_mail(
        _("%(app)s — rejoignez l'équipe de %(expl)s") % {"app": app, "expl": exploitation},
        _(
            "Bonjour %(nom)s,\n\n"
            "Vous avez été ajouté(e) à l'équipe de %(expl)s sur %(app)s. "
            "Ouvrez votre espace employé pour retrouver vos tâches et votre planning :\n\n"
            "%(lien)s\n\n"
            "Ce lien est valable 7 jours.\n\n"
            "— L'équipe %(app)s"
        ) % {"nom": membre.name, "expl": exploitation, "app": app, "lien": url},
        None,
        [membre.email],
    )
    membre.invitation_sent_at = timezone.now()
    membre.save(update_fields=["invitation_sent_at", "updated_at"])
    return url


def accepter(membre: TeamMember, user) -> None:
    """Rattache `user` à la fiche : c'est ce qui ouvre l'espace employé."""
    membre.user = user
    membre.invitation_accepted_at = timezone.now()
    membre.save(update_fields=["user", "invitation_accepted_at", "updated_at"])
