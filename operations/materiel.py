"""Le vocabulaire du parc matériel : familles et types d'engins.

Ce module est la seule liste. `Machine` décrit l'exemplaire qu'une exploitation
possède, `CatalogueEngin` le modèle du marché ; l'un et l'autre parlent bien
d'un tracteur ou d'une herse, ils partagent donc les mêmes types. Les deux
énumérations qui vivaient chacune de son côté divergeaient déjà — six valeurs
tournées irrigation ici, dix tournées grandes cultures là.

La famille sert d'abord à se retrouver : soixante-dix types dans une liste
déroulante plate seraient illisibles. Elle porte aussi une distinction qui
compte, celle de l'automoteur et de l'outil attelé. Un tracteur a un compteur
horaire, du carburant et une carte grise ; une charrue n'a qu'une largeur de
travail et un tracteur pour la tirer.
"""

from django.db import models
from django.utils.translation import gettext_lazy as _


class Famille(models.TextChoices):
    AUTOMOTEUR = "automoteur", _("Automoteurs")
    TRAVAIL_DU_SOL = "travail_du_sol", _("Travail du sol")
    SEMIS = "semis", _("Semis et plantation")
    FERTILISATION = "fertilisation", _("Fertilisation et protection")
    RECOLTE = "recolte", _("Récolte et fourrage")
    TRANSPORT = "transport", _("Transport et manutention")
    IRRIGATION = "irrigation", _("Irrigation")
    BATIMENT = "batiment", _("Bâtiment et post-récolte")
    ELEVAGE = "elevage", _("Élevage")
    NUMERIQUE = "numerique", _("Numérique")
    AUTRE = "autre", _("Autre")


class TypeMateriel(models.TextChoices):
    # ── Automoteurs ──
    TRACTEUR_STANDARD = "tracteur_standard", _("Tracteur standard")
    TRACTEUR_VIGNERON = "tracteur_vigneron", _("Tracteur vigneron (étroit)")
    TRACTEUR_CHENILLE = "tracteur_chenille", _("Tracteur chenillé")
    TELESCOPIQUE = "telescopique", _("Télescopique ou chargeur")
    MOISSONNEUSE_BATTEUSE = "moissonneuse_batteuse", _("Moissonneuse-batteuse")
    ENSILEUSE = "ensileuse", _("Ensileuse")
    MACHINE_A_VENDANGER = "machine_a_vendanger", _("Machine à vendanger")
    AUTOMOTEUR_PULVERISATION = "automoteur_pulverisation", _("Automoteur de pulvérisation")
    QUAD = "quad", _("Quad ou UTV")
    CAMION = "camion", _("Camion")
    CHARIOT_ELEVATEUR = "chariot_elevateur", _("Chariot élévateur")

    # ── Travail du sol ──
    CHARRUE = "charrue", _("Charrue")
    DECHAUMEUR = "dechaumeur", _("Déchaumeur")
    CULTIVATEUR = "cultivateur", _("Cultivateur")
    VIBROCULTEUR = "vibroculteur", _("Vibroculteur")
    HERSE_ROTATIVE = "herse_rotative", _("Herse rotative")
    HERSE_ETRILLE = "herse_etrille", _("Herse étrille")
    ROULEAU = "rouleau", _("Rouleau")
    DECOMPACTEUR = "decompacteur", _("Décompacteur")
    BROYEUR = "broyeur", _("Broyeur")

    # ── Semis et plantation ──
    SEMOIR_LIGNE = "semoir_ligne", _("Semoir en ligne")
    SEMOIR_MONOGRAINE = "semoir_monograine", _("Semoir monograine")
    SEMOIR_DIRECT = "semoir_direct", _("Semoir direct")
    PLANTEUSE = "planteuse", _("Planteuse")
    BINEUSE = "bineuse", _("Bineuse")

    # ── Fertilisation et protection ──
    EPANDEUR_ENGRAIS = "epandeur_engrais", _("Épandeur d'engrais centrifuge")
    EPANDEUR_FUMIER = "epandeur_fumier", _("Épandeur à fumier")
    TONNE_A_LISIER = "tonne_a_lisier", _("Tonne à lisier")
    PULVERISATEUR = "pulverisateur", _("Pulvérisateur porté ou traîné")
    ATOMISEUR = "atomiseur", _("Atomiseur (arboriculture, viticulture)")

    # ── Récolte et fourrage ──
    FAUCHEUSE = "faucheuse", _("Faucheuse")
    FANEUSE = "faneuse", _("Faneuse")
    ANDAINEUR = "andaineur", _("Andaineur")
    PRESSE_A_BALLES = "presse_a_balles", _("Presse à balles")
    ENRUBANNEUSE = "enrubanneuse", _("Enrubanneuse")
    AUTOCHARGEUSE = "autochargeuse", _("Autochargeuse")
    ARRACHEUSE = "arracheuse", _("Arracheuse")

    # ── Transport et manutention ──
    REMORQUE = "remorque", _("Remorque")
    BENNE = "benne", _("Benne")
    PLATEAU = "plateau", _("Plateau")
    GODET = "godet", _("Godet")
    FOURCHE = "fourche", _("Fourche")
    PINCE_A_BALLES = "pince_a_balles", _("Pince à balles")

    # ── Irrigation ──
    POMPE = "pompe", _("Pompe")
    STATION_POMPAGE = "station_pompage", _("Station de pompage")
    ENROULEUR = "enrouleur", _("Enrouleur")
    PIVOT = "pivot", _("Pivot")
    RAMPE = "rampe", _("Rampe")
    GOUTTE_A_GOUTTE = "goutte_a_goutte", _("Goutte-à-goutte")
    FILTRATION = "filtration", _("Filtration")
    BORNE = "borne", _("Borne")

    # ── Bâtiment et post-récolte ──
    SECHOIR = "sechoir", _("Séchoir")
    TRIEUSE = "trieuse", _("Trieuse")
    CALIBREUSE = "calibreuse", _("Calibreuse")
    CHAMBRE_FROIDE = "chambre_froide", _("Chambre froide")
    GROUPE_ELECTROGENE = "groupe_electrogene", _("Groupe électrogène")
    NETTOYEUR_HP = "nettoyeur_hp", _("Nettoyeur haute pression")
    CUVE = "cuve", _("Cuve")
    PRESSOIR = "pressoir", _("Pressoir")

    # ── Élevage ──
    MELANGEUSE = "melangeuse", _("Mélangeuse")
    DESILEUSE = "desileuse", _("Désileuse")
    ROBOT_TRAITE = "robot_traite", _("Robot de traite")
    SALLE_TRAITE = "salle_traite", _("Salle de traite")
    TANK_A_LAIT = "tank_a_lait", _("Tank à lait")
    PAILLEUSE = "pailleuse", _("Pailleuse")
    RACLEUR = "racleur", _("Racleur")

    # ── Numérique ──
    CONSOLE_GPS = "console_gps", _("Console GPS")
    AUTOGUIDAGE_RTK = "autoguidage_rtk", _("Autoguidage RTK")
    STATION_METEO = "station_meteo", _("Station météo")
    DRONE = "drone", _("Drone")
    CAPTEUR = "capteur", _("Capteur")

    # ── Hors nomenclature ──
    AUTRE = "autre", _("Autre")


#: L'ordre des familles fait l'ordre du menu déroulant et des sections de la
#: page. Chaque type appartient à une famille et à une seule.
TYPES_PAR_FAMILLE = {
    Famille.AUTOMOTEUR: (
        TypeMateriel.TRACTEUR_STANDARD,
        TypeMateriel.TRACTEUR_VIGNERON,
        TypeMateriel.TRACTEUR_CHENILLE,
        TypeMateriel.TELESCOPIQUE,
        TypeMateriel.MOISSONNEUSE_BATTEUSE,
        TypeMateriel.ENSILEUSE,
        TypeMateriel.MACHINE_A_VENDANGER,
        TypeMateriel.AUTOMOTEUR_PULVERISATION,
        TypeMateriel.QUAD,
        TypeMateriel.CAMION,
        TypeMateriel.CHARIOT_ELEVATEUR,
    ),
    Famille.TRAVAIL_DU_SOL: (
        TypeMateriel.CHARRUE,
        TypeMateriel.DECHAUMEUR,
        TypeMateriel.CULTIVATEUR,
        TypeMateriel.VIBROCULTEUR,
        TypeMateriel.HERSE_ROTATIVE,
        TypeMateriel.HERSE_ETRILLE,
        TypeMateriel.ROULEAU,
        TypeMateriel.DECOMPACTEUR,
        TypeMateriel.BROYEUR,
    ),
    Famille.SEMIS: (
        TypeMateriel.SEMOIR_LIGNE,
        TypeMateriel.SEMOIR_MONOGRAINE,
        TypeMateriel.SEMOIR_DIRECT,
        TypeMateriel.PLANTEUSE,
        TypeMateriel.BINEUSE,
    ),
    Famille.FERTILISATION: (
        TypeMateriel.EPANDEUR_ENGRAIS,
        TypeMateriel.EPANDEUR_FUMIER,
        TypeMateriel.TONNE_A_LISIER,
        TypeMateriel.PULVERISATEUR,
        TypeMateriel.ATOMISEUR,
    ),
    Famille.RECOLTE: (
        TypeMateriel.FAUCHEUSE,
        TypeMateriel.FANEUSE,
        TypeMateriel.ANDAINEUR,
        TypeMateriel.PRESSE_A_BALLES,
        TypeMateriel.ENRUBANNEUSE,
        TypeMateriel.AUTOCHARGEUSE,
        TypeMateriel.ARRACHEUSE,
    ),
    Famille.TRANSPORT: (
        TypeMateriel.REMORQUE,
        TypeMateriel.BENNE,
        TypeMateriel.PLATEAU,
        TypeMateriel.GODET,
        TypeMateriel.FOURCHE,
        TypeMateriel.PINCE_A_BALLES,
    ),
    Famille.IRRIGATION: (
        TypeMateriel.POMPE,
        TypeMateriel.STATION_POMPAGE,
        TypeMateriel.ENROULEUR,
        TypeMateriel.PIVOT,
        TypeMateriel.RAMPE,
        TypeMateriel.GOUTTE_A_GOUTTE,
        TypeMateriel.FILTRATION,
        TypeMateriel.BORNE,
    ),
    Famille.BATIMENT: (
        TypeMateriel.SECHOIR,
        TypeMateriel.TRIEUSE,
        TypeMateriel.CALIBREUSE,
        TypeMateriel.CHAMBRE_FROIDE,
        TypeMateriel.GROUPE_ELECTROGENE,
        TypeMateriel.NETTOYEUR_HP,
        TypeMateriel.CUVE,
        TypeMateriel.PRESSOIR,
    ),
    Famille.ELEVAGE: (
        TypeMateriel.MELANGEUSE,
        TypeMateriel.DESILEUSE,
        TypeMateriel.ROBOT_TRAITE,
        TypeMateriel.SALLE_TRAITE,
        TypeMateriel.TANK_A_LAIT,
        TypeMateriel.PAILLEUSE,
        TypeMateriel.RACLEUR,
    ),
    Famille.NUMERIQUE: (
        TypeMateriel.CONSOLE_GPS,
        TypeMateriel.AUTOGUIDAGE_RTK,
        TypeMateriel.STATION_METEO,
        TypeMateriel.DRONE,
        TypeMateriel.CAPTEUR,
    ),
    Famille.AUTRE: (
        TypeMateriel.AUTRE,
    ),
}

#: Famille d'un type, dérivée de la table ci-dessus pour n'écrire la liste
#: qu'une fois.
FAMILLE_PAR_TYPE = {
    type_materiel: famille
    for famille, types in TYPES_PAR_FAMILLE.items()
    for type_materiel in types
}

#: Choix groupés par famille : le `<select>` du formulaire et l'admin y gagnent
#: leurs `<optgroup>`, sans quoi soixante-dix entrées défileraient à plat.
CHOIX_GROUPES = [
    (famille.label, [(t.value, t.label) for t in types])
    for famille, types in TYPES_PAR_FAMILLE.items()
]

#: Longueur du plus long code, pour que le `max_length` suive la liste plutôt
#: qu'un chiffre choisi à la main et vite dépassé.
LONGUEUR_MAX_TYPE = 32


def famille_de(type_materiel):
    """La famille d'un type, ou « Autre » si le type n'est pas connu."""
    return FAMILLE_PAR_TYPE.get(type_materiel, Famille.AUTRE)


def est_automoteur(type_materiel):
    """Un engin qui roule par lui-même : compteur horaire, carburant, carte grise."""
    return famille_de(type_materiel) == Famille.AUTOMOTEUR
