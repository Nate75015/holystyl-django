"""Les pièces d'identité de l'exploitant : carte, passeport, signature."""

import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
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
        "numero": (request.POST.get("numero") or "").strip()[:60],
        "delivre_le": _to_date(request.POST.get("delivre_le")),
        "expire_le": _to_date(request.POST.get("expire_le")),
        "notes": (request.POST.get("notes") or "").strip(),
    }


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
    exploitation = _exploitation(request)
    piece = get_object_or_404(Piece, pk=pk, exploitation=exploitation)

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
    exploitation = _exploitation(request)
    piece = get_object_or_404(Piece, pk=pk, exploitation=exploitation)
    piece.fichier.delete(save=False)
    piece.delete()
    messages.success(request, _("Pièce supprimée."))
    return redirect("identite:pieces")
