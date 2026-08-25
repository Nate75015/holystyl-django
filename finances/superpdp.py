"""Client de l'API SUPER PDP — plateforme agréée (PA/PDP).

SUPER PDP transporte les factures électroniques sur le réseau (Peppol et
annuaire français). On y dépose une facture au format EN16931 (UBL ou CII), la
plateforme se charge de l'acheminer et nous renvoie les statuts du cycle de vie.

Le module reste inerte sans identifiants : `is_configured()` renvoie False et
la page Facturation affiche une explication plutôt que de tenter un appel.

Authentification : OAuth 2.1 « client credentials ». L'access_token vaut 30
minutes ; on le garde en cache et on le renouvelle une minute avant l'échéance.
C'est la clé d'application qui détermine l'environnement — une clé bac à sable
ne peut pas toucher aux données de production.

Documentation : https://www.superpdp.tech/documentation/3
"""

from __future__ import annotations

import requests
from django.conf import settings
from django.core.cache import cache

#: Préfixe des routes métier. Les routes OAuth vivent sous /oauth2/.
API_PREFIX = "/v1.beta"

#: Marge de sécurité avant expiration du jeton, en secondes.
_TOKEN_MARGE = 60

#: Un appel réseau ne doit jamais bloquer une requête web indéfiniment.
_TIMEOUT = 20

CACHE_KEY_TOKEN = "superpdp:access_token"


class SuperPDPError(RuntimeError):
    """Appel API en échec — porte le message rendu par la plateforme."""

    def __init__(self, message: str, *, status: int | None = None, payload=None):
        super().__init__(message)
        self.status = status
        self.payload = payload


class SuperPDPNotConfigured(SuperPDPError):
    """Levée quand l'API est appelée sans identifiants configurés."""


def is_configured() -> bool:
    return bool(getattr(settings, "SUPERPDP_CLIENT_ID", "") and getattr(settings, "SUPERPDP_CLIENT_SECRET", ""))


def _url(path: str) -> str:
    return f"{settings.SUPERPDP_ENDPOINT.rstrip('/')}{path}"


def token(*, force: bool = False) -> str:
    """access_token OAuth2, mis en cache jusqu'à peu avant son expiration."""
    if not is_configured():
        raise SuperPDPNotConfigured(
            "SUPERPDP_CLIENT_ID / SUPERPDP_CLIENT_SECRET manquants — connexion SUPER PDP non configurée."
        )
    if not force:
        en_cache = cache.get(CACHE_KEY_TOKEN)
        if en_cache:
            return en_cache

    try:
        resp = requests.post(
            _url("/oauth2/token"),
            data={
                "grant_type": "client_credentials",
                "client_id": settings.SUPERPDP_CLIENT_ID,
                "client_secret": settings.SUPERPDP_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise SuperPDPError(f"SUPER PDP injoignable : {exc}") from exc

    if resp.status_code != 200:
        raise SuperPDPError(
            f"Authentification SUPER PDP refusée (HTTP {resp.status_code}). "
            "Vérifiez client_id et client_secret.",
            status=resp.status_code,
        )
    body = resp.json()
    acces = body.get("access_token") or ""
    if not acces:
        raise SuperPDPError("Réponse d'authentification SUPER PDP sans access_token.")
    duree = int(body.get("expires_in") or 1800)
    cache.set(CACHE_KEY_TOKEN, acces, max(duree - _TOKEN_MARGE, 30))
    return acces


def oublier_token() -> None:
    """Vide le jeton en cache (rotation d'identifiants, test de connexion)."""
    cache.delete(CACHE_KEY_TOKEN)


def _call(method: str, path: str, *, reessai: bool = True, **kwargs):
    """Appel authentifié. Un 401 déclenche un renouvellement du jeton."""
    entete = {"Authorization": f"Bearer {token()}"}
    entete.update(kwargs.pop("headers", {}))
    try:
        resp = requests.request(method, _url(path), headers=entete, timeout=_TIMEOUT, **kwargs)
    except requests.RequestException as exc:
        raise SuperPDPError(f"SUPER PDP injoignable : {exc}") from exc

    # Jeton périmé côté plateforme (rotation, révocation) : on rejoue une fois.
    if resp.status_code == 401 and reessai:
        oublier_token()
        return _call(method, path, reessai=False, **kwargs)

    if resp.status_code >= 400:
        raise SuperPDPError(_message_erreur(resp), status=resp.status_code, payload=_json_ou_none(resp))
    return resp


def _json_ou_none(resp):
    try:
        return resp.json()
    except ValueError:
        return None


def _message_erreur(resp) -> str:
    """Message lisible : la plateforme renvoie un corps JSON détaillé."""
    corps = _json_ou_none(resp)
    if isinstance(corps, dict):
        detail = corps.get("message") or corps.get("error_description") or corps.get("error")
        erreurs = corps.get("errors")
        if isinstance(erreurs, list) and erreurs:
            details = "; ".join(str(e.get("message", e)) if isinstance(e, dict) else str(e) for e in erreurs[:3])
            detail = f"{detail} — {details}" if detail else details
        if detail:
            return f"SUPER PDP : {detail} (HTTP {resp.status_code})"
    texte = (resp.text or "").strip()[:200]
    return f"SUPER PDP a répondu HTTP {resp.status_code}{' — ' + texte if texte else ''}"


# ── Entreprise ──────────────────────────────────────────────────────────


def company() -> dict:
    """Entreprise associée au jeton — sert aussi de test de connexion."""
    return _call("GET", f"{API_PREFIX}/companies/me").json()


# ── Factures ────────────────────────────────────────────────────────────


def validate(xml: str) -> dict:
    """Rapport de validation d'une facture, avant envoi (schematrons à jour)."""
    fichier = {"file": ("facture.xml", xml.encode("utf-8"), "application/xml")}
    return _call("POST", f"{API_PREFIX}/validation_reports", files=fichier).json()


def send_invoice(xml: str, *, external_id: str = "") -> dict:
    """Dépose une facture (UBL/CII) : elle part ensuite de façon asynchrone."""
    params = {"external_id": external_id} if external_id else None
    return _call(
        "POST",
        f"{API_PREFIX}/invoices",
        params=params,
        data=xml.encode("utf-8"),
        headers={"Content-Type": "application/xml"},
    ).json()


def invoice(invoice_id: int) -> dict:
    return _call("GET", f"{API_PREFIX}/invoices/{invoice_id}").json()


def invoices(**params) -> list[dict]:
    """Liste des factures (entrantes et sortantes par défaut)."""
    return _call("GET", f"{API_PREFIX}/invoices", params=params or None).json().get("data", [])


def invoice_events(invoice_id: int) -> list[dict]:
    return (
        _call("GET", f"{API_PREFIX}/invoice_events", params={"invoice_id": invoice_id})
        .json()
        .get("data", [])
    )


def create_invoice_event(invoice_id: int, status_code: str, *, details=None) -> dict:
    """Statut du cycle de vie (fr:204 … fr:220 ; fr:212 = encaissée)."""
    corps = {"invoice_id": invoice_id, "status_code": status_code}
    if details:
        corps["details"] = details
    return _call("POST", f"{API_PREFIX}/invoice_events", json=corps).json()


def generate_test_invoice(format: str = "ubl") -> str:
    """Facture d'exemple prête à envoyer — utile pour éprouver la chaîne."""
    return _call("GET", f"{API_PREFIX}/invoices/generate_test_invoice", params={"format": format}).text
