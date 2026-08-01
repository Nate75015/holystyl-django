"""Correspondance entre le schéma Cultiveau et les modèles Holystyl.

Ce fichier est le seul endroit à modifier quand le DTI évolue. L'importeur,
lui, ne connaît aucune table : il lit cette table de correspondance et
l'applique. Ajouter un modèle à l'échange, c'est donc ajouter une entrée ici
et une migration — pas réécrire du code d'import.

Chaque entrée répond à trois questions :

1. **Où va cette table ?** Un modèle Holystyl existant qu'on alimente
   (`exploitations.Exploitation`, `parcelles.Parcelle`…), un modèle de l'app
   `dti` créé pour l'occasion, ou nulle part — auquel cas la donnée reste
   consultable dans `DtiImport.payload` et rien n'est perdu.
2. **Quels champs, sous quels noms ?** Les deux schémas ont divergé sur le
   vocabulaire (`nom` / `name`, `surface_ha` / `area`) ; la traduction est ici,
   explicite, plutôt que dispersée dans l'importeur.
3. **Comment reconnaître un objet déjà connu ?** `cle` désigne le champ
   d'identité métier (le SIRET pour une exploitation) quand l'objet doit être
   retrouvé plutôt que recréé.

Le principe directeur est de **ne jamais dupliquer ce que Holystyl sait déjà**.
Une exploitation, une parcelle, une campagne culturale, une analyse NDVI et un
score DTI ont leurs modèles ici depuis longtemps : l'import les alimente. Seul
ce qui n'existait pas arrive dans l'app `dti`.
"""

from __future__ import annotations

#: Sentinelle : la table est reçue et archivée dans `DtiImport.payload`, mais
#: n'alimente aucun modèle. C'est un choix, pas un oubli — et le test de
#: couverture exige qu'il soit écrit.
ARCHIVE_SEULE = "archive_seule"


class Cible:
    """Destination d'une table du payload.

    `champs` va du nom **source** vers le nom **Holystyl**. Un champ absent de
    ce dictionnaire n'est pas importé : il reste dans le payload archivé.

    `reste_dans` nomme, le cas échéant, le `JSONField` qui recueille tous les
    champs non listés — utilisé pour l'équipement, dont les 175 colonnes
    polymorphes n'ont pas vocation à devenir 175 colonnes ici.
    """

    def __init__(self, modele, champs=None, cle=None, reste_dans=None,
                 parent=None, note=""):
        self.modele = modele
        self.champs = champs or {}
        self.cle = cle
        self.reste_dans = reste_dans
        self.parent = parent
        self.note = note


#: Ordre d'application. Il suit l'ordre d'insertion imposé par les dépendances
#: (§ 1 du schéma) : une parcelle avant les objets qui s'y rattachent, un
#: équipement avant la borne qui le désigne comme station de pompage.
#: `RessourceEau.station_pompage` et `Equipement.borne_source` forment un
#: cycle : l'importeur le résout en second passage.
CORRESPONDANCE = {

    # ── Ce que Holystyl connaît déjà : on alimente, on ne duplique pas ──

    "exploitation": Cible(
        "exploitations.Exploitation",
        cle="siret",
        note="Rattachement par SIRET. Jamais créée automatiquement : "
             "Exploitation.owner est obligatoire et personne ne peut deviner "
             "à quel utilisateur elle revient — d'où la quarantaine.",
        champs={
            "nom": "name",
            "prenom": "prenom",
            "forme_juridique": "forme_juridique",
            "siret": "siret",
            "pacage": "pacage",
            "tva_intra": "tva_intra",
            "annee_installation": "annee_installation",
            "voie_numero": "voie_numero",
            "voie_type": "voie_type",
            "voie_nom": "voie_nom",
            "code_postal": "postal_code",
            "ville": "city",
            "surface_totale_ha": "total_area",
            "sau_ha": "sau_ha",
        },
    ),

    "parcelles": Cible(
        "parcelles.Parcelle",
        cle="cadastral_ref",
        note="Les deux schémas portent déjà boundaries, cadastre_data et "
             "l'orientation des rangs — le recouvrement est presque total.",
        champs={
            "nom": "name",
            "surface_ha": "area",
            "latitude": "latitude",
            "longitude": "longitude",
            "boundaries": "boundaries",
            "orientation_rangs_deg": "orientation_rangs_deg",
            "cadastral_ref": "cadastral_ref",
            "commune": "commune",
            "surface_cadastrale_ha": "official_area_ha",
            "cadastre_data": "cadastre_data",
            "type_sol": "soil_type",
        },
    ),

    "parcelles.assolements": Cible(
        "parcelles.ParcelleCampagne",
        parent="parcelles",
        note="La campagne de la source est un libellé (« 2026 »), pas une "
             "date : elle alimente libelle, et non une année typée.",
        champs={
            "campagne": "libelle",
            "culture": "culture",
            "date_semis": "planting_date",
        },
    ),

    "parcelles.analyses_satellite": Cible(
        "irrigation.NdviData",
        parent="parcelles",
        note="Holystyl stocke déjà l'historique NDVI ; un modèle de plus "
             "ferait deux sources pour la même courbe. Les deux schémas "
             "nomment identiquement les indices, seuls la date et le taux de "
             "nuages diffèrent.",
        champs={
            "date_image": "acquisition_date",
            "cloud_cover_pct": "cloud_coverage",
            "ndvi_mean": "ndvi_mean", "ndvi_min": "ndvi_min", "ndvi_max": "ndvi_max",
            "ndwi_mean": "ndwi_mean", "ndwi_min": "ndwi_min", "ndwi_max": "ndwi_max",
            "source": "source",
        },
    ),

    # ── Ce qui n'existait pas : créé dans l'app dti ──

    "ressources_eau": Cible(
        "dti.RessourceEau",
        champs={
            "categorie": "categorie", "nom": "nom", "type_ressource": "type_ressource",
            "volume_autorise_m3": "volume_autorise_m3", "debit_max_m3h": "debit_max_m3h",
            "diametre_dn_mm": "diametre_dn_mm",
            "pression_requise_bar": "pression_requise_bar",
            "profondeur_m": "profondeur_m", "numero_point": "numero_point",
            "durete_th": "durete_th", "ph": "ph", "fer_mg_l": "fer_mg_l",
            "matieres_suspension": "matieres_suspension",
            "latitude": "latitude", "longitude": "longitude",
            "cadastral_ref": "cadastral_ref", "commune": "commune", "notes": "notes",
        },
    ),

    "ressources_eau.composants": Cible(
        "dti.Composant", parent="ressources_eau", reste_dans="caracteristiques",
        note="Matériel monté sur une borne : corps de borne, vannes, raccords. "
             "pn_bar, materiau, annee, fournisseur partent en caractéristiques.",
        champs={
            "type_composant": "type_composant", "marque": "marque", "modele": "modele",
            "etat": "etat", "dn_mm": "diametre_mm", "reference": "catalogue_ref",
            "notes": "notes",
        },
    ),

    "canalisations": Cible(
        "dti.Canalisation",
        champs={
            "nom": "nom", "ordre": "ordre", "diametre_mm": "diametre_mm",
            "diametre_int_mm": "diametre_int_mm", "materiau": "materiau",
            "longueur_m": "longueur_m", "debit_m3h": "debit_m3h",
            "geometry": "geometry",
        },
    ),

    "equipements": Cible(
        "dti.Equipement", reste_dans="caracteristiques",
        note="175 colonnes polymorphes à la source, ~90 % vides pour un objet "
             "donné. On garde en colonnes ce qui est commun à tous les types, "
             "donc requêtable ; le spécifique va dans caracteristiques sous ses "
             "noms d'origine.",
        champs={
            "nom": "nom", "type_equipement": "type_equipement",
            "categorie": "categorie", "marque": "marque", "modele": "modele",
            "annee": "annee", "etat": "etat",
            "latitude": "latitude", "longitude": "longitude",
        },
    ),

    "equipements.composants_station": Cible(
        "dti.Composant", parent="equipements", reste_dans="caracteristiques",
        note="Même modèle que les composants de borne : une pièce reste une "
             "pièce, seul son porteur change (cf. dti.Composant).",
        champs={
            "type_composant": "type_composant", "marque": "marque", "modele": "modele",
            "etat": "etat", "dn_mm": "diametre_mm", "catalogue_ref": "catalogue_ref",
            "notes": "notes",
        },
    ),

    "equipements.mesures_electriques": Cible(
        "dti.MesureElectrique", parent="equipements", reste_dans="caracteristiques",
        note="La source relève trois phases séparément (résistances et "
             "ampérages) ; on remonte en colonnes la mesure qui porte le "
             "diagnostic de vétusté, le détail par phase reste accessible.",
        champs={
            "date_mesure": "date",
            "resistance_isolement_mohm": "isolement_mohm",
            "amperage_ph1_a": "intensite_a",
            "tension_mesuree_v": "tension_v",
        },
    ),

    "mesures_debit": Cible(
        "dti.MesureDebit",
        champs={"date_mesure": "date", "point_libelle": "point_libelle",
                "methode": "methode", "debit_m3h": "debit_m3h",
                "pression_bar": "pression_bar", "notes": "notes"},
    ),

    # ── Reçu et archivé, pas encore exploité ──

    "organisation": Cible(ARCHIVE_SEULE, note="Conduite de l'irrigation : "
                          "tour d'eau, pilotage, pertes déclarées. À promouvoir "
                          "le jour où Holystyl en fait quelque chose."),
    "couts": Cible(ARCHIVE_SEULE, note="Poste de coûts du diagnostic ; "
                   "finances a son propre modèle, la fusion demande un arbitrage."),
    "cultures_irriguees": Cible(ARCHIVE_SEULE, note="Doublonne en partie "
                                "ParcelleCampagne — à réconcilier avant import."),
    "groupes_parcelles": Cible(ARCHIVE_SEULE, note="Notion d'îlot absente de "
                               "parcelles.Parcelle pour l'instant."),
    "parcelles.photos": Cible(ARCHIVE_SEULE, note="Traité par MediaDti."),
    "ressources_eau.photos": Cible(ARCHIVE_SEULE, note="Traité par MediaDti."),
    "canalisations.photos": Cible(ARCHIVE_SEULE, note="Traité par MediaDti."),
    "equipements.photos": Cible(ARCHIVE_SEULE, note="Traité par MediaDti."),
    "ressources_eau.composants.photos": Cible(ARCHIVE_SEULE, note="Traité par MediaDti."),
}

#: Version majeure du schéma source acceptée. Un import qui annonce autre chose
#: est rejeté plutôt que relu au jugé : mieux vaut un refus lisible qu'un
#: diagnostic à moitié compris.
SCHEMA_MAJEUR_SUPPORTE = "1"


def entrees_ordonnees():
    """Les entrées à importer, parents avant enfants."""
    return [(chemin, cible) for chemin, cible in CORRESPONDANCE.items()
            if cible.modele != ARCHIVE_SEULE]


def chemins_declares():
    """Tous les chemins connus — sert au test de couverture."""
    return set(CORRESPONDANCE)
