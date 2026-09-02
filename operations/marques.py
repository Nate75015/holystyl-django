"""Les marques proposées à la saisie, par famille de matériel.

Ce sont des suggestions, pas un référentiel. Le champ reste libre : un parc
compte toujours un constructeur local, un engin d'occasion rebadgé ou une
remorque montée à la ferme. La liste sert à éviter les dix orthographes de
« Deutz-Fahr », pas à refuser la onzième marque.

Elle est rangée par famille plutôt que par type : proposer DeLaval pour une
charrue n'aiderait personne, mais distinguer les marques d'une faucheuse de
celles d'une presse n'apporterait rien — les constructeurs de fenaison sont
les mêmes.
"""

from .materiel import Famille

#: Valeur du choix « Autre marque… » : elle ouvre la saisie libre au lieu de
#: désigner un constructeur. Jamais enregistrée telle quelle.
MARQUE_AUTRE = "__autre__"

MARQUES_PAR_FAMILLE = {
    Famille.AUTOMOTEUR: (
        # Tracteurs
        "John Deere", "Fendt", "New Holland", "Case IH", "Claas", "Massey Ferguson",
        "Deutz-Fahr", "Valtra", "Kubota", "Same", "Landini", "McCormick", "Steyr",
        "Antonio Carraro", "Goldoni", "Arbos",
        # Télescopiques et chargeurs
        "Manitou", "JCB", "Merlo", "Kramer", "Bobcat", "Weidemann", "Caterpillar", "Liebherr",
        # Récolte automotrice
        "Krone", "Pellenc", "Grégoire", "Ero",
        # Pulvérisation automotrice
        "Berthoud", "Tecnoma", "Matrot", "Artec", "Agrifac", "Horsch", "Amazone",
        # Quads et utilitaires
        "Polaris", "Can-Am", "Yamaha", "Honda",
        # Camions et manutention
        "Renault Trucks", "Iveco", "MAN", "Scania", "Mercedes-Benz", "Volvo",
        "Toyota", "Linde", "Fenwick", "Jungheinrich", "Still",
    ),
    Famille.TRAVAIL_DU_SOL: (
        "Kuhn", "Lemken", "Amazone", "Horsch", "Väderstad", "Grégoire-Besson",
        "Kverneland", "Pöttinger", "Maschio Gaspardo", "Sulky", "Quivogne",
        "Agrisem", "Carré", "Actisol", "Razol", "Souchu-Pinet", "Bednar",
        "Treffler", "Einböck", "Güttler", "Dal-Bo", "Alpego", "Rabe", "Nardi",
    ),
    Famille.SEMIS: (
        "Monosem", "Kuhn", "Väderstad", "Horsch", "Amazone", "Lemken", "Sulky",
        "Kverneland", "Pöttinger", "Maschio Gaspardo", "Sky Agriculture", "Carré",
        "Einböck", "Steketee", "Garford", "Grimme", "Dewulf", "AVR",
    ),
    Famille.FERTILISATION: (
        # Engrais
        "Amazone", "Sulky", "Kuhn", "Rauch", "Bogballe", "Vicon",
        # Effluents
        "Joskin", "Pichon", "Jeantil", "Samson", "Zunhammer", "Vredo",
        # Pulvérisation et arboriculture-viticulture
        "Berthoud", "Tecnoma", "Hardi", "Caruelle", "Blanchard", "Nicolas",
        "Pellenc", "Grégoire", "Caffini", "Ideal", "Dhugues",
    ),
    Famille.RECOLTE: (
        "Claas", "Krone", "Kuhn", "Pöttinger", "John Deere", "New Holland",
        "Massey Ferguson", "Fendt", "Kverneland", "Vicon", "Fella", "Lely",
        "McHale", "Strautmann", "Schuitemaker", "Jeantil", "Supertino",
        "Grimme", "Dewulf", "AVR", "Holmer", "Ropa",
    ),
    Famille.TRANSPORT: (
        "Joskin", "Rolland", "Gilibert", "Maupu", "Brimont", "La Campagne",
        "Legrand", "Leboulch", "Dangreville", "Pérard", "Chevance", "Beiser",
        "Fliegl", "Krampe",
        # Outils de chargeur
        "MX", "Quicke", "Stoll", "Alö", "Faucheux", "Fuchs",
    ),
    Famille.IRRIGATION: (
        # Enrouleurs, pivots et rampes
        "Otech", "Irrifrance", "Bauer", "Ocmis", "RM", "Casella",
        "Valley", "Zimmatic", "Lindsay", "Reinke",
        # Micro-irrigation
        "Netafim", "Rain Bird", "Toro", "Hunter",
        # Pompage et filtration
        "Grundfos", "KSB", "Caprari", "Rovatti", "Amiad", "Azud",
    ),
    Famille.BATIMENT: (
        # Séchage, tri, calibrage
        "Petkus", "Cimbria", "Denis", "Marot", "Kerian", "Manter", "Greefa", "MAF Roda",
        # Vinification
        "Bucher Vaslin", "Pera-Pellenc", "Diemme", "Scharfenberger",
        # Énergie et nettoyage
        "Kärcher", "Nilfisk", "SDMO", "Pramac", "Honda", "Kohler", "Hatz",
    ),
    Famille.ELEVAGE: (
        # Traite et lait
        "DeLaval", "Lely", "GEA", "BouMatic", "Fullwood", "Serap", "Milkline",
        # Alimentation
        "Kuhn", "Trioliet", "Siloking", "Keenan", "Storti", "Faresin",
        "Jeantil", "Emily", "Lucas G",
        # Paillage et raclage
        "Joskin", "Rabaud", "Dussau",
    ),
    Famille.NUMERIQUE: (
        "Trimble", "Topcon", "Raven", "Ag Leader", "Müller-Elektronik", "Teejet",
        "John Deere", "Case IH", "Claas", "Hexagon",
        # Stations météo et capteurs
        "Sencrop", "Weenat", "Pessl (Metos)", "Davis", "Sentek",
        # Drones
        "DJI", "Parrot", "Delair",
    ),
    # Hors nomenclature : aucune suggestion ne serait pertinente.
    Famille.AUTRE: (),
}


def marques_par_famille():
    """Les marques indexées par code de famille, prêtes à passer en JSON."""
    return {famille.value: list(marques) for famille, marques in MARQUES_PAR_FAMILLE.items()}
