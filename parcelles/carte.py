"""Ce qu'attendent les partials de sélection de parcelles.

Les pastilles seules ne suffisent pas : un agriculteur reconnaît ses
parcelles à leur forme, pas à leur référence cadastrale. Trois écrans
proposent donc le même choix — le planning, la tâche, la campagne — et
tiraient chacun leur GeoJSON de leur côté. Il est ici, une fois.
"""

from __future__ import annotations


def contexte(parcelles) -> dict:
    """`parcelles`, `parcelles_mappables` et `parcelles_geojson`, prêts à rendre."""
    parcelles = list(parcelles)
    return {
        "parcelles": parcelles,
        "parcelles_mappables": sum(1 for p in parcelles if p.boundaries),
        "parcelles_geojson": {
            "type": "FeatureCollection",
            "features": [
                {"type": "Feature", "geometry": p.boundaries,
                 "properties": {"id": p.pk, "name": p.name, "area": p.area}}
                for p in parcelles if p.boundaries
            ],
        },
    }
