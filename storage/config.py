"""Réglages du stockage objet Scaleway, lus depuis l'environnement.

Module volontairement léger (n'importe PAS django-storages) : il peut être
importé partout — y compris quand le paquet S3 n'est pas installé — pour
savoir si le stockage objet est actif et récupérer ses paramètres.
"""

from __future__ import annotations

import os


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def region() -> str:
    return _env("AWS_S3_REGION_NAME", "fr-par")


def endpoint_url() -> str:
    """Endpoint Scaleway (fr-par par défaut) ; surchargeable via AWS_S3_ENDPOINT_URL."""
    return _env("AWS_S3_ENDPOINT_URL") or f"https://s3.{region()}.scw.cloud"


def bucket() -> str:
    return _env("AWS_STORAGE_BUCKET_NAME")


def is_enabled() -> bool:
    """Vrai si USE_S3 est activé (les media doivent aller sur l'objet Scaleway)."""
    return _env("USE_S3", "0").lower() in {"1", "true", "yes", "on"}


def is_configured() -> bool:
    """Vrai si le stockage objet est activé ET qu'un bucket est renseigné."""
    return is_enabled() and bool(bucket())
