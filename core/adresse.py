"""Adresses : catégories de voie et autocomplétion.

Deux fournisseurs, choisis automatiquement :
  • Google Places (API « New ») dès que `GOOGLE_MAPS_API_KEY` est renseignée ;
  • sinon la Base Adresse Nationale (api-adresse.data.gouv.fr), gratuite et
    sans clé — déjà utilisée par le géocodage météo.

La clé Google reste côté serveur : le navigateur n'appelle que nos endpoints.
"""

import json
import unicodedata
import urllib.parse
import urllib.request

from django.conf import settings
from django.utils.translation import gettext_lazy as _

BAN_URL = "https://api-adresse.data.gouv.fr/search/"
GOOGLE_AUTOCOMPLETE_URL = "https://places.googleapis.com/v1/places:autocomplete"
GOOGLE_DETAILS_URL = "https://places.googleapis.com/v1/places/"

# Catégories de voie — nomenclature courante des adresses françaises.
TYPES_VOIE = [
    ("allee", _("Allée")),
    ("avenue", _("Avenue")),
    ("boulevard", _("Boulevard")),
    ("carrefour", _("Carrefour")),
    ("chaussee", _("Chaussée")),
    ("chemin", _("Chemin")),
    ("cite", _("Cité")),
    ("clos", _("Clos")),
    ("corniche", _("Corniche")),
    ("cote", _("Côte")),
    ("cour", _("Cour")),
    ("cours", _("Cours")),
    ("descente", _("Descente")),
    ("domaine", _("Domaine")),
    ("esplanade", _("Esplanade")),
    ("faubourg", _("Faubourg")),
    ("ferme", _("Ferme")),
    ("grande_rue", _("Grande rue")),
    ("hameau", _("Hameau")),
    ("impasse", _("Impasse")),
    ("lieu_dit", _("Lieu-dit")),
    ("lotissement", _("Lotissement")),
    ("mas", _("Mas")),
    ("montee", _("Montée")),
    ("parc", _("Parc")),
    ("passage", _("Passage")),
    ("place", _("Place")),
    ("placette", _("Placette")),
    ("plaine", _("Plaine")),
    ("plateau", _("Plateau")),
    ("pont", _("Pont")),
    ("port", _("Port")),
    ("promenade", _("Promenade")),
    ("quai", _("Quai")),
    ("quartier", _("Quartier")),
    ("residence", _("Résidence")),
    ("rond_point", _("Rond-point")),
    ("route", _("Route")),
    ("rue", _("Rue")),
    ("ruelle", _("Ruelle")),
    ("sentier", _("Sentier")),
    ("square", _("Square")),
    ("traverse", _("Traverse")),
    ("vallon", _("Vallon")),
    ("villa", _("Villa")),
    ("village", _("Village")),
    ("voie", _("Voie")),
    ("zone", _("Zone")),
    ("autre", _("Autre")),
]


def _sans_accent(texte):
    texte = unicodedata.normalize("NFKD", str(texte))
    return "".join(c for c in texte if not unicodedata.combining(c)).casefold()


def _index_categories():
    """Mots d'attaque d'une voie → catégorie (libellés + abréviations usuelles)."""
    index = {_sans_accent(label).replace("-", " "): value for value, label in TYPES_VOIE}
    index.update({
        "all": "allee", "av": "avenue", "ave": "avenue", "bd": "boulevard", "bld": "boulevard",
        "boul": "boulevard", "che": "chemin", "chem": "chemin", "imp": "impasse",
        "lieu dit": "lieu_dit", "ld": "lieu_dit", "lot": "lotissement", "pl": "place",
        "rd pt": "rond_point", "rpt": "rond_point", "res": "residence", "rte": "route",
        "sq": "square", "trav": "traverse", "vla": "villa", "zi": "zone", "za": "zone",
        "zac": "zone",
    })
    return index


_CATEGORIES = _index_categories()


def split_voie(libelle):
    """« Rue des Vergers » → ("rue", "des Vergers"). Catégorie vide si inconnue."""
    mots = (libelle or "").split()
    if not mots:
        return "", ""
    # Les catégories en deux mots (« grande rue ») d'abord ; les traits d'union
    # comptent comme des espaces (« Rond-point » ≡ « rond point »).
    for taille in (2, 1):
        if len(mots) >= taille:
            cle = _sans_accent(" ".join(mots[:taille])).replace("-", " ").strip(". ")
            if cle in _CATEGORIES:
                return _CATEGORIES[cle], " ".join(mots[taille:])
    return "", libelle.strip()


def _google_key():
    return getattr(settings, "GOOGLE_MAPS_API_KEY", "") or ""


def fournisseur():
    """Nom du fournisseur actif — utile pour les tests et le debug."""
    return "google" if _google_key() else "ban"


def _get_json(url, *, data=None, headers=None, timeout=6):
    req = urllib.request.Request(
        url, data=data, headers={"User-Agent": "Holystyl/1.0", **(headers or {})}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def _adresse_vide():
    return {"numero_voie": "", "type_voie": "", "voie": "", "code_postal": "", "ville": "", "pays": ""}


# ── Base Adresse Nationale (aucune clé requise) ─────────────────────

def _suggest_ban(query, limit):
    url = f"{BAN_URL}?limit={limit}&autocomplete=1&q={urllib.parse.quote(query)}"
    features = (_get_json(url).get("features") or [])[:limit]

    resultats = []
    for feature in features:
        props = feature.get("properties") or {}
        type_voie, voie = split_voie(props.get("street") or props.get("name") or "")
        resultats.append({
            "id": props.get("id") or "",
            "label": props.get("label") or "",
            # La BAN renvoie déjà l'adresse découpée : pas de second appel.
            "adresse": {
                "numero_voie": props.get("housenumber") or "",
                "type_voie": type_voie,
                "voie": voie,
                "code_postal": props.get("postcode") or "",
                "ville": props.get("city") or "",
                "pays": "France",
            },
        })
    return resultats


# ── Google Places (API « New ») ─────────────────────────────────────

def _suggest_google(query, limit):
    corps = json.dumps({
        "input": query,
        "includedRegionCodes": ["fr"],
        "languageCode": "fr",
    }).encode()
    data = _get_json(
        GOOGLE_AUTOCOMPLETE_URL,
        data=corps,
        headers={"Content-Type": "application/json", "X-Goog-Api-Key": _google_key()},
    )

    resultats = []
    for suggestion in (data.get("suggestions") or [])[:limit]:
        prediction = suggestion.get("placePrediction") or {}
        libelle = (prediction.get("text") or {}).get("text") or ""
        if prediction.get("placeId"):
            # Le détail (composants d'adresse) demande un second appel.
            resultats.append({"id": prediction["placeId"], "label": libelle, "adresse": None})
    return resultats


def _details_google(place_id):
    data = _get_json(
        GOOGLE_DETAILS_URL + urllib.parse.quote(place_id) + "?languageCode=fr",
        headers={"X-Goog-Api-Key": _google_key(), "X-Goog-FieldMask": "addressComponents"},
    )

    composants = {}
    for composant in data.get("addressComponents") or []:
        for type_ in composant.get("types") or []:
            composants.setdefault(type_, composant.get("longText") or "")

    type_voie, voie = split_voie(composants.get("route", ""))
    return {
        "numero_voie": composants.get("street_number", ""),
        "type_voie": type_voie,
        "voie": voie,
        "code_postal": composants.get("postal_code", ""),
        "ville": composants.get("locality") or composants.get("postal_town", ""),
        "pays": composants.get("country", ""),
    }


# ── API publique du module ──────────────────────────────────────────

def suggest(query, limit=6):
    """Suggestions d'adresses. Renvoie [] si le fournisseur est injoignable."""
    query = (query or "").strip()
    if len(query) < 3:
        return []
    try:
        if _google_key():
            return _suggest_google(query, limit)
        return _suggest_ban(query, limit)
    except Exception:  # noqa: BLE001 — réseau/quota : la saisie manuelle reste possible
        return []


def details(identifiant):
    """Composants d'une suggestion Google (inutile pour la BAN, déjà complète)."""
    identifiant = (identifiant or "").strip()
    if not identifiant or not _google_key():
        return _adresse_vide()
    try:
        return _details_google(identifiant)
    except Exception:  # noqa: BLE001
        return _adresse_vide()
