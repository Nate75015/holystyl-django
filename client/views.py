"""Vues web Clients : fiches clients et KPIs (tenant-scoped)."""

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation

from core.adresse import TYPES_VOIE

from .models import Client, Partenaire


def _to_float(value, default=None):
    try:
        return float(str(value).replace(",", ".").replace("€", "").replace(" ", "").strip())
    except (TypeError, ValueError):
        return default


def _to_int(value, default=None):
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


def _client_fields(request):
    """Champs de la fiche client lus depuis le POST (création et édition).

    Les champs propres à une catégorie sont vidés côté serveur quand ils ne la
    concernent pas, le formulaire les masquant déjà : prénom pour un
    professionnel ; sous-catégorie, SIRET, TVA, délai de paiement et CA annuel
    pour un particulier.
    """
    categorie = request.POST.get("categorie") or Client.Categorie.PROFESSIONNEL
    if categorie not in Client.Categorie.values:
        categorie = Client.Categorie.PROFESSIONNEL
    particulier = categorie == Client.Categorie.PARTICULIER

    return {
        "categorie": categorie,
        "prenom": (request.POST.get("prenom") or "").strip() if particulier else "",
        "type_client": "" if particulier else (request.POST.get("type_client") or Client.TypeClient.AUTRE),
        "siret": "" if particulier else (request.POST.get("siret") or "").strip(),
        "tva_intracom": "" if particulier else (request.POST.get("tva_intracom") or "").strip(),
        # Adresse d'annuaire : elle sert à router les factures électroniques,
        # donc sans objet pour un particulier (hors périmètre de la réforme).
        "superpdp_adresse": "" if particulier else (request.POST.get("superpdp_adresse") or "").strip(),
        "statut": request.POST.get("statut") or Client.Statut.PROSPECT,
        "contact_principal": (request.POST.get("contact_principal") or "").strip(),
        "email": (request.POST.get("email") or "").strip(),
        "telephone": (request.POST.get("telephone") or "").strip(),
        "site_web": (request.POST.get("site_web") or "").strip(),
        "numero_voie": (request.POST.get("numero_voie") or "").strip(),
        "type_voie": (request.POST.get("type_voie") or "").strip(),
        "voie": (request.POST.get("voie") or "").strip(),
        "code_postal": (request.POST.get("code_postal") or "").strip(),
        "ville": (request.POST.get("ville") or "").strip(),
        "pays": (request.POST.get("pays") or "").strip(),
        "delai_paiement_jours": None if particulier else _to_int(request.POST.get("delai_paiement_jours")),
        "ca_annuel": None if particulier else _to_float(request.POST.get("ca_annuel")),
        "notes": (request.POST.get("notes") or "").strip(),
    }


# ── Clients ─────────────────────────────────────────────────────────

@login_required
def clients(request):
    exploitation = _exploitation(request)
    base = Client.objects.filter(exploitation=exploitation) if exploitation else Client.objects.none()

    ca = base.aggregate(s=Sum("ca_annuel"))["s"] or 0

    return render(request, "client/clients.html", {
        "clients": base,
        "kpi_count": base.count(),
        "kpi_actifs": base.filter(statut=Client.Statut.ACTIF).count(),
        "kpi_prospects": base.filter(statut=Client.Statut.PROSPECT).count(),
        "kpi_ca": round(ca),
        "types": Client.TypeClient.choices,
        "categories": Client.Categorie.choices,
        "types_voie": TYPES_VOIE,
        "statuts": Client.Statut.choices,
        "page_title": _("Clients"),
    })


@login_required
@require_POST
def client_create(request):
    exploitation = _exploitation(request)
    nom = (request.POST.get("nom") or "").strip()
    if exploitation and nom:
        client = Client.objects.create(exploitation=exploitation, nom=nom, **_client_fields(request))
        return redirect("client:detail", pk=client.pk)
    return redirect("client:clients")


@login_required
def client_detail(request, pk):
    exploitation = _exploitation(request)
    client = get_object_or_404(Client, pk=pk, exploitation=exploitation)

    return render(request, "client/detail.html", {
        "client": client,
        # ?modifier=1 → la fiche s'ouvre directement sur le formulaire.
        "ouvrir_modification": request.GET.get("modifier") == "1",
        "types": Client.TypeClient.choices,
        "categories": Client.Categorie.choices,
        "types_voie": TYPES_VOIE,
        "statuts": Client.Statut.choices,
        "page_title": client.nom_complet,
    })


@login_required
def client_edit(request, pk):
    """Modification d'un client.

    En POST, c'est la cible du formulaire de la fiche. En GET, l'URL est un
    raccourci : on renvoie sur la fiche avec le formulaire déjà ouvert, plutôt
    que de répondre « méthode non autorisée » à quelqu'un qui suit un lien.
    """
    exploitation = _exploitation(request)
    client = get_object_or_404(Client, pk=pk, exploitation=exploitation)

    if request.method != "POST":
        return redirect(f"{reverse('client:detail', args=[client.pk])}?modifier=1")

    nom = (request.POST.get("nom") or "").strip()
    if nom:
        for field, value in {"nom": nom, **_client_fields(request)}.items():
            setattr(client, field, value)
        client.save()
    return redirect("client:detail", pk=client.pk)


@login_required
@require_POST
def client_delete(request, pk):
    exploitation = _exploitation(request)
    get_object_or_404(Client, pk=pk, exploitation=exploitation).delete()
    return redirect("client:clients")



# ── Partenaires : bailleurs, comptables, avocats ─────────────────────────

def _libelles_partenaire(type_partenaire):
    """Titre et libellé au singulier, pour un gabarit partagé entre les types."""
    pluriels = {
        Partenaire.Type.BAILLEUR: (_("Bailleurs"), _("bailleur")),
        Partenaire.Type.COMPTABLE: (_("Comptables"), _("comptable")),
        Partenaire.Type.AVOCAT: (_("Avocats"), _("avocat")),
    }
    return pluriels.get(type_partenaire, (_("Partenaires"), _("partenaire")))


@login_required
def partenaires(request, type_partenaire):
    """Liste des tiers d'un type donné (une page par type, même gabarit)."""
    if type_partenaire not in {t.value for t in Partenaire.Type}:
        raise Http404("Type de relation inconnu")
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    items = (
        Partenaire.objects.filter(exploitation=exploitation, type_partenaire=type_partenaire)
        if exploitation else Partenaire.objects.none()
    )
    titre, singulier = _libelles_partenaire(type_partenaire)
    return render(request, "client/partenaires.html", {
        "partenaires": items,
        "type_partenaire": type_partenaire,
        "titre": titre,
        "singulier": singulier,
        "types_voie": TYPES_VOIE,
        "page_title": titre,
    })


@login_required
@require_POST
def partenaire_create(request):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    type_partenaire = request.POST.get("type_partenaire") or Partenaire.Type.AUTRE
    nom = (request.POST.get("nom") or "").strip()
    valides = {t.value for t in Partenaire.Type}
    if exploitation and nom and type_partenaire in valides:
        Partenaire.objects.create(
            exploitation=exploitation,
            type_partenaire=type_partenaire,
            nom=nom[:255],
            contact_principal=(request.POST.get("contact_principal") or "").strip()[:255],
            email=(request.POST.get("email") or "").strip(),
            telephone=(request.POST.get("telephone") or "").strip()[:30],
            site_web=(request.POST.get("site_web") or "").strip()[:255],
            numero_voie=(request.POST.get("numero_voie") or "").strip()[:10],
            type_voie=request.POST.get("type_voie") or "",
            voie=(request.POST.get("voie") or "").strip()[:255],
            code_postal=(request.POST.get("code_postal") or "").strip()[:10],
            ville=(request.POST.get("ville") or "").strip()[:100],
            siret=(request.POST.get("siret") or "").strip()[:20],
            notes=(request.POST.get("notes") or "").strip(),
        )
    return redirect("client:partenaires", type_partenaire=type_partenaire)


@login_required
@require_POST
def partenaire_delete(request, pk):
    exploitation = Exploitation.objects.filter(owner=request.user).first()
    partenaire = get_object_or_404(Partenaire, pk=pk, exploitation=exploitation)
    type_partenaire = partenaire.type_partenaire
    partenaire.delete()
    return redirect("client:partenaires", type_partenaire=type_partenaire)
