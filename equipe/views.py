"""Vues web équipe : équipe, tâches, mes-tâches (technicien), partage géoloc public."""

from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core.mail import BadHeaderError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from core import espaces as espaces_service
from core.decorators import espace_requis
from core.espaces import EMPLOYE, EXPLOITANT
from exploitations.models import Exploitation
from parcelles.models import Parcelle

from . import invitations
from .forms import InvitationAccountForm, TaskForm, TeamMemberForm
from . import contrats as contrats_service
from .models import (Candidature, ContratTravail, ModeleContrat, OffreEmploi,
                     Task, TeamMember)

User = get_user_model()


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
@espace_requis(EXPLOITANT)
def equipe(request):
    exploitation = _exploitation(request)
    form = TeamMemberForm()
    if request.method == "POST":
        if exploitation is None:
            messages.error(request, _("Créez d'abord votre exploitation avant d'ajouter un membre."))
        else:
            form = TeamMemberForm(request.POST)
            if form.is_valid():
                member = form.save(exploitation=exploitation, managed_by=request.user)
                messages.success(request, _("%(name)s a été ajouté à l'équipe.") % {"name": member.name})
                return redirect("equipe:equipe")
    members = TeamMember.objects.filter(exploitation=exploitation) if exploitation else TeamMember.objects.none()
    return render(request, "equipe/equipe.html", {
        "members": members, "form": form, "roles": TeamMember.Role.choices, "page_title": _("Équipe"),
    })


@login_required
def membre_edit(request, pk):
    exploitation = _exploitation(request)
    member = get_object_or_404(TeamMember, pk=pk, exploitation=exploitation)
    if request.method == "POST":
        form = TeamMemberForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            messages.success(request, _("%(name)s a été mis à jour.") % {"name": member.name})
            return redirect("equipe:equipe")
    else:
        form = TeamMemberForm(instance=member)
    return render(request, "equipe/edit.html", {"form": form, "member": member, "page_title": _("Modifier le membre")})


@login_required
@require_POST
def membre_inviter(request, pk):
    """Envoie au membre le lien qui lui ouvrira son espace employé."""
    exploitation = _exploitation(request)
    member = get_object_or_404(TeamMember, pk=pk, exploitation=exploitation)
    if member.user_id is not None:
        messages.info(request, _("%(name)s a déjà un compte lié.") % {"name": member.name})
    elif not member.email:
        messages.error(request, _("Renseignez un email avant d'inviter %(name)s.") % {"name": member.name})
    else:
        try:
            invitations.envoyer(member, request)
        except (BadHeaderError, OSError):
            # SMTP indisponible ou refusé : le dire, ne pas laisser croire à un envoi.
            messages.error(request, _("L'invitation n'a pas pu être envoyée à %(email)s. "
                                      "Réessayez dans un instant.") % {"email": member.email})
        else:
            messages.success(request, _("Invitation envoyée à %(email)s.") % {"email": member.email})
    return redirect("equipe:membre_edit", pk=member.pk)


def invitation(request, token):
    """Acceptation d'une invitation — publique, le jeton fait l'authentification.

    Quatre situations, une seule page : lien mort, compte à créer, compte
    existant à connecter, ou compte déjà connecté à confirmer.
    """
    member = invitations.membre_du_jeton(token)
    if member is None:
        return render(request, "equipe/invitation.html",
                      {"etat": "invalide", "page_title": _("Invitation")}, status=410)

    if member.user_id is not None:
        if request.user.is_authenticated and request.user.pk == member.user_id:
            return redirect("core:dashboard")
        return render(request, "equipe/invitation.html",
                      {"etat": "deja_utilisee", "membre": member, "page_title": _("Invitation")},
                      status=410)

    if request.user.is_authenticated:
        etat = "confirmer"
        form = None
    elif User.objects.filter(email__iexact=member.email).exists():
        etat = "connexion"
        form = None
    else:
        etat = "creation"
        form = InvitationAccountForm(email=member.email)

    if request.method == "POST" and etat in ("confirmer", "creation"):
        user = request.user
        if etat == "creation":
            form = InvitationAccountForm(request.POST, email=member.email)
            if not form.is_valid():
                return _rendre_invitation(request, etat, member, form)
            user = form.save()
            login(request, user)
        invitations.accepter(member, user)
        # Le rattachement vient de naître : le contexte d'espaces posé par le
        # middleware en début de requête l'ignore encore.
        espaces_service.invalider(request)
        # L'invitation porte sur l'espace employé : l'ouvrir tout de suite,
        # sans quoi un exploitant invité resterait sur son espace habituel.
        espaces_service.definir_espace(request, EMPLOYE)
        messages.success(request, _("Bienvenue dans l'équipe de %(expl)s.")
                         % {"expl": member.exploitation.name})
        return redirect("core:dashboard")

    return _rendre_invitation(request, etat, member, form)


def _rendre_invitation(request, etat, member, form):
    return render(request, "equipe/invitation.html", {
        "etat": etat, "membre": member, "form": form,
        "url_connexion": f"{reverse('accounts:login')}?next={request.path}",
        "page_title": _("Invitation"),
    })


@login_required
@require_POST
def membre_delete(request, pk):
    """Supprime un membre d'équipe."""
    exploitation = _exploitation(request)
    get_object_or_404(TeamMember, pk=pk, exploitation=exploitation).delete()
    messages.success(request, _("Membre supprimé."))
    return redirect("equipe:equipe")


@login_required
def taches(request):
    exploitation = _exploitation(request)
    form = TaskForm(exploitation=exploitation)
    if request.method == "POST":
        if exploitation is None:
            messages.error(request, _("Créez d'abord votre exploitation avant d'ajouter une tâche."))
        else:
            form = TaskForm(request.POST, exploitation=exploitation)
            if form.is_valid():
                task = form.save(commit=False)
                task.exploitation = exploitation
                task.created_by = request.user
                task.save()
                messages.success(request, _("Tâche « %(t)s » ajoutée.") % {"t": task.title})
                return redirect("equipe:taches")
    # « Mes tâches » : membre lié à mon compte (par user, ou à défaut par email).
    my_member = None
    if exploitation:
        q = Q(user=request.user)
        if request.user.email:
            q |= Q(email__iexact=request.user.email)
        my_member = TeamMember.objects.filter(exploitation=exploitation).filter(q).first()
    tasks = list(
        Task.objects.filter(exploitation=exploitation).select_related("assigned_to", "parent")
        if exploitation else Task.objects.none()
    )
    for t in tasks:
        t.is_mine = my_member is not None and t.assigned_to_id == my_member.id
    has_mine = any(t.is_mine for t in tasks)
    return render(request, "equipe/taches.html", {
        "tasks": tasks, "form": form, "has_mine": has_mine,
        "priorities": Task.Priority.choices, "statuses": Task.Status.choices,
        "page_title": _("Tâches"),
    })


@login_required
def taches_edit(request, pk):
    """Modifie une tâche (soumis depuis la modale de /taches/)."""
    exploitation = _exploitation(request)
    task = get_object_or_404(Task, pk=pk, exploitation=exploitation)
    if request.method == "POST":
        form = TaskForm(request.POST, instance=task, exploitation=exploitation)
        if form.is_valid():
            form.save()
            messages.success(request, _("Tâche « %(t)s » modifiée.") % {"t": task.title})
        else:
            messages.error(request, _("Modification impossible : vérifiez les champs."))
    return redirect("equipe:taches")


@login_required
@require_POST
def taches_delete(request, pk):
    """Supprime une tâche."""
    exploitation = _exploitation(request)
    get_object_or_404(Task, pk=pk, exploitation=exploitation).delete()
    messages.success(request, _("Tâche supprimée."))
    return redirect("equipe:taches")


def location_share(request, token):
    """Page publique de partage de position (lien 24h)."""
    member = TeamMember.objects.filter(
        location_token=token, location_token_expires_at__gt=timezone.now()
    ).first()
    return render(request, "equipe/location_share.html", {"member": member, "token": token})


def _rh_placeholder(request, title):
    """Page « en préparation » pour une sous-section RH."""
    return render(request, "equipe/placeholder.html", {"title": title, "page_title": title})


def _to_float(valeur, defaut=None):
    try:
        return float(str(valeur).replace(",", ".").replace(" ", "").strip())
    except (TypeError, ValueError):
        return defaut


def _to_date(valeur):
    from django.utils.dateparse import parse_date

    return parse_date((valeur or "").strip()) or None


@login_required
@espace_requis(EXPLOITANT)
def contrats(request):
    """Modèles de contrat et contrats établis."""
    exploitation = _exploitation(request)
    return render(request, "equipe/contrats.html", {
        "modeles": ModeleContrat.objects.filter(exploitation=exploitation) if exploitation else [],
        "contrats": (ContratTravail.objects.filter(exploitation=exploitation)
                     .select_related("membre", "modele") if exploitation else []),
        "membres": TeamMember.objects.filter(exploitation=exploitation) if exploitation else [],
        "types": ModeleContrat.Type.choices,
        "statuts": ContratTravail.Statut.choices,
        "jetons": contrats_service.JETONS,
        "squelettes": contrats_service.SQUELETTES,
        "page_title": _("Contrats de travail"),
    })


@login_required
@espace_requis(EXPLOITANT)
@require_POST
def modeles_importer(request):
    """Copie les squelettes fournis dans les modèles de l'exploitation.

    Ce sont des points de départ : une fois copiés, ils appartiennent à la
    ferme et s'adaptent sans que la mise à jour de l'application les écrase.
    """
    exploitation = _exploitation(request)
    if exploitation is None:
        messages.error(request, _("Créez d'abord votre exploitation."))
        return redirect("equipe:contrats")

    ajoutes = 0
    for squelette in contrats_service.SQUELETTES:
        _modele, cree = ModeleContrat.objects.get_or_create(
            exploitation=exploitation, nom=str(squelette["nom"]),
            defaults={"type_contrat": squelette["type_contrat"],
                      "corps": str(squelette["corps"])})
        ajoutes += 1 if cree else 0
    messages.success(request, _("%(n)s modèle(s) ajouté(s).") % {"n": ajoutes})
    return redirect("equipe:contrats")


@login_required
@espace_requis(EXPLOITANT)
@require_POST
def modele_save(request, pk=None):
    exploitation = _exploitation(request)
    if exploitation is None:
        messages.error(request, _("Créez d'abord votre exploitation."))
        return redirect("equipe:contrats")

    modele = (get_object_or_404(ModeleContrat, pk=pk, exploitation=exploitation)
              if pk else ModeleContrat(exploitation=exploitation))
    nom = (request.POST.get("nom") or "").strip()
    corps = (request.POST.get("corps") or "").strip()
    if not (nom and corps):
        messages.error(request, _("Un modèle a besoin d'un nom et d'un corps."))
        return redirect("equipe:contrats")

    type_contrat = request.POST.get("type_contrat") or ModeleContrat.Type.CDI
    modele.nom = nom[:255]
    modele.corps = corps
    modele.type_contrat = (type_contrat if type_contrat in ModeleContrat.Type.values
                           else ModeleContrat.Type.CDI)
    modele.notes = (request.POST.get("notes") or "").strip()
    modele.save()
    return redirect("equipe:contrats")


@login_required
@espace_requis(EXPLOITANT)
@require_POST
def modele_delete(request, pk):
    exploitation = _exploitation(request)
    get_object_or_404(ModeleContrat, pk=pk, exploitation=exploitation).delete()
    return redirect("equipe:contrats")


def _champs_contrat(request):
    return {
        "poste": (request.POST.get("poste") or "").strip()[:255],
        "lieu": (request.POST.get("lieu") or "").strip()[:255],
        "date_debut": _to_date(request.POST.get("date_debut")),
        "date_fin": _to_date(request.POST.get("date_fin")),
        "duree_hebdo": _to_float(request.POST.get("duree_hebdo")),
        "remuneration": _to_float(request.POST.get("remuneration")),
    }


@login_required
@espace_requis(EXPLOITANT)
@require_POST
def contrat_create(request):
    """Établit le contrat d'un salarié à partir d'un modèle.

    Le corps est rendu maintenant et figé : retoucher le modèle ensuite ne
    réécrit pas un contrat déjà remis.
    """
    exploitation = _exploitation(request)
    membre = TeamMember.objects.filter(
        pk=request.POST.get("membre") or 0, exploitation=exploitation).first()
    modele = ModeleContrat.objects.filter(
        pk=request.POST.get("modele") or 0, exploitation=exploitation).first()
    if not (exploitation and membre and modele):
        messages.error(request, _("Choisissez un salarié et un modèle."))
        return redirect("equipe:contrats")

    contrat = ContratTravail(exploitation=exploitation, membre=membre, modele=modele,
                             type_contrat=modele.type_contrat, **_champs_contrat(request))
    contrat.corps = contrats_service.remplir(
        modele.corps, contrats_service.valeurs_pour(contrat))
    contrat.save()
    messages.success(request, _("Contrat établi. Relisez-le avant de le remettre."))
    return redirect("equipe:contrats")


@login_required
@espace_requis(EXPLOITANT)
@require_POST
def contrat_edit(request, pk):
    exploitation = _exploitation(request)
    contrat = get_object_or_404(ContratTravail, pk=pk, exploitation=exploitation)
    for champ, valeur in _champs_contrat(request).items():
        setattr(contrat, champ, valeur)

    statut = request.POST.get("statut") or contrat.statut
    if statut in ContratTravail.Statut.values:
        contrat.statut = statut
    contrat.date_signature = _to_date(request.POST.get("date_signature"))
    if request.POST.get("corps") is not None:
        contrat.corps = request.POST.get("corps")
    contrat.save()
    return redirect("equipe:contrats")


@login_required
@espace_requis(EXPLOITANT)
@require_POST
def contrat_delete(request, pk):
    exploitation = _exploitation(request)
    get_object_or_404(ContratTravail, pk=pk, exploitation=exploitation).delete()
    return redirect("equipe:contrats")


@login_required
@espace_requis(EXPLOITANT)
def contrat_pdf(request, pk):
    """Le contrat en PDF, ou en page imprimable si WeasyPrint n'est pas là."""
    exploitation = _exploitation(request)
    contrat = get_object_or_404(
        ContratTravail.objects.select_related("membre"), pk=pk, exploitation=exploitation)
    html = render(request, "equipe/contrat_pdf.html", {
        "contrat": contrat, "exploitation": exploitation}).content.decode()

    try:
        from weasyprint import HTML
    except Exception:  # noqa: BLE001 — libs système absentes : on rend la page
        return render(request, "equipe/contrat_pdf.html",
                      {"contrat": contrat, "exploitation": exploitation})

    from django.http import HttpResponse

    pdf = HTML(string=html, base_url=request.build_absolute_uri("/")).write_pdf()
    reponse = HttpResponse(pdf, content_type="application/pdf")
    nom = f"contrat-{contrat.membre.name}-{contrat.pk}.pdf".replace(" ", "-").lower()
    reponse["Content-Disposition"] = f'inline; filename="{nom}"'
    return reponse


@login_required
@espace_requis(EXPLOITANT)
def paie(request):
    """Paie — module RH en préparation."""
    return _rh_placeholder(request, _("Paie"))


# ── Offres d'emploi : back-office ────────────────────────────────────


def _champs_offre(request):
    type_contrat = request.POST.get("type_contrat") or ModeleContrat.Type.SAISONNIER
    return {
        "titre": (request.POST.get("titre") or "").strip()[:255],
        "type_contrat": (type_contrat if type_contrat in ModeleContrat.Type.values
                         else ModeleContrat.Type.SAISONNIER),
        "description": (request.POST.get("description") or "").strip(),
        "profil": (request.POST.get("profil") or "").strip(),
        "lieu": (request.POST.get("lieu") or "").strip()[:255],
        "date_debut": _to_date(request.POST.get("date_debut")),
        "duree_hebdo": _to_float(request.POST.get("duree_hebdo")),
        "remuneration": (request.POST.get("remuneration") or "").strip()[:255],
        "logement": request.POST.get("logement") == "on",
        "contact_email": (request.POST.get("contact_email") or "").strip(),
        "expire_le": _to_date(request.POST.get("expire_le")),
    }


def _communes(exploitation):
    """Les communes où l'exploitation a des parcelles, sans doublon."""
    if exploitation is None:
        return []
    return sorted({
        c.strip() for c in Parcelle.objects
        .filter(exploitation=exploitation)
        .exclude(commune="")
        .values_list("commune", flat=True) if c.strip()
    })


@login_required
@espace_requis(EXPLOITANT)
def offres(request):
    """Les offres de l'exploitation et les candidatures reçues."""
    exploitation = _exploitation(request)
    lot = (OffreEmploi.objects.filter(exploitation=exploitation)
           .prefetch_related("candidatures") if exploitation else [])
    return render(request, "equipe/offres.html", {
        "offres": lot,
        # Le lieu de travail se choisit parmi les communes des parcelles : une
        # offre situe le poste là où la ferme travaille, pas ailleurs.
        "communes": _communes(exploitation),
        "types": ModeleContrat.Type.choices,
        "statuts": OffreEmploi.Statut.choices,
        "statuts_candidature": Candidature.Statut.choices,
        "page_title": _("Offres d'emploi"),
    })


@login_required
@espace_requis(EXPLOITANT)
@require_POST
def offre_save(request, pk=None):
    exploitation = _exploitation(request)
    if exploitation is None:
        messages.error(request, _("Créez d'abord votre exploitation."))
        return redirect("equipe:offres")

    offre = (get_object_or_404(OffreEmploi, pk=pk, exploitation=exploitation)
             if pk else OffreEmploi(exploitation=exploitation))
    champs = _champs_offre(request)
    if not (champs["titre"] and champs["description"]):
        messages.error(request, _("Une offre a besoin d'un intitulé et d'une description."))
        return redirect("equipe:offres")

    for champ, valeur in champs.items():
        setattr(offre, champ, valeur)
    offre.save()
    return redirect("equipe:offres")


@login_required
@espace_requis(EXPLOITANT)
@require_POST
def offre_statut(request, pk):
    """Publie, dépublie, ou clôt une offre."""
    exploitation = _exploitation(request)
    offre = get_object_or_404(OffreEmploi, pk=pk, exploitation=exploitation)
    statut = request.POST.get("statut")
    if statut in OffreEmploi.Statut.values:
        offre.statut = statut
        # La date de publication se pose à la première mise en ligne et ne
        # bouge plus : elle ordonne la liste publique.
        if statut == OffreEmploi.Statut.PUBLIEE and offre.publiee_le is None:
            offre.publiee_le = timezone.now()
        offre.save(update_fields=["statut", "publiee_le", "updated_at"])
    return redirect("equipe:offres")


@login_required
@espace_requis(EXPLOITANT)
@require_POST
def offre_delete(request, pk):
    exploitation = _exploitation(request)
    get_object_or_404(OffreEmploi, pk=pk, exploitation=exploitation).delete()
    return redirect("equipe:offres")


@login_required
@espace_requis(EXPLOITANT)
@require_POST
def candidature_statut(request, pk):
    exploitation = _exploitation(request)
    candidature = get_object_or_404(
        Candidature, pk=pk, offre__exploitation=exploitation)
    statut = request.POST.get("statut")
    if statut in Candidature.Statut.values:
        candidature.statut = statut
        candidature.save(update_fields=["statut", "updated_at"])
    return redirect("equipe:offres")
