"""Modèles de contrat : jetons, remplissage, et squelettes de départ.

Un modèle est du texte semé de jetons `{{ … }}` que l'établissement remplace
par les données du salarié et de l'exploitation. Le remplacement est une
simple substitution de chaînes, pas un rendu de gabarit Django : le corps est
écrit par l'exploitant, il n'a aucune raison d'exécuter du code, et un jeton
inconnu doit rester visible plutôt que de disparaître en silence.

Les squelettes ci-dessous donnent les rubriques et les mentions usuelles d'un
contrat agricole. Ce ne sont pas des textes juridiquement validés : la
convention collective applicable, la durée d'essai et les clauses obligatoires
varient, et l'exploitant doit les faire relire avant usage.
"""

from django.utils import formats
from django.utils.translation import gettext_lazy as _

#: Les jetons proposés à l'exploitant, avec ce qu'ils deviennent. L'ordre fait
#: celui de l'aide affichée sous l'éditeur.
JETONS = (
    ("salarie", _("Nom du salarié")),
    ("salarie_email", _("Email du salarié")),
    ("salarie_telephone", _("Téléphone du salarié")),
    ("exploitation", _("Nom de l'exploitation")),
    ("exploitation_adresse", _("Adresse de l'exploitation")),
    ("exploitation_siret", _("SIRET de l'exploitation")),
    ("employeur", _("Nom du chef d'exploitation")),
    ("poste", _("Poste occupé")),
    ("lieu", _("Lieu de travail")),
    ("date_debut", _("Date de début")),
    ("date_fin", _("Date de fin")),
    ("duree_hebdo", _("Durée hebdomadaire")),
    ("remuneration", _("Rémunération brute mensuelle")),
    ("date_du_jour", _("Date d'établissement")),
)


def _texte(valeur):
    """Une valeur prête à s'insérer : dates à la française, nombres lisibles."""
    if valeur is None or valeur == "":
        return ""
    if hasattr(valeur, "isoformat") and not isinstance(valeur, str):
        return formats.date_format(valeur, "DATE_FORMAT")
    if isinstance(valeur, float):
        return formats.number_format(valeur, decimal_pos=2, use_l10n=True)
    return str(valeur)


def remplir(corps, valeurs):
    """Remplace les jetons connus par leur valeur.

    Un jeton laissé vide devient une ligne de pointillés plutôt qu'un blanc :
    sur un contrat imprimé, on voit ainsi ce qui reste à compléter à la main.
    """
    rendu = corps or ""
    for cle, _libelle in JETONS:
        valeur = _texte(valeurs.get(cle))
        rendu = rendu.replace("{{ %s }}" % cle, valeur or "……………………")
        rendu = rendu.replace("{{%s}}" % cle, valeur or "……………………")
    return rendu


def valeurs_pour(contrat):
    """Les valeurs d'un contrat, prêtes pour `remplir`."""
    from django.utils import timezone

    membre = contrat.membre
    exploitation = contrat.exploitation
    proprietaire = getattr(exploitation, "owner", None)
    return {
        "salarie": membre.name,
        "salarie_email": membre.email,
        "salarie_telephone": membre.phone,
        "exploitation": exploitation.name,
        "exploitation_adresse": " ".join(
            p for p in (getattr(exploitation, "address", ""),
                        getattr(exploitation, "postal_code", "")) if p),
        "exploitation_siret": getattr(exploitation, "siret", "") or "",
        "employeur": proprietaire.display_name if proprietaire else "",
        "poste": contrat.poste,
        "lieu": contrat.lieu,
        "date_debut": contrat.date_debut,
        "date_fin": contrat.date_fin,
        "duree_hebdo": contrat.duree_hebdo,
        "remuneration": contrat.remuneration,
        "date_du_jour": timezone.localdate(),
    }


#: Corps commun : identité des parties, puis les clauses propres au type.
_ENTETE = """CONTRAT DE TRAVAIL

Entre les soussignés :

{{ exploitation }}, dont le siège est situé {{ exploitation_adresse }},
immatriculée sous le SIRET {{ exploitation_siret }}, représentée par
{{ employeur }}, ci-après « l'employeur »,

et

{{ salarie }}, ci-après « le salarié »,

il a été convenu ce qui suit.
"""

_PIED = """
Article — Convention collective
Le présent contrat est régi par la convention collective applicable à
l'exploitation. Le salarié déclare en avoir pris connaissance.

Article — Période d'essai
Une période d'essai est prévue conformément à la convention collective
applicable. Elle peut être renouvelée dans les conditions qu'elle fixe.

Fait à {{ lieu }}, le {{ date_du_jour }}, en deux exemplaires originaux.


L'employeur                                Le salarié
{{ employeur }}                            {{ salarie }}
"""

#: Squelettes proposés à l'import. Rubriques et mentions usuelles, à faire
#: relire : ce ne sont pas des contrats prêts à signer.
SQUELETTES = (
    {
        "nom": _("CDI — contrat à durée indéterminée"),
        "type_contrat": "cdi",
        "corps": _ENTETE + """
Article 1 — Engagement
Le salarié est engagé à compter du {{ date_debut }} pour une durée
indéterminée, au poste de {{ poste }}.

Article 2 — Lieu de travail
Le salarié exerce ses fonctions à {{ lieu }}. La nature agricole de l'activité
peut le conduire à intervenir sur les différentes parcelles de l'exploitation.

Article 3 — Durée du travail
La durée hebdomadaire de travail est de {{ duree_hebdo }} heures. Elle peut
varier selon les saisons dans les conditions prévues par la convention
collective et l'accord d'annualisation éventuellement applicable.

Article 4 — Rémunération
Le salarié perçoit une rémunération brute mensuelle de {{ remuneration }} euros,
versée à terme échu.
""" + _PIED,
    },
    {
        "nom": _("CDD — contrat à durée déterminée"),
        "type_contrat": "cdd",
        "corps": _ENTETE + """
Article 1 — Objet et motif du recours
Le présent contrat est conclu pour une durée déterminée. Le motif du recours
doit être précisé ici : accroissement temporaire d'activité, remplacement d'un
salarié absent, ou emploi à caractère saisonnier.

Article 2 — Durée
Le contrat prend effet le {{ date_debut }} et prend fin le {{ date_fin }}.

Article 3 — Poste et lieu
Le salarié est engagé au poste de {{ poste }}, à {{ lieu }}.

Article 4 — Durée du travail
La durée hebdomadaire de travail est de {{ duree_hebdo }} heures.

Article 5 — Rémunération
Le salarié perçoit une rémunération brute mensuelle de {{ remuneration }} euros.

Article 6 — Indemnité de fin de contrat
Sauf dans les cas où la loi l'exclut — notamment l'emploi saisonnier — une
indemnité de fin de contrat est versée au terme du contrat.
""" + _PIED,
    },
    {
        "nom": _("Contrat saisonnier"),
        "type_contrat": "saisonnier",
        "corps": _ENTETE + """
Article 1 — Objet
Le présent contrat est conclu pour l'exécution de travaux à caractère
saisonnier, dont la répétition est liée au rythme des saisons.

Article 2 — Durée
Le contrat prend effet le {{ date_debut }} et prend fin le {{ date_fin }}.
Il peut prendre fin par anticipation à l'achèvement de la saison, si cette
possibilité est prévue et portée à la connaissance du salarié.

Article 3 — Travaux confiés
Le salarié est engagé au poste de {{ poste }}, à {{ lieu }}, pour les travaux
liés à la saison en cours.

Article 4 — Durée du travail et rémunération
La durée hebdomadaire de travail est de {{ duree_hebdo }} heures. La
rémunération brute mensuelle est de {{ remuneration }} euros.

Article 5 — Hébergement et repas
Préciser ici, le cas échéant, les conditions d'hébergement et de restauration,
ainsi que les retenues correspondantes.
""" + _PIED,
    },
    {
        "nom": _("Contrat d'apprentissage"),
        "type_contrat": "apprentissage",
        "corps": _ENTETE + """
Article 1 — Objet
Le présent contrat a pour objet la formation de l'apprenti, qui prépare un
diplôme ou un titre à finalité professionnelle, en alternance entre
l'exploitation et son centre de formation.

Article 2 — Durée
Le contrat prend effet le {{ date_debut }} et prend fin le {{ date_fin }}.

Article 3 — Maître d'apprentissage
Le maître d'apprentissage désigné est {{ employeur }}. Il assure la formation
pratique de l'apprenti sur l'exploitation.

Article 4 — Travail et formation
L'apprenti occupe le poste de {{ poste }} à {{ lieu }}, pour une durée
hebdomadaire de {{ duree_hebdo }} heures, temps de formation compris.

Article 5 — Rémunération
La rémunération brute mensuelle est de {{ remuneration }} euros, déterminée
selon l'âge de l'apprenti et l'année d'exécution du contrat.
""" + _PIED,
    },
    {
        "nom": _("Convention de stage"),
        "type_contrat": "stage",
        "corps": _ENTETE + """
Article 1 — Objet
La présente convention règle les rapports entre l'exploitation, le stagiaire
et son établissement d'enseignement. Elle ne constitue pas un contrat de
travail.

Article 2 — Durée
Le stage se déroule du {{ date_debut }} au {{ date_fin }}, à {{ lieu }}.

Article 3 — Objectifs pédagogiques
Décrire ici les missions confiées et les compétences visées, en cohérence avec
la formation suivie. Missions envisagées : {{ poste }}.

Article 4 — Encadrement
Le tuteur de stage au sein de l'exploitation est {{ employeur }}.

Article 5 — Gratification
Une gratification est due au-delà de la durée légale de stage. Son montant
mensuel est de {{ remuneration }} euros.
""" + _PIED,
    },
)
