"""Calculs géométriques sur les contours de parcelles (GeoJSON WGS84).

Sans dépendance géospatiale : les contours tiennent dans quelques dizaines
d'hectares, où la formule sphérique est largement assez précise.
"""

import math

RAYON_TERRE_M = 6378137.0


def anneau_exterieur(geometry):
    """Anneau extérieur [[lon, lat], …] d'un Polygon / MultiPolygon, ou None."""
    if not geometry:
        return None
    if geometry.get("type") == "Polygon":
        coords = geometry.get("coordinates") or []
        return coords[0] if coords else None
    if geometry.get("type") == "MultiPolygon":
        coords = geometry.get("coordinates") or []
        return coords[0][0] if coords and coords[0] else None
    return None


def surface_ha(anneau):
    """Surface (ha) d'un anneau [[lon, lat], …], ou None si le tracé est dégénéré."""
    if not anneau or len(anneau) < 3:
        return None
    total = 0.0
    n = len(anneau)
    for i in range(n):
        lon1, lat1 = anneau[i][0], anneau[i][1]
        lon2, lat2 = anneau[(i + 1) % n][0], anneau[(i + 1) % n][1]
        total += math.radians(lon2 - lon1) * (
            2 + math.sin(math.radians(lat1)) + math.sin(math.radians(lat2))
        )
    surface_m2 = abs(total * RAYON_TERRE_M * RAYON_TERRE_M / 2.0)
    return round(surface_m2 / 10000, 2)
