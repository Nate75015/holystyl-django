"""Espaces : chef d'entreprise, employé, bailleur.

Un espace est une **audience**, pas un domaine : les trois regardent les mêmes
apps métier (parcelles, contrat, equipe…), mais chacun n'en voit qu'une part.

L'espace n'est donc pas un champ du `User` : il se **déduit** des rattachements
qui existent déjà en base, pour ne pas dupliquer une vérité qui vit ailleurs.

    exploitant → Exploitation.owner
    employé    → equipe.TeamMember.user   (membre actif)
    bailleur   → client.Partenaire.user   (type_partenaire = bailleur)

Un même compte peut relever de plusieurs espaces (un associé salarié de sa
propre exploitation, par exemple) : d'où `espaces_de()` qui renvoie une liste,
et l'espace actif mémorisé en session.

Les imports des apps métier sont volontairement tardifs (dans les fonctions) :
le socle ne doit pas dépendre du chargement des apps au moment de l'import.
"""

from django.utils.translation import gettext_lazy as _

EXPLOITANT = "exploitant"
EMPLOYE = "employe"
BAILLEUR = "bailleur"

#: Clé de session portant l'espace actif.
SESSION_KEY = "espace"

#: Source de vérité pour l'affichage (sélecteur de la sidebar). L'ordre fait foi :
#: c'est celui du sélecteur, et le premier espace disponible sert de défaut.
#:
#: `action` (facultatif) : que faire pour ouvrir cet espace quand il n'est pas
#: encore disponible. Un espace se gagne par un rattachement, et ce rattachement
#: se crée toujours depuis un autre espace — d'où `depuis`, qui évite de proposer
#: un écran auquel le compte n'a pas accès.
ESPACES = (
    {"cle": EXPLOITANT, "label": _("Chef d'entreprise"), "icone": "business_center"},
    {
        "cle": EMPLOYE,
        "label": _("Employé"),
        "icone": "badge",
        "action": {
            "vue": "equipe:equipe",
            "libelle": _("définir les membres de l'équipe"),
            "depuis": EXPLOITANT,
        },
    },
    {"cle": BAILLEUR, "label": _("Bailleur"), "icone": "real_estate_agent"},
)

ORDRE = tuple(e["cle"] for e in ESPACES)

#: Entrées de navigation ouvertes à chaque espace, par nom de vue.
#:
#: L'exploitant est absent du dictionnaire : il voit toute la nav, c'est le
#: comportement historique. Pour les deux autres, on **liste ce qui est permis**
#: plutôt que ce qui est interdit : une section ajoutée plus tard reste invisible
#: par défaut, au lieu de fuiter chez un employé ou un bailleur.
#:
#: Ceci pilote l'affichage, pas les permissions : une entrée masquée reste
#: atteignable en tapant l'URL. Le contrôle d'accès par vue reste à faire.
NAV_AUTORISEE = {
    EMPLOYE: {
        "core:dashboard",
        "notifications:center",
        "messagerie:inbox",
        "planning:planning",
        "equipe:taches",
    },
    BAILLEUR: {
        "core:dashboard",
        "notifications:center",
        "messagerie:inbox",
        "contrat:baux",
    },
}


def nav_autorisee(espace):
    """Les noms de vue visibles dans cet espace, ou None si tout est ouvert."""
    return NAV_AUTORISEE.get(espace)


def _rattachement(user, espace):
    """L'objet qui rattache `user` à `espace`, ou None.

    Renvoie l'Exploitation pour l'exploitant, le TeamMember pour l'employé, le
    Partenaire pour le bailleur — chacun porte l'exploitation concernée.
    """
    if user is None or not user.is_authenticated:
        return None

    if espace == EXPLOITANT:
        from exploitations.models import Exploitation

        return Exploitation.objects.filter(owner=user).first()

    if espace == EMPLOYE:
        from equipe.models import TeamMember

        return TeamMember.objects.filter(user=user, is_active=True).first()

    if espace == BAILLEUR:
        from client.models import Partenaire

        return Partenaire.objects.filter(
            user=user, type_partenaire=Partenaire.Type.BAILLEUR
        ).first()

    return None


def _calculer(request):
    """Résout (rattachements, espaces disponibles, espace courant) en une passe.

    Trois requêtes indexées au plus, et zéro pour un visiteur anonyme.
    """
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}, [], None

    rattachements = {cle: _rattachement(user, cle) for cle in ORDRE}
    disponibles = [cle for cle in ORDRE if rattachements[cle] is not None]
    if not disponibles:
        return rattachements, [], None

    memorise = request.session.get(SESSION_KEY) if hasattr(request, "session") else None
    courant = memorise if memorise in disponibles else disponibles[0]
    return rattachements, disponibles, courant


def contexte(request):
    """Le triplet ci-dessus, mémorisé pour la durée de la requête."""
    cache = getattr(request, "_espaces_cache", None)
    if cache is None:
        cache = _calculer(request)
        request._espaces_cache = cache
    return cache


def invalider(request):
    """Oublie le cache de requête après un changement de rattachement.

    Le contexte est résolu une fois par requête (middleware). Une vue qui crée
    ou supprime un rattachement — accepter une invitation, par exemple — le rend
    donc périmé au milieu de son propre traitement : sans cet appel, l'espace
    tout juste ouvert paraîtrait encore indisponible.
    """
    request._espaces_cache = None


def espaces_de(user):
    """Les espaces auxquels `user` a droit, dans l'ordre de `ESPACES`.

    Liste vide pour un compte sans aucun rattachement (utilisateur fraîchement
    inscrit, avant l'onboarding).
    """
    return [cle for cle in ORDRE if _rattachement(user, cle) is not None]


def espace_courant(request):
    """L'espace actif, ou None si le compte n'a aucun espace.

    Un espace mémorisé en session auquel l'utilisateur n'a plus droit est
    ignoré au profit du premier disponible.
    """
    return contexte(request)[2]


def espaces_disponibles(request):
    """Les espaces ouverts à l'utilisateur de la requête (pour le sélecteur)."""
    return contexte(request)[1]


def definir_espace(request, espace):
    """Mémorise l'espace actif. Renvoie False si l'utilisateur n'y a pas droit."""
    if espace not in espaces_disponibles(request):
        return False
    request.session[SESSION_KEY] = espace
    invalider(request)
    return True


def exploitation_de(request):
    """L'exploitation vue depuis l'espace courant, ou None.

    C'est ce que pose `CurrentExploitationMiddleware` : l'exploitation dépend
    de l'espace, un employé n'étant pas propriétaire de la sienne.
    """
    rattachements, _, courant = contexte(request)
    if courant is None:
        return None
    rattachement = rattachements[courant]
    if courant == EXPLOITANT:
        return rattachement
    return rattachement.exploitation
