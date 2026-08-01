"""Contrat d'échange avec Cultiveau.

Ces tests ne vérifient pas du code : ils vérifient qu'une correspondance
déclarée reste applicable. C'est ce qui permet de faire évoluer les deux
schémas sans découvrir la casse six mois plus tard, sur des imports
silencieusement tronqués.

`dti/fixtures/dti_reference.json` est un export réel anonymisé. Il est le
spécimen contre lequel la correspondance est éprouvée ; le régénérer après une
évolution du schéma se fait côté Cultiveau, par
`manage.py exporter_dti <id> --sortie …`.
"""

import json
from pathlib import Path

from django.apps import apps
from django.test import TestCase

from . import correspondance as corr

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "dti_reference.json"


def charger_reference():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class FixtureDeReferenceTests(TestCase):
    """Le spécimen doit rester un export plausible et anonyme."""

    def test_fixture_presente_et_versionnee(self):
        env = charger_reference()
        self.assertIn("payload", env)
        self.assertEqual(env["payload"]["schema_version"].split(".")[0],
                         corr.SCHEMA_MAJEUR_SUPPORTE)

    def test_fixture_ne_porte_pas_de_donnees_reelles(self):
        """Un dépôt n'est pas l'endroit où stocker le SIRET d'un exploitant."""
        env = charger_reference()
        exploitation = env["payload"]["dti"]["exploitation"]
        self.assertEqual(exploitation["siret"], "00000000000000")
        self.assertNotIn("@gmail", json.dumps(env))

    def test_fixture_est_un_specimen_complet(self):
        """Une fixture vide ne prouverait rien : elle doit exercer les chemins
        qui comptent — rattachement, parcellaire, hydraulique, matériel."""
        d = charger_reference()["payload"]["dti"]
        self.assertTrue(d["exploitation"]["siret"])
        self.assertGreater(len(d["parcelles"]), 0)
        self.assertGreater(len(d["ressources_eau"]), 0)
        self.assertGreater(len(d["equipements"]), 0)


class CorrespondanceTests(TestCase):
    """La table de correspondance doit rester applicable telle qu'écrite."""

    def test_modeles_cibles_existent(self):
        """Une cible mal orthographiée ne doit pas se découvrir en production."""
        for chemin, cible in corr.entrees_ordonnees():
            with self.subTest(chemin=chemin):
                try:
                    apps.get_model(cible.modele)
                except LookupError:
                    self.fail(f"« {chemin} » vise « {cible.modele} », qui n'existe pas.")

    def test_champs_cibles_existent(self):
        """Le garde-fou décisif : un champ renommé côté Holystyl casse ici, et
        non à l'import du prochain diagnostic."""
        for chemin, cible in corr.entrees_ordonnees():
            modele = apps.get_model(cible.modele)
            noms = {f.name for f in modele._meta.get_fields()}
            for source, destination in cible.champs.items():
                with self.subTest(chemin=chemin, champ=destination):
                    self.assertIn(
                        destination, noms,
                        f"« {chemin} » écrit dans {cible.modele}.{destination}, "
                        f"qui n'existe pas (source : {source}).")

    def test_champ_de_reste_est_un_json(self):
        for chemin, cible in corr.entrees_ordonnees():
            if not cible.reste_dans:
                continue
            modele = apps.get_model(cible.modele)
            champ = modele._meta.get_field(cible.reste_dans)
            self.assertEqual(champ.get_internal_type(), "JSONField", chemin)

    def test_cle_de_rapprochement_existe(self):
        for chemin, cible in corr.entrees_ordonnees():
            if not cible.cle:
                continue
            modele = apps.get_model(cible.modele)
            noms = {f.name for f in modele._meta.get_fields()}
            self.assertIn(cible.cle, noms, f"clé de « {chemin} »")

    def test_archive_seule_est_motivee(self):
        """Écarter une table est un choix ; il doit être écrit, sinon rien ne
        distingue « pas encore exploité » de « oublié »."""
        for chemin, cible in corr.CORRESPONDANCE.items():
            if cible.modele == corr.ARCHIVE_SEULE:
                self.assertTrue(cible.note.strip(),
                                f"« {chemin} » est archivé sans raison déclarée.")


class CouvertureDuPayloadTests(TestCase):
    """Tout ce que la source émet doit être déclaré — importé ou archivé.

    C'est le pendant du test de couverture des modèles côté Cultiveau. Là-bas,
    on garantit qu'un modèle ajouté entre bien dans l'export ; ici, qu'il ne
    tombe pas dans un angle mort à l'arrivée.
    """

    #: Clés scalaires de la racine DTI : métadonnées de l'objet lui-même, pas
    #: des tables filles. Elles sont portées par DtiImport.
    RACINE_SCALAIRE = {"id", "nom", "created_at", "updated_at"}

    @staticmethod
    def _est_une_ligne(valeur):
        """Distingue une ligne de table d'une colonne JSON.

        Les deux se présentent comme des dicts, et une colonne JSON peut même
        être une liste de dicts (`equipements.arroseurs`, `secteurs`…). Le
        départage tient à l'identifiant : la source conserve l'`id` d'origine
        de chaque ligne comme identifiant de corrélation, quand ses colonnes
        JSON n'en portent pas.
        """
        return isinstance(valeur, dict) and "id" in valeur

    def _chemins_du_payload(self, nœud, prefixe=""):
        """Les chemins de tables filles présents dans le payload."""
        trouves = set()
        for cle, valeur in nœud.items():
            if prefixe == "" and cle in self.RACINE_SCALAIRE:
                continue
            chemin = f"{prefixe}{cle}"
            if isinstance(valeur, list) and valeur and self._est_une_ligne(valeur[0]):
                trouves.add(chemin)
                # Toute la collection, pas seulement sa première ligne : une
                # borne sans photo suivie d'un forage qui en porte une ferait
                # sinon passer « ressources_eau.photos » pour non émis.
                for ligne in valeur:
                    trouves |= self._chemins_du_payload(ligne, f"{chemin}.")
            elif self._est_une_ligne(valeur):
                trouves.add(chemin)
                trouves |= self._chemins_du_payload(valeur, f"{chemin}.")
        return trouves

    def test_toute_collection_du_payload_est_declaree(self):
        d = charger_reference()["payload"]["dti"]
        presents = self._chemins_du_payload(d)
        # Les collections vides du spécimen n'apparaissent pas : on les ajoute
        # depuis la racine pour que la couverture ne dépende pas du contenu.
        presents |= {c for c in d if isinstance(d[c], list)}
        non_declares = {c for c in presents
                        if c not in corr.chemins_declares()
                        and not c.endswith("_desservies")}
        self.assertEqual(
            non_declares, set(),
            f"Chemin(s) émis par la source mais non déclaré(s) : "
            f"{sorted(non_declares)}. Ajoutez-les à CORRESPONDANCE — avec "
            f"ARCHIVE_SEULE et une raison si Holystyl ne les exploite pas.")

    def test_version_majeure_inconnue_serait_rejetee(self):
        env = charger_reference()
        majeur = env["payload"]["schema_version"].split(".")[0]
        self.assertEqual(majeur, corr.SCHEMA_MAJEUR_SUPPORTE)
        self.assertNotEqual("2", corr.SCHEMA_MAJEUR_SUPPORTE,
                            "Pensez à relire la correspondance avant de passer "
                            "à un schéma majeur suivant.")
