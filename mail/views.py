"""Vues Mail : connexion Gmail (OAuth), boîte de réception et envoi via Gmail."""

import logging
import re

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from equipe.models import TeamMember
from exploitations.models import Exploitation

from . import gmail as gmail_api
from .models import GmailAccount

logger = logging.getLogger(__name__)


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


def _parse_addresses(raw):
    """Découpe une saisie libre (virgules, points-virgules, retours) en adresses."""
    parts = [p.strip() for p in re.split(r"[,;\n]+", raw or "") if p.strip()]
    valid, invalid = [], []
    for p in parts:
        try:
            validate_email(p)
            valid.append(p)
        except ValidationError:
            invalid.append(p)
    return valid, invalid


def _gmail_account(request):
    return GmailAccount.objects.filter(user=request.user).first()


def _unread_counts(account):
    """Compteurs de messages non lus par libellé (badges rail + onglets)."""
    if not account:
        return {}
    try:
        return gmail_api.GmailClient(account).unread_counts()
    except Exception:  # noqa: BLE001 — badges non bloquants
        return {}


# Onglets de catégories affichés sur la Boîte de réception (façon Gmail).
INBOX_TABS = [
    ("principale", "Principale", "inbox", "CATEGORY_PERSONAL"),
    ("promotions", "Promotions", "local_offer", "CATEGORY_PROMOTIONS"),
    ("social", "Réseaux sociaux", "group", "CATEGORY_SOCIAL"),
    ("notifications", "Notifications", "info", "CATEGORY_UPDATES"),
]


def _rail_context(account, active=None, counts=None):
    """Dossiers du rail (façon Gmail) + compteurs non-lus."""
    if counts is None:
        counts = _unread_counts(account)

    def build(section):
        return [
            {"key": k, "label": lab, "icon": ic, "count": counts.get(k, 0)}
            for (k, lab, ic, sec) in gmail_api.FOLDERS if sec == section
        ]

    return {
        "rail_main": build("main"), "rail_more": build("more"),
        "account": account, "active_folder": active,
        "gmail_configured": gmail_api.is_configured(),
    }


@login_required
def outbox(request):
    """Point d'entrée /mail/ : Gmail si connecté, sinon écran de connexion.

    Tant qu'aucune boîte n'est importée, l'utilisateur ne peut que connecter
    sa boîte : l'envoi n'est disponible qu'une fois la boîte importée.
    """
    account = _gmail_account(request)
    if account:
        return redirect("mail:folder", folder="INBOX")
    ctx = {"configured": gmail_api.is_configured(), "page_title": _("Mail")}
    ctx.update(_rail_context(None))
    return render(request, "mail/connect.html", ctx)


# ══════════════════════════════════════════════════════════════════
#  Gmail API — connexion OAuth + boîte de réception réelle
# ══════════════════════════════════════════════════════════════════

@login_required
def gmail_connect(request):
    """Démarre le flow OAuth Google (redirige vers l'écran de consentement)."""
    if not gmail_api.is_configured():
        messages.error(request, _("La connexion Gmail n'est pas configurée sur ce serveur."))
        return redirect("mail:outbox")
    flow = gmail_api.build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent",
    )
    request.session["gmail_oauth_state"] = state
    # PKCE : on conserve le code_verifier généré ici pour le rejouer au callback.
    request.session["gmail_code_verifier"] = flow.code_verifier
    return redirect(auth_url)


@login_required
def gmail_callback(request):
    """Callback OAuth : échange le code, récupère l'adresse, stocke les jetons."""
    if request.GET.get("error"):
        messages.error(request, _("Connexion Gmail annulée."))
        return redirect("mail:outbox")

    state = request.session.get("gmail_oauth_state")
    flow = gmail_api.build_flow(state=state)
    # PKCE : rejoue le code_verifier stocké lors de la connexion.
    flow.code_verifier = request.session.get("gmail_code_verifier")
    try:
        flow.fetch_token(code=request.GET.get("code"))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Échec fetch_token OAuth Gmail")
        messages.error(request, _("Échec de la connexion Gmail : %(e)s") % {"e": exc})
        return redirect("mail:outbox")

    creds = flow.credentials
    # Adresse du compte connecté via l'endpoint userinfo.
    try:
        from googleapiclient.discovery import build

        info = build("oauth2", "v2", credentials=creds, cache_discovery=False)
        email = info.userinfo().get().execute().get("email", "")
    except Exception:  # noqa: BLE001
        email = ""

    GmailAccount.objects.update_or_create(
        user=request.user,
        defaults={"email": email, "credentials": gmail_api.encrypt_token(gmail_api.creds_to_dict(creds))},
    )
    messages.success(request, _("Boîte mail %(e)s connectée.") % {"e": email})
    return redirect("mail:folder", folder="INBOX")


@login_required
def gmail_disconnect(request):
    if request.method == "POST":
        GmailAccount.objects.filter(user=request.user).delete()
        messages.success(request, _("Boîte mail déconnectée."))
    return redirect("mail:outbox")


def _folder_label(folder):
    for key, label, *_ in gmail_api.FOLDERS:
        if key == folder:
            return label
    raise Http404


@login_required
def folder(request, folder):
    """Liste les messages d'un dossier/libellé Gmail."""
    account = _gmail_account(request)
    if not account:
        return redirect("mail:outbox")
    label = _folder_label(folder)
    client = gmail_api.GmailClient(account)
    counts = _unread_counts(account)

    # Onglets de catégories, uniquement sur la Boîte de réception.
    tabs, active_tab, extra_labels = [], None, None
    if folder == "INBOX":
        active_tab = request.GET.get("tab", "principale")
        tab_cat = {t[0]: t[3] for t in INBOX_TABS}
        extra_labels = [tab_cat.get(active_tab, "CATEGORY_PERSONAL")]
        tabs = [
            {"key": k, "label": lab, "icon": ic, "count": counts.get(cat, 0)}
            for (k, lab, ic, cat) in INBOX_TABS
        ]

    error = None
    messages_list, next_token = [], None
    try:
        messages_list, next_token = client.list_messages(
            folder, page_token=request.GET.get("page") or None, extra_labels=extra_labels,
        )
    except Exception as exc:  # noqa: BLE001
        error = str(exc)

    ctx = {
        "folder": folder, "folder_label": label,
        "messages_list": messages_list, "next_token": next_token,
        "tabs": tabs, "active_tab": active_tab,
        "error": error, "page_title": label,
    }
    ctx.update(_rail_context(account, active=folder, counts=counts))
    return render(request, "mail/gmail_list.html", ctx)


@login_required
def gmail_message(request, mid):
    """Lecture d'un message Gmail (le marque comme lu)."""
    account = _gmail_account(request)
    if not account:
        return redirect("mail:outbox")
    client = gmail_api.GmailClient(account)
    try:
        msg = client.get_message(mid)
        client.mark_read(mid)
    except Exception as exc:  # noqa: BLE001
        messages.error(request, _("Message introuvable : %(e)s") % {"e": exc})
        return redirect("mail:folder", folder="INBOX")

    ctx = {
        "msg": msg, "back_folder": request.GET.get("from", "INBOX"),
        "page_title": msg["subject"],
    }
    ctx.update(_rail_context(account, active=request.GET.get("from", "INBOX")))
    return render(request, "mail/gmail_message.html", ctx)


@login_required
def compose(request):
    """Composition + envoi via le compte Gmail connecté.

    L'envoi n'est accessible qu'une fois la boîte importée : sans compte
    connecté, on renvoie vers l'écran de connexion.
    """
    account = _gmail_account(request)
    if not account:
        messages.info(request, _("Importez d'abord votre boîte mail pour envoyer un message."))
        return redirect("mail:outbox")

    # Carnet d'adresses : e-mails des membres d'équipe de l'exploitation
    exploitation = _exploitation(request)
    contacts = []
    if exploitation:
        contacts = list(
            TeamMember.objects.filter(exploitation=exploitation)
            .exclude(email="")
            .values_list("name", "email")
        )

    if request.method == "POST":
        to_raw = request.POST.get("to", "")
        cc_raw = request.POST.get("cc", "")
        subject = (request.POST.get("subject") or "").strip()
        body = request.POST.get("body") or ""
        files = request.FILES.getlist("fichiers")

        to_list, to_invalid = _parse_addresses(to_raw)
        cc_list, cc_invalid = _parse_addresses(cc_raw)
        invalid = to_invalid + cc_invalid

        errors = []
        if not to_list:
            errors.append(_("Indiquez au moins un destinataire valide."))
        if invalid:
            errors.append(_("Adresses invalides ignorées : %(list)s") % {"list": ", ".join(invalid)})
        if not subject:
            errors.append(_("L'objet est obligatoire."))

        if not errors:
            attachments = [(f.name, f.read(), f.content_type) for f in files]
            try:
                gmail_api.GmailClient(account).send_message(
                    to_list, subject, body, cc=cc_list or None, attachments=attachments,
                )
                messages.success(request, _("Message envoyé depuis %(e)s.") % {"e": account.email})
                return redirect("mail:folder", folder="SENT")
            except Exception as exc:  # noqa: BLE001
                errors.append(_("Échec de l'envoi : %(e)s") % {"e": exc})

        return render(request, "mail/compose.html", {
            "errors": errors, "contacts": contacts, "account": account,
            "page_title": _("Nouveau message"),
            "form": {"to": to_raw, "cc": cc_raw, "subject": subject, "body": body},
        })

    prefill = request.GET.get("to", "")
    return render(request, "mail/compose.html", {
        "contacts": contacts, "account": account, "page_title": _("Nouveau message"),
        "form": {"to": prefill, "cc": "", "subject": "", "body": ""},
    })
