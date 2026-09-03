"""Réglages communs à toute la suite de tests."""

import pytest


@pytest.fixture(autouse=True)
def media_temporaire(tmp_path, settings):
    """Les fichiers écrits par un test n'ont rien à faire dans les vrais media.

    Sans cela, chaque exécution laissait des pièces d'identité, des logos et
    des baux de fixtures au milieu des documents de l'exploitation — jusqu'à
    plusieurs centaines. Chaque test reçoit son propre dossier, effacé avec
    lui.
    """
    settings.MEDIA_ROOT = str(tmp_path / "media")
