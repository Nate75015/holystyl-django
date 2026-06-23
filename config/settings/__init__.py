"""Sélection de l'environnement de réglages via DJANGO_ENV (dev par défaut)."""

import os

_env = os.environ.get("DJANGO_ENV", "dev").lower()

if _env == "prod":
    from .prod import *  # noqa: F401,F403
else:
    from .dev import *  # noqa: F401,F403
