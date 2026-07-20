"""Backend de stockage objet Scaleway (S3) — django-storages + boto3.

Client de stockage par défaut du projet pour tous les documents / media
(FileField, ImageField, `default_storage`). Référencé par `STORAGES["default"]`
uniquement quand `USE_S3=1` (cf. config/settings/base.py) ; sinon le projet
reste sur le disque local et ce module n'est jamais importé.

La configuration (bucket, région, endpoint, identifiants) est lue depuis
l'environnement via `storage.config`, pas depuis les settings Django.
"""

from __future__ import annotations

import os

from storages.backends.s3 import S3Storage

from . import config


class ScalewayMediaStorage(S3Storage):
    """Media de l'exploitation stockés sur Scaleway Object Storage."""

    access_key = os.environ.get("AWS_ACCESS_KEY_ID", "")
    secret_key = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    bucket_name = config.bucket()
    region_name = config.region()
    endpoint_url = config.endpoint_url()
    file_overwrite = False
    default_acl = None
    querystring_auth = False
