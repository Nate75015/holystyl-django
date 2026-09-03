"""Les pièces d'identité de l'exploitant : carte, passeport, signature."""

import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation

from .models import Piece


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


def _to_date(valeur):
    from datetime import datetime

    try:
        return datetime.strptime(valeur, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@login_required
def pieces(request, type_piece=""):
    exploitation = _exploitation(request)
    base = (Piece.objects.filter(exploitation=exploitation)
            if exploitation else Piece.objects.none())
    if type_piece and type_piece in Piece.Type.values:
        base = base.filter(type_piece=type_piece)
    elif type_piece:
        type_piece = ""

    liste = list(base)
    return render(request, "identite/pieces.html", {
        "pieces": liste,
        # Une pièce périmée ne se découvre pas au moment où l'on en a besoin.
        "alertes": [p for p in liste if p.perimee or p.expire_bientot],
        "types": Piece.Type.choices,
        "type_actif": type_piece,
        "signature_active": Piece.signature_active(exploitation),
        "extensions": ",".join(sorted(Piece.EXTENSIONS)),
        "page_title": _("Identité"),
    })


def _refuse(request, fichier) -> bool:
    if os.path.splitext(fichier.name)[1].lower() not in Piece.EXTENSIONS:
        messages.error(request, _("Document non accepté : PDF ou photo seulement."))
        return True
    if fichier.size > Piece.TAILLE_MAX:
        messages.error(request, _("Le document ne doit pas dépasser 10 Mo."))
        return True
    return False


def _champs(request):
    type_piece = request.POST.get("type_piece") or Piece.Type.CARTE
    return {
        "type_piece": (type_piece if type_piece in Piece.Type.values else Piece.Type.CARTE),
        "titulaire": (request.POST.get("titulaire") or "").strip()[:160],
        "nom_usage": (request.POST.get("nom_usage") or "").strip()[:160],
        "numero": (request.POST.get("numero") or "").strip()[:60],
        "autorite": (request.POST.get("autorite") or "").strip()[:160],
        "prolongee": request.POST.get("prolongee") == "on",
        "par_defaut": request.POST.get("par_defaut") == "on",
        "delivre_le": _to_date(request.POST.get("delivre_le")),
        "expire_le": _to_date(request.POST.get("expire_le")),
        "notes": (request.POST.get("notes") or "").strip(),
    }


@login_required
@require_POST
def signature_definir(request):
    """Enregistre la signature tracée à l'écran, et la rend active.

    Le tracé arrive en data URL depuis le pavé : on le convertit en fichier
    plutôt que de le garder en base, pour qu'il s'insère dans un PDF comme
    n'importe quelle image.
    """
    import base64
    import binascii

    from django.core.files.base import ContentFile

    exploitation = _exploitation(request)
    if exploitation is None:
        return redirect("identite:pieces_type", type_piece="signature")

    trace = (request.POST.get("trace") or "").strip()
    prefixe = "data:image/png;base64,"
    if not trace.startswith(prefixe):
        messages.error(request, _("Tracé illisible : recommencez la signature."))
        return redirect("identite:pieces_type", type_piece="signature")
    try:
        binaire = base64.b64decode(trace[len(prefixe):], validate=True)
    except (binascii.Error, ValueError):
        messages.error(request, _("Tracé illisible : recommencez la signature."))
        return redirect("identite:pieces_type", type_piece="signature")
    if len(binaire) > Piece.TAILLE_MAX:
        messages.error(request, _("Le document ne doit pas dépasser 10 Mo."))
        return redirect("identite:pieces_type", type_piece="signature")

    piece = Piece(exploitation=exploitation, type_piece=Piece.Type.SIGNATURE,
                  titulaire=(request.POST.get("titulaire") or "").strip()[:160],
                  par_defaut=True)
    piece.fichier.save("signature.png", ContentFile(binaire), save=False)
    piece.save()
    messages.success(request, _("Signature enregistrée."))
    return redirect("identite:pieces_type", type_piece="signature")


@login_required
@require_POST
def signature_activer(request, pk):
    piece = _piece_ou_rien(request, pk, Piece.Type.SIGNATURE)
    if piece is None:
        return redirect("identite:pieces_type", type_piece="signature")
    piece.par_defaut = True
    piece.save()
    messages.success(request, _("Signature active mise à jour."))
    return redirect("identite:pieces_type", type_piece="signature")


@login_required
@require_POST
def piece_scanner(request):
    """Lit une pièce déposée et renvoie les champs, sans rien enregistrer.

    Le document ne transite que le temps de la lecture : rien n'est écrit
    avant que la personne ait relu et validé.
    """
    from django.http import JsonResponse

    from . import ocr

    fichier = request.FILES.get("fichier")
    if not fichier:
        return JsonResponse({"error": _("Aucun document reçu.")}, status=400)
    if os.path.splitext(fichier.name)[1].lower() not in Piece.EXTENSIONS:
        return JsonResponse({"error": _("Format non lisible : PDF ou photo.")}, status=400)
    if fichier.size > Piece.TAILLE_MAX:
        return JsonResponse({"error": _("Le document ne doit pas dépasser 10 Mo.")}, status=400)

    champs = ocr.lire(fichier.read(), fichier.name)
    if champs is None:
        return JsonResponse(
            {"error": _("Lecture impossible : Agent IA non configuré, ou document illisible.")},
            status=503)
    return JsonResponse({"champs": champs})


def _piece_ou_rien(request, pk, type_piece=None):
    """La pièce demandée, ou None avec un message.

    Une même réponse dans les deux cas où l'on n'y a pas droit : la pièce
    n'existe plus, ou elle appartient à quelqu'un d'autre. Distinguer les deux
    dirait à un curieux quels identifiants sont pris — sur des papiers
    d'identité, cela ne se donne pas.

    Et une page qui date est une situation ordinaire — deux onglets, un retour
    arrière : elle mérite un message, pas un écran d'erreur.
    """
    base = Piece.objects.filter(pk=pk, exploitation=_exploitation(request))
    if type_piece:
        base = base.filter(type_piece=type_piece)
    piece = base.first()
    if piece is None:
        messages.info(request, _("Cette pièce n'existe plus."))
    return piece


@login_required
@require_POST
def piece_ajouter(request):
    exploitation = _exploitation(request)
    fichier = request.FILES.get("fichier")
    if exploitation is None or not fichier or _refuse(request, fichier):
        return redirect("identite:pieces")

    Piece.objects.create(exploitation=exploitation, fichier=fichier, **_champs(request))
    messages.success(request, _("Pièce enregistrée."))
    return redirect("identite:pieces")


@login_required
@require_POST
def piece_modifier(request, pk):
    piece = _piece_ou_rien(request, pk)
    if piece is None:
        return redirect("identite:pieces")

    fichier = request.FILES.get("fichier")
    if fichier:
        if _refuse(request, fichier):
            return redirect("identite:pieces")
        piece.fichier = fichier
    for champ, valeur in _champs(request).items():
        setattr(piece, champ, valeur)
    piece.save()
    messages.success(request, _("Pièce modifiée."))
    return redirect("identite:pieces")


@login_required
@require_POST
def piece_supprimer(request, pk):
    piece = _piece_ou_rien(request, pk)
    if piece is None:
        return redirect("identite:pieces")
    piece.fichier.delete(save=False)
    piece.delete()
    messages.success(request, _("Pièce supprimée."))
    return redirect("identite:pieces")
