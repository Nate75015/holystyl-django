"""Vues web Contrats : liste, KPIs, ajout et suppression (tenant-scoped)."""

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from planning.models import PlanningTask

from .models import ActeNotarie, Assurance, Bail, Contrat, Msa


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").replace("€", "").replace(" ", "").strip())
    except (TypeError, ValueError):
        return default


def _to_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


@login_required
def contrats(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    base = Contrat.objects.filter(exploitation=exploitation) if exploitation else Contrat.objects.none()

    total = base.aggregate(s=Sum("montant"))["s"] or 0
    nb_actifs = base.filter(statut=Contrat.Statut.ACTIF).count()

    return render(request, "contrat/contrats.html", {
        "contrats": base,
        "kpi_total": round(total),
        "kpi_count": base.count(),
        "kpi_actifs": nb_actifs,
        "types": Contrat.TypeContrat.choices,
        "statuts": Contrat.Statut.choices,
        "page_title": _("Contrats"),
    })


@login_required
@require_POST
def contrat_create(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    intitule = (request.POST.get("intitule") or "").strip()
    if exploitation and intitule:
        Contrat.objects.create(
            exploitation=exploitation,
            intitule=intitule,
            type_contrat=request.POST.get("type_contrat") or Contrat.TypeContrat.AUTRE,
            contractant=(request.POST.get("contractant") or "").strip(),
            date_debut=_to_date(request.POST.get("date_debut")),
            date_fin=_to_date(request.POST.get("date_fin")),
            montant=_to_float(request.POST.get("montant")),
            statut=request.POST.get("statut") or Contrat.Statut.BROUILLON,
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("contrat:contrats")


@login_required
@require_POST
def contrat_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    contrat = get_object_or_404(Contrat, pk=pk, exploitation=exploitation)
    contrat.delete()
    return redirect("contrat:contrats")


# ── Baux ────────────────────────────────────────────────────────────

@login_required
def baux(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    base = Bail.objects.filter(exploitation=exploitation) if exploitation else Bail.objects.none()

    surface = base.aggregate(s=Sum("surface_ha"))["s"] or 0
    loyer = base.aggregate(s=Sum("loyer_annuel"))["s"] or 0
    nb_actifs = base.filter(statut=Bail.Statut.ACTIF).count()

    from .models import DocumentBail

    liste = list(base.prefetch_related("documents"))
    return render(request, "contrat/baux.html", {
        "baux": liste,
        # La fenêtre de congé se ferme dix-huit mois avant le terme : passée,
        # le bail se renouvelle pour neuf ans. C'est l'échéance qui compte.
        "conges_imminents": [b for b in liste if b.conge_imminent],
        "kpi_count": len(liste),
        "kpi_actifs": nb_actifs,
        "kpi_surface": round(surface, 2),
        "kpi_loyer": round(loyer),
        "types": Bail.TypeBail.choices,
        "statuts": Bail.Statut.choices,
        "types_document": DocumentBail.Type.choices,
        "page_title": _("Baux"),
    })


@login_required
@require_POST
def _champs_bail(request):
    """Les champs d'un bail lus du POST, ou None sans désignation."""
    designation = (request.POST.get("designation") or "").strip()
    if not designation:
        return None

    type_bail = request.POST.get("type_bail") or Bail.TypeBail.FERME_9
    statut = request.POST.get("statut") or Bail.Statut.BROUILLON
    return {
        "designation": designation[:255],
        "type_bail": (type_bail if type_bail in Bail.TypeBail.values else Bail.TypeBail.AUTRE),
        "statut": statut if statut in Bail.Statut.values else Bail.Statut.BROUILLON,
        "bailleur": (request.POST.get("bailleur") or "").strip()[:255],
        "preneur": (request.POST.get("preneur") or "").strip()[:255],
        "contact_telephone": (request.POST.get("contact_telephone") or "").strip()[:30],
        "contact_email": (request.POST.get("contact_email") or "").strip(),
        "surface_ha": _to_float(request.POST.get("surface_ha")),
        "loyer_annuel": _to_float(request.POST.get("loyer_annuel")),
        "loyer_base_ha": _to_float(request.POST.get("loyer_base_ha")),
        "annee_reference": _to_int(request.POST.get("annee_reference")),
        "date_debut": _to_date(request.POST.get("date_debut")),
        "date_fin": _to_date(request.POST.get("date_fin")),
        "date_resiliation": _to_date(request.POST.get("date_resiliation")),
        # Les délais et les charges : ce qui se joue au renouvellement.
        "preavis_conge_mois": _to_int(request.POST.get("preavis_conge_mois")) or 18,
        "renouvellement_tacite": request.POST.get("renouvellement_tacite") == "on",
        "date_revision_fermage": _to_date(request.POST.get("date_revision_fermage")),
        "charges_recuperables": (request.POST.get("charges_recuperables") or "").strip(),
        "taxe_fonciere_part_preneur": _to_float(request.POST.get("taxe_fonciere_part_preneur")),
        "etat_des_lieux": request.POST.get("etat_des_lieux") == "on",
        "clauses_environnementales": (request.POST.get("clauses_environnementales") or "").strip(),
        "references_cadastrales": (request.POST.get("references_cadastrales") or "").strip(),
        "droit_preemption": (request.POST.get("droit_preemption") or "").strip(),
        "notes": (request.POST.get("notes") or "").strip(),
    }


@login_required
@require_POST
def bail_create(request, pk=None):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    if exploitation is None:
        return redirect("contrat:baux")

    champs = _champs_bail(request)
    if champs is None:
        messages.error(request, _("Un bail a besoin d'une désignation."))
        return redirect("contrat:baux")

    bail = (get_object_or_404(Bail, pk=pk, exploitation=exploitation)
            if pk else Bail(exploitation=exploitation))
    for champ, valeur in champs.items():
        setattr(bail, champ, valeur)
    bail.save()

    fichier = request.FILES.get("document")
    if fichier:
        _archiver_document_bail(bail, request, fichier)
    return redirect("contrat:baux")


def _archiver_document_bail(bail, request, fichier):
    """Range une pièce au dossier du bail, avec les mêmes garde-fous."""
    import os

    from .models import DocumentBail

    if os.path.splitext(fichier.name)[1].lower() not in EXTENSIONS_DOC:
        messages.error(request, _("Document non accepté : PDF ou photo seulement."))
        return None
    if fichier.size > TAILLE_MAX_DOC:
        messages.error(request, _("Le document ne doit pas dépasser 10 Mo."))
        return None

    type_document = request.POST.get("type_document") or DocumentBail.Type.BAIL
    return DocumentBail.objects.create(
        bail=bail, fichier=fichier, nom=fichier.name[:255],
        type_document=(type_document if type_document in DocumentBail.Type.values
                       else DocumentBail.Type.AUTRE))


@login_required
@require_POST
def bail_document(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    bail = get_object_or_404(Bail, pk=pk, exploitation=exploitation)
    fichier = request.FILES.get("document")
    if fichier:
        _archiver_document_bail(bail, request, fichier)
    return redirect("contrat:baux")


@login_required
@require_POST
def bail_document_delete(request, pk):
    from .models import DocumentBail

    exploitation = Exploitation.objects.filter(owner=request.user).first()
    get_object_or_404(DocumentBail, pk=pk, bail__exploitation=exploitation).delete()
    return redirect("contrat:baux")


@login_required
@require_POST
def bail_scanner(request):
    """Lit un bail déposé et renvoie les champs, sans rien enregistrer."""
    import os

    from django.http import JsonResponse

    from . import bail_ocr

    fichier = request.FILES.get("document")
    if not fichier:
        return JsonResponse({"error": _("Aucun document reçu.")}, status=400)
    if os.path.splitext(fichier.name)[1].lower() not in EXTENSIONS_DOC:
        return JsonResponse({"error": _("Format non lisible : PDF ou photo.")}, status=400)
    if fichier.size > TAILLE_MAX_DOC:
        return JsonResponse({"error": _("Le document ne doit pas dépasser 10 Mo.")}, status=400)

    champs = bail_ocr.lire(fichier.read(), fichier.name)
    if champs is None:
        return JsonResponse(
            {"error": _("Lecture impossible : Agent IA non configuré, ou document illisible.")},
            status=503)
    return JsonResponse({"champs": champs})


@login_required
@require_POST
def bail_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    bail = get_object_or_404(Bail, pk=pk, exploitation=exploitation)
    bail.delete()
    return redirect("contrat:baux")


# ── Actes notariés ──────────────────────────────────────────────────

@login_required
def actes_notaries(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    base = (ActeNotarie.objects.filter(exploitation=exploitation)
            if exploitation else ActeNotarie.objects.none())

    from .models import DocumentActe

    liste = list(base.prefetch_related("documents"))
    total = base.aggregate(s=Sum("montant"))["s"] or 0
    surface = base.aggregate(s=Sum("surface_ha"))["s"] or 0

    return render(request, "contrat/actes.html", {
        "actes": liste,
        # Une promesse qui expire ou une hypothèque à lever : les deux
        # échéances qu'on ne rattrape pas une fois passées.
        "actions_imminentes": [a for a in liste if a.action_imminente or a.action_depassee],
        "publications_attendues": [a for a in liste if a.publication_en_attente],
        "kpi_count": len(liste),
        "kpi_en_vigueur": sum(1 for a in liste if a.est_en_vigueur),
        "kpi_surface": round(surface, 2),
        "kpi_total": round(total),
        "types": ActeNotarie.TypeActe.choices,
        "statuts": ActeNotarie.Statut.choices,
        "types_document": DocumentActe.Type.choices,
        "page_title": _("Patrimoine"),
    })


def _champs_acte(request):
    """Les champs d'un acte lus du POST, ou None sans objet."""
    objet = (request.POST.get("objet") or "").strip()
    if not objet:
        return None

    type_acte = request.POST.get("type_acte") or ActeNotarie.TypeActe.AUTRE
    statut = request.POST.get("statut") or ActeNotarie.Statut.PROJET
    return {
        "objet": objet[:255],
        "type_acte": (type_acte if type_acte in ActeNotarie.TypeActe.values
                      else ActeNotarie.TypeActe.AUTRE),
        "statut": (statut if statut in ActeNotarie.Statut.values
                   else ActeNotarie.Statut.PROJET),
        "notaire": (request.POST.get("notaire") or "").strip()[:255],
        "telephone_notaire": (request.POST.get("telephone_notaire") or "").strip()[:30],
        "email_notaire": (request.POST.get("email_notaire") or "").strip(),
        "parties": (request.POST.get("parties") or "").strip()[:255],
        "reference": (request.POST.get("reference") or "").strip()[:100],
        "date_promesse": _to_date(request.POST.get("date_promesse")),
        "date_limite_realisation": _to_date(request.POST.get("date_limite_realisation")),
        "date_signature": _to_date(request.POST.get("date_signature")),
        "date_publication": _to_date(request.POST.get("date_publication")),
        "date_peremption": _to_date(request.POST.get("date_peremption")),
        "mainlevee_obtenue": request.POST.get("mainlevee_obtenue") == "on",
        "surface_ha": _to_float(request.POST.get("surface_ha")),
        "references_cadastrales": (request.POST.get("references_cadastrales") or "").strip(),
        "montant": _to_float(request.POST.get("montant")),
        "frais_notaire": _to_float(request.POST.get("frais_notaire")),
        "droits_enregistrement": _to_float(request.POST.get("droits_enregistrement")),
        "conditions_suspensives": (request.POST.get("conditions_suspensives") or "").strip(),
        "charges_et_servitudes": (request.POST.get("charges_et_servitudes") or "").strip(),
        "droit_preemption": (request.POST.get("droit_preemption") or "").strip(),
        "notes": (request.POST.get("notes") or "").strip(),
    }


@login_required
@require_POST
def acte_create(request, pk=None):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    if exploitation is None:
        return redirect("contrat:actes")

    champs = _champs_acte(request)
    if champs is None:
        messages.error(request, _("Un acte a besoin d'un objet."))
        return redirect("contrat:actes")

    acte = (get_object_or_404(ActeNotarie, pk=pk, exploitation=exploitation)
            if pk else ActeNotarie(exploitation=exploitation))
    for champ, valeur in champs.items():
        setattr(acte, champ, valeur)
    acte.save()

    fichier = request.FILES.get("document")
    if fichier:
        _archiver_document_acte(acte, request, fichier)
    return redirect("contrat:actes")


def _archiver_document_acte(acte, request, fichier):
    """Range une pièce au dossier de l'acte, avec les mêmes garde-fous."""
    import os

    from .models import DocumentActe

    if os.path.splitext(fichier.name)[1].lower() not in EXTENSIONS_DOC:
        messages.error(request, _("Document non accepté : PDF ou photo seulement."))
        return None
    if fichier.size > TAILLE_MAX_DOC:
        messages.error(request, _("Le document ne doit pas dépasser 10 Mo."))
        return None

    type_document = request.POST.get("type_document") or DocumentActe.Type.ACTE
    return DocumentActe.objects.create(
        acte=acte, fichier=fichier, nom=fichier.name[:255],
        type_document=(type_document if type_document in DocumentActe.Type.values
                       else DocumentActe.Type.AUTRE))


@login_required
@require_POST
def acte_document(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    acte = get_object_or_404(ActeNotarie, pk=pk, exploitation=exploitation)
    fichier = request.FILES.get("document")
    if fichier:
        _archiver_document_acte(acte, request, fichier)
    return redirect("contrat:actes")


@login_required
@require_POST
def acte_document_delete(request, pk):
    from .models import DocumentActe

    exploitation = Exploitation.objects.filter(owner=request.user).first()
    get_object_or_404(DocumentActe, pk=pk, acte__exploitation=exploitation).delete()
    return redirect("contrat:actes")


@login_required
@require_POST
def acte_scanner(request):
    """Lit un acte déposé et renvoie les champs, sans rien enregistrer."""
    import os

    from django.http import JsonResponse

    from . import acte_ocr

    fichier = request.FILES.get("document")
    if not fichier:
        return JsonResponse({"error": _("Aucun document reçu.")}, status=400)
    if os.path.splitext(fichier.name)[1].lower() not in EXTENSIONS_DOC:
        return JsonResponse({"error": _("Format non lisible : PDF ou photo.")}, status=400)
    if fichier.size > TAILLE_MAX_DOC:
        return JsonResponse({"error": _("Le document ne doit pas dépasser 10 Mo.")}, status=400)

    champs = acte_ocr.lire(fichier.read(), fichier.name)
    if champs is None:
        return JsonResponse(
            {"error": _("Lecture impossible : Agent IA non configuré, ou document illisible.")},
            status=503)
    return JsonResponse({"champs": champs})


@login_required
@require_POST
def acte_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    acte = get_object_or_404(ActeNotarie, pk=pk, exploitation=exploitation)
    acte.delete()
    return redirect("contrat:actes")


# ── Assurances ──────────────────────────────────────────────────────

@login_required
def assurances(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    base = Assurance.objects.filter(exploitation=exploitation) if exploitation else Assurance.objects.none()

    prime = base.aggregate(s=Sum("prime_annuelle"))["s"] or 0
    capital = base.aggregate(s=Sum("capital_assure"))["s"] or 0
    nb_actives = base.filter(statut=Assurance.Statut.ACTIVE).count()

    polices = list(base.prefetch_related("documents"))
    from .models import DocumentAssurance

    return render(request, "contrat/assurances.html", {
        "assurances": polices,
        # Ce qui arrive à échéance : c'est là que se joue la renégociation,
        # le préavis de résiliation courant étant de deux mois.
        "echeances_proches": [a for a in polices if a.echeance_proche],
        "kpi_count": len(polices),
        "kpi_actives": nb_actives,
        "kpi_prime": round(prime),
        "kpi_capital": round(capital),
        "types": Assurance.TypeAssurance.choices,
        "statuts": Assurance.Statut.choices,
        "types_document": DocumentAssurance.Type.choices,
        "page_title": _("Assurances"),
    })


def _to_int(valeur):
    try:
        return int(str(valeur).strip())
    except (TypeError, ValueError):
        return None


def _champs_assurance(request):
    """Les champs d'une police lus du POST, ou None sans intitulé."""
    intitule = (request.POST.get("intitule") or "").strip()
    if not intitule:
        return None

    type_assurance = request.POST.get("type_assurance") or Assurance.TypeAssurance.MULTIRISQUE
    statut = request.POST.get("statut") or Assurance.Statut.BROUILLON
    return {
        "intitule": intitule[:255],
        "type_assurance": (type_assurance if type_assurance in Assurance.TypeAssurance.values
                           else Assurance.TypeAssurance.AUTRE),
        "statut": statut if statut in Assurance.Statut.values else Assurance.Statut.BROUILLON,
        "assureur": (request.POST.get("assureur") or "").strip()[:255],
        "numero_police": (request.POST.get("numero_police") or "").strip()[:100],
        "prime_annuelle": _to_float(request.POST.get("prime_annuelle")),
        "capital_assure": _to_float(request.POST.get("capital_assure")),
        "plafond": _to_float(request.POST.get("plafond")),
        "date_debut": _to_date(request.POST.get("date_debut")),
        "date_fin": _to_date(request.POST.get("date_fin")),
        "date_resiliation": _to_date(request.POST.get("date_resiliation")),
        # Ce qui sert le jour du sinistre.
        "garanties": (request.POST.get("garanties") or "").strip(),
        "exclusions": (request.POST.get("exclusions") or "").strip(),
        "franchise": (request.POST.get("franchise") or "").strip()[:255],
        "delai_declaration_jours": _to_int(request.POST.get("delai_declaration_jours")),
        "procedure_sinistre": (request.POST.get("procedure_sinistre") or "").strip(),
        "telephone_sinistre": (request.POST.get("telephone_sinistre") or "").strip()[:30],
        "email_sinistre": (request.POST.get("email_sinistre") or "").strip(),
        # L'interlocuteur, et la sortie.
        "courtier": (request.POST.get("courtier") or "").strip()[:255],
        "telephone_courtier": (request.POST.get("telephone_courtier") or "").strip()[:30],
        "email_courtier": (request.POST.get("email_courtier") or "").strip(),
        "tacite_reconduction": request.POST.get("tacite_reconduction") == "on",
        "preavis_resiliation_jours": _to_int(request.POST.get("preavis_resiliation_jours")),
        "notes": (request.POST.get("notes") or "").strip(),
    }


@login_required
@require_POST
def assurance_create(request, pk=None):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    if exploitation is None:
        return redirect("contrat:assurances")

    champs = _champs_assurance(request)
    if champs is None:
        messages.error(request, _("Une police a besoin d'un intitulé."))
        return redirect("contrat:assurances")

    assurance = (get_object_or_404(Assurance, pk=pk, exploitation=exploitation)
                 if pk else Assurance(exploitation=exploitation))
    for champ, valeur in champs.items():
        setattr(assurance, champ, valeur)
    assurance.save()

    fichier = request.FILES.get("document")
    if fichier:
        _archiver_document(assurance, request, fichier)
    return redirect("contrat:assurances")


#: Ce qu'on accepte comme pièce jointe. Une police se scanne au téléphone ou
#: s'exporte en PDF ; le reste n'a rien à faire ici.
EXTENSIONS_DOC = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".heic"}
TAILLE_MAX_DOC = 10 * 1024 * 1024


def _archiver_document(assurance, request, fichier, type_document=None):
    """Range une pièce au dossier, en gardant ce que l'IA en a lu."""
    import os

    from .models import DocumentAssurance

    if os.path.splitext(fichier.name)[1].lower() not in EXTENSIONS_DOC:
        messages.error(request, _("Document non accepté : PDF ou photo seulement."))
        return None
    if fichier.size > TAILLE_MAX_DOC:
        messages.error(request, _("Le document ne doit pas dépasser 10 Mo."))
        return None

    type_document = type_document or request.POST.get("type_document") or DocumentAssurance.Type.POLICE
    return DocumentAssurance.objects.create(
        assurance=assurance, fichier=fichier, nom=fichier.name[:255],
        type_document=(type_document if type_document in DocumentAssurance.Type.values
                       else DocumentAssurance.Type.AUTRE))


@login_required
@require_POST
def assurance_document(request, pk):
    """Ajoute une pièce au dossier d'une police déjà enregistrée."""
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    assurance = get_object_or_404(Assurance, pk=pk, exploitation=exploitation)
    fichier = request.FILES.get("document")
    if fichier:
        _archiver_document(assurance, request, fichier)
    return redirect("contrat:assurances")


@login_required
@require_POST
def assurance_document_delete(request, pk):
    from .models import DocumentAssurance

    exploitation = Exploitation.objects.filter(owner=request.user).first()
    get_object_or_404(DocumentAssurance, pk=pk,
                      assurance__exploitation=exploitation).delete()
    return redirect("contrat:assurances")


@login_required
@require_POST
def assurance_scanner(request):
    """Lit une police déposée et renvoie les champs, sans rien enregistrer.

    L'exploitant relit et corrige avant de valider : une franchise mal recopiée
    se découvre le jour du sinistre.
    """
    from django.http import JsonResponse

    from . import assurance_ocr

    fichier = request.FILES.get("document")
    if not fichier:
        return JsonResponse({"error": _("Aucun document reçu.")}, status=400)

    import os

    if os.path.splitext(fichier.name)[1].lower() not in EXTENSIONS_DOC:
        return JsonResponse({"error": _("Format non lisible : PDF ou photo.")}, status=400)
    if fichier.size > TAILLE_MAX_DOC:
        return JsonResponse({"error": _("Le document ne doit pas dépasser 10 Mo.")}, status=400)

    champs = assurance_ocr.lire(fichier.read(), fichier.name)
    if champs is None:
        return JsonResponse(
            {"error": _("Lecture impossible : Agent IA non configuré, ou document illisible.")},
            status=503)
    return JsonResponse({"champs": champs})


@login_required
@require_POST
def assurance_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    assurance = get_object_or_404(Assurance, pk=pk, exploitation=exploitation)
    assurance.delete()
    return redirect("contrat:assurances")


# ── MSA (Mutualité Sociale Agricole) ────────────────────────────────

@login_required
def msa(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    base = Msa.objects.filter(exploitation=exploitation) if exploitation else Msa.objects.none()

    total = base.aggregate(s=Sum("montant"))["s"] or 0
    du = base.filter(statut__in=[Msa.Statut.A_PAYER, Msa.Statut.EN_RETARD]).aggregate(s=Sum("montant"))["s"] or 0

    return render(request, "contrat/msa.html", {
        "cotisations": base,
        "kpi_count": base.count(),
        "kpi_a_payer": base.filter(statut__in=[Msa.Statut.A_PAYER, Msa.Statut.EN_RETARD]).count(),
        "kpi_total": round(total),
        "kpi_du": round(du),
        "types": Msa.TypeCotisation.choices,
        "statuts": Msa.Statut.choices,
        "page_title": _("MSA"),
    })


@login_required
@require_POST
def msa_create(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    intitule = (request.POST.get("intitule") or "").strip()
    if exploitation and intitule:
        Msa.objects.create(
            exploitation=exploitation,
            intitule=intitule,
            type_cotisation=request.POST.get("type_cotisation") or Msa.TypeCotisation.AMEXA,
            numero_adherent=(request.POST.get("numero_adherent") or "").strip(),
            caisse=(request.POST.get("caisse") or "").strip(),
            montant=_to_float(request.POST.get("montant")),
            periode=(request.POST.get("periode") or "").strip(),
            date_echeance=_to_date(request.POST.get("date_echeance")),
            statut=request.POST.get("statut") or Msa.Statut.A_PAYER,
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("contrat:msa")


@login_required
@require_POST
def msa_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    get_object_or_404(Msa, pk=pk, exploitation=exploitation).delete()
    return redirect("contrat:msa")


@login_required
@require_POST
def rendez_vous_create(request):
    """Planifie un rendez-vous avec un professionnel depuis la page Assurances.

    Le rendez-vous atterrit dans le planning existant (une tâche de type
    « rendez-vous ») plutôt que dans un agenda parallèle.
    """
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    professionnel = (request.POST.get("professionnel") or "").strip()
    if not (exploitation and professionnel):
        messages.error(request, _("Indiquez le professionnel à rencontrer."))
        return redirect("contrat:assurances")

    debut = parse_datetime(request.POST.get("date_debut") or "")
    if debut and timezone.is_naive(debut):
        debut = timezone.make_aware(debut)
    objet = (request.POST.get("objet") or "").strip() or _("Rendez-vous assurance")

    PlanningTask.objects.create(
        exploitation=exploitation,
        created_by=request.user,
        type="rendez_vous",
        titre=f"{objet} — {professionnel}"[:255],
        description=(request.POST.get("notes") or "").strip(),
        client_nom=professionnel[:255],
        client_telephone=(request.POST.get("telephone") or "").strip()[:50],
        date_debut=debut,
        duree_estimee_minutes=int(_to_float(request.POST.get("duree_minutes"), 60) or 60),
        # Sans date, le rendez-vous reste à caler : il va dans le backlog.
        is_backlog=debut is None,
    )
    messages.success(request, _("Rendez-vous ajouté au planning."))
    return redirect("contrat:assurances")


# ── Drive : les documents de l'exploitation, rangés ───────────────────
#
# Un drive doit accepter ce qui arrive vraiment d'un tiers : le PDF avant
# tout, mais aussi le tableur du comptable ou la photo d'un courrier. Plus
# large que les pièces attachées à un bail, dont on sait ce qu'on attend.
EXTENSIONS_DRIVE = EXTENSIONS_DOC | {
    ".doc", ".docx", ".odt", ".rtf", ".txt",
    ".xls", ".xlsx", ".ods", ".csv",
    ".ppt", ".pptx", ".odp", ".zip", ".gif",
}
TAILLE_MAX_DRIVE = 50 * 1024 * 1024


def _drive_dossier(request, pk):
    """Le dossier demandé s'il appartient à la ferme, sinon la racine.

    Rendre la racine plutôt qu'un 404 : un dossier supprimé depuis un autre
    onglet ne doit pas jeter l'exploitant sur une page d'erreur.
    """
    from .models import Dossier

    if not pk:
        return None
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    return Dossier.objects.filter(pk=pk, exploitation=exploitation).first()


def _drive_refuse(request, fichier):
    """Vrai — et le dit — si ce fichier n'a pas sa place dans le drive."""
    import os

    if os.path.splitext(fichier.name)[1].lower() not in EXTENSIONS_DRIVE:
        messages.error(request, _("« %(nom)s » : format non accepté.") % {"nom": fichier.name})
        return True
    if fichier.size > TAILLE_MAX_DRIVE:
        messages.error(request, _("« %(nom)s » dépasse 50 Mo.") % {"nom": fichier.name})
        return True
    return False


def _drive_retour(dossier):
    if dossier is None:
        return redirect("contrat:drive")
    return redirect("contrat:drive_dossier", pk=dossier.pk)


@login_required
def drive(request, pk=None):
    """Le contenu d'un dossier : ses sous-dossiers, puis ses fichiers."""
    from .models import Dossier, Fichier

    exploitation = Exploitation.objects.filter(owner=request.user).first()
    dossier = _drive_dossier(request, pk)
    if pk and dossier is None:
        messages.info(request, _("Ce dossier n'existe plus."))
        return redirect("contrat:drive")

    dossiers = Dossier.objects.filter(exploitation=exploitation, parent=dossier)
    fichiers = Fichier.objects.filter(exploitation=exploitation, dossier=dossier)

    # La liste des destinations possibles pour un déplacement, à plat : sur
    # quelques dizaines de dossiers, un arbre déroulant coûterait plus qu'il
    # ne rapporte.
    destinations = [{"pk": d.pk, "chemin": " / ".join(p.nom for p in d.chemin)}
                    for d in Dossier.objects.filter(exploitation=exploitation)
                    .select_related("parent")]
    destinations.sort(key=lambda d: d["chemin"])

    return render(request, "contrat/drive.html", {
        "dossier": dossier,
        "chemin": dossier.chemin if dossier else [],
        "dossiers": dossiers,
        "fichiers": fichiers,
        "destinations": destinations,
        "vide": not dossiers.exists() and not fichiers.exists(),
        "page_title": dossier.nom if dossier else _("Drive"),
    })


@login_required
@require_POST
def drive_dossier_creer(request, pk=None):
    from django.db import IntegrityError, transaction

    from .models import Dossier

    exploitation = Exploitation.objects.filter(owner=request.user).first()
    parent = _drive_dossier(request, pk)
    nom = (request.POST.get("nom") or "").strip()[:255]
    if not exploitation or not nom:
        return _drive_retour(parent)
    if parent and parent.profondeur >= Dossier.PROFONDEUR_MAX:
        messages.error(request, _("Trop de dossiers imbriqués : rangez plus à plat."))
        return _drive_retour(parent)
    try:
        with transaction.atomic():
            Dossier.objects.create(exploitation=exploitation, parent=parent, nom=nom)
    except IntegrityError:
        messages.error(request, _("Un dossier porte déjà ce nom ici."))
    return _drive_retour(parent)


@login_required
@require_POST
def drive_dossier_renommer(request, pk):
    from django.db import IntegrityError, transaction

    dossier = _drive_dossier(request, pk)
    if dossier is None:
        return redirect("contrat:drive")
    nom = (request.POST.get("nom") or "").strip()[:255]
    if nom:
        dossier.nom = nom
        try:
            with transaction.atomic():
                dossier.save(update_fields=["nom", "updated_at"])
        except IntegrityError:
            messages.error(request, _("Un dossier porte déjà ce nom ici."))
    return _drive_retour(dossier.parent)


@login_required
@require_POST
def drive_dossier_supprimer(request, pk):
    dossier = _drive_dossier(request, pk)
    if dossier is None:
        return redirect("contrat:drive")
    parent = dossier.parent
    dossier.delete()  # emporte ses sous-dossiers et leurs fichiers
    messages.success(request, _("Dossier supprimé."))
    return _drive_retour(parent)


@login_required
@require_POST
def drive_deposer(request, pk=None):
    """Dépose les fichiers choisis dans le dossier courant."""
    import os

    from .models import Fichier

    exploitation = Exploitation.objects.filter(owner=request.user).first()
    dossier = _drive_dossier(request, pk)
    if exploitation is None:
        return _drive_retour(dossier)

    deposes = 0
    for envoye in request.FILES.getlist("fichiers"):
        if _drive_refuse(request, envoye):
            continue
        Fichier.objects.create(
            exploitation=exploitation, dossier=dossier,
            nom=os.path.basename(envoye.name)[:255], fichier=envoye,
            taille=envoye.size, depose_par=request.user)
        deposes += 1
    if deposes:
        messages.success(request, _("%(n)s document(s) importé(s).") % {"n": deposes})
    return _drive_retour(dossier)


def _drive_fichier(request, pk):
    from .models import Fichier

    exploitation = Exploitation.objects.filter(owner=request.user).first()
    return Fichier.objects.filter(pk=pk, exploitation=exploitation).first()


@login_required
@require_POST
def drive_fichier_renommer(request, pk):
    fichier = _drive_fichier(request, pk)
    if fichier is None:
        return redirect("contrat:drive")
    nom = (request.POST.get("nom") or "").strip()[:255]
    if nom:
        fichier.nom = nom
        fichier.save(update_fields=["nom"])
    return _drive_retour(fichier.dossier)


@login_required
@require_POST
def drive_fichier_supprimer(request, pk):
    fichier = _drive_fichier(request, pk)
    if fichier is None:
        return redirect("contrat:drive")
    dossier = fichier.dossier
    fichier.delete()
    messages.success(request, _("Document supprimé."))
    return _drive_retour(dossier)


@login_required
@require_POST
def drive_deplacer(request, pk):
    """Déplace un dossier ou un fichier vers un autre dossier.

    Un dossier ne peut pas descendre dans sa propre branche : la boucle
    rendrait tout ce qu'elle contient inatteignable.
    """
    from django.db import IntegrityError, transaction

    quoi = request.POST.get("quoi")
    vers = _drive_dossier(request, request.POST.get("vers") or None)

    if quoi == "dossier":
        dossier = _drive_dossier(request, pk)
        if dossier is None:
            return redirect("contrat:drive")
        depart = dossier.parent
        if vers is not None and dossier.contient(vers):
            messages.error(request, _("Un dossier ne peut pas être déplacé dans lui-même."))
            return _drive_retour(depart)
        dossier.parent = vers
        try:
            with transaction.atomic():
                dossier.save(update_fields=["parent", "updated_at"])
        except IntegrityError:
            messages.error(request, _("Un dossier porte déjà ce nom là-bas."))
            return _drive_retour(depart)
        return _drive_retour(depart)

    fichier = _drive_fichier(request, pk)
    if fichier is None:
        return redirect("contrat:drive")
    depart = fichier.dossier
    fichier.dossier = vers
    fichier.save(update_fields=["dossier"])
    return _drive_retour(depart)
