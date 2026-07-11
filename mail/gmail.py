"""Intégration Gmail API (OAuth2) : connexion d'une boîte mail réelle.

Ce module encapsule tout l'accès à Gmail :
  • construction du flow OAuth (consentement Google → callback) ;
  • persistance chiffrée des jetons dans ``GmailAccount`` ;
  • un petit client haut-niveau (``GmailClient``) pour lister les libellés,
    lister/lire les messages d'un dossier, et les marquer comme lus.

Aucune donnée n'est stockée en base : on interroge l'API à la volée. Les
jetons OAuth (dont le *refresh token*) sont chiffrés au repos via Fernet,
avec une clé dérivée de ``SETTINGS.SECRET_KEY``.
"""

from __future__ import annotations

import base64
import hashlib
import json
from email.utils import parseaddr, parsedate_to_datetime

from django.conf import settings

# ── Portées OAuth demandées ─────────────────────────────────────────
# gmail.modify : lire + modifier libellés/état lu (pas de suppression def.).
# userinfo.email : récupérer l'adresse du compte connecté.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# ── Rail : dossiers/libellés Gmail affichés, dans l'ordre de la capture ──
# (clé Gmail, libellé FR, icône Material, section)
FOLDERS = [
    ("INBOX", "Boîte de réception", "inbox", "main"),
    ("STARRED", "Messages suivis", "star", "main"),
    ("SNOOZED", "En attente", "schedule", "main"),
    ("IMPORTANT", "Important", "label_important", "main"),
    ("SENT", "Messages envoyés", "send", "main"),
    ("DRAFT", "Brouillons", "insert_drive_file", "main"),
    ("CATEGORY_PURCHASES", "Achats", "shopping_bag", "main"),
    ("CATEGORY_SOCIAL", "Réseaux sociaux", "group", "main"),
    ("CATEGORY_UPDATES", "Notifications", "info", "main"),
    ("CATEGORY_FORUMS", "Forums", "forum", "main"),
    ("CATEGORY_PROMOTIONS", "Promotions", "local_offer", "main"),
    ("SCHEDULED", "Planifié", "schedule_send", "more"),
    ("ALL", "Tous les messages", "all_inbox", "more"),
    ("SPAM", "Spam", "report", "more"),
    ("TRASH", "Corbeille", "delete", "more"),
]

# Libellés « système » qui ne se filtrent pas via labelIds directement.
_QUERY_ONLY = {
    "ALL": "in:anywhere",
    "SCHEDULED": "in:scheduled",
    "SNOOZED": "in:snoozed",
}


def is_configured() -> bool:
    """Les identifiants OAuth Google sont-ils renseignés ?"""
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID and settings.GOOGLE_OAUTH_CLIENT_SECRET)


def redirect_uri() -> str:
    return settings.APP_URL.rstrip("/") + "/mail/oauth/callback/"


def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri()],
        }
    }


# ── Chiffrement des jetons au repos ─────────────────────────────────
def _fernet():
    from cryptography.fernet import Fernet

    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    return Fernet(key)


def encrypt_token(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt_token(blob: str) -> dict:
    return json.loads(_fernet().decrypt(blob.encode()).decode())


# ── Flow OAuth ──────────────────────────────────────────────────────
def build_flow(state: str | None = None):
    import os

    # Google renvoie souvent plus de scopes que demandé (grants antérieurs) :
    # on relâche la vérification sinon fetch_token lève « Scope has changed ».
    os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")
    # En dev, la redirection est en http://127.0.0.1 : oauthlib l'interdit
    # par défaut. On autorise le transport non chiffré uniquement en local.
    if redirect_uri().startswith("http://"):
        os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(_client_config(), scopes=SCOPES, state=state)
    flow.redirect_uri = redirect_uri()
    return flow


def creds_to_dict(creds) -> dict:
    return {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": creds.scopes,
    }


# ── Client haut-niveau ──────────────────────────────────────────────
class GmailClient:
    """Petit wrapper autour de l'API Gmail pour un compte connecté."""

    def __init__(self, account):
        self.account = account
        self._service = None

    def _credentials(self):
        from google.oauth2.credentials import Credentials

        data = decrypt_token(self.account.credentials)
        return Credentials(**data)

    @property
    def service(self):
        if self._service is None:
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = self._credentials()
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self.account.credentials = encrypt_token(creds_to_dict(creds))
                self.account.save(update_fields=["credentials", "updated_at"])
            self._service = build(
                "gmail", "v1", credentials=creds, cache_discovery=False
            )
        return self._service

    # ── Libellés & compteurs ────────────────────────────────────────
    def unread_counts(self) -> dict:
        """Nombre de messages non lus par libellé système (pour les badges)."""
        counts = {}
        try:
            resp = self.service.users().labels().list(userId="me").execute()
            wanted = {f[0] for f in FOLDERS}
            for lab in resp.get("labels", []):
                if lab["id"] in wanted:
                    detail = (
                        self.service.users()
                        .labels()
                        .get(userId="me", id=lab["id"])
                        .execute()
                    )
                    counts[lab["id"]] = detail.get("messagesUnread", 0)
        except Exception:  # noqa: BLE001 — badges non critiques
            pass
        return counts

    # ── Liste des messages d'un dossier ─────────────────────────────
    def list_messages(
        self,
        folder: str,
        max_results: int = 40,
        page_token: str | None = None,
        extra_labels: list | None = None,
    ):
        params = {"userId": "me", "maxResults": max_results}
        if page_token:
            params["pageToken"] = page_token
        if folder in _QUERY_ONLY:
            params["q"] = _QUERY_ONLY[folder]
        else:
            # extra_labels : intersection ET (ex. INBOX + CATEGORY_PROMOTIONS pour l'onglet Promotions).
            params["labelIds"] = [folder] + list(extra_labels or [])

        resp = self.service.users().messages().list(**params).execute()
        ids = [m["id"] for m in resp.get("messages", [])]
        messages = [self._get_meta(mid) for mid in ids]
        return messages, resp.get("nextPageToken")

    def _get_meta(self, mid: str) -> dict:
        msg = (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=mid,
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Date"],
            )
            .execute()
        )
        headers = {
            h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])
        }
        from_name, from_addr = parseaddr(headers.get("From", ""))
        short, full = self._fmt_date(headers.get("Date", ""))
        return {
            "id": mid,
            "thread_id": msg.get("threadId"),
            "from_name": from_name or from_addr,
            "from_addr": from_addr,
            "to": headers.get("To", ""),
            "subject": headers.get("Subject", "(sans objet)"),
            "snippet": msg.get("snippet", ""),
            "date_short": short,
            "date_full": full,
            "unread": "UNREAD" in msg.get("labelIds", []),
            "starred": "STARRED" in msg.get("labelIds", []),
            "has_attachment": self._has_attachment(msg.get("payload", {})),
        }

    @staticmethod
    def _fmt_date(raw: str):
        """(court, complet) depuis un en-tête Date RFC 2822."""
        try:
            dt = parsedate_to_datetime(raw)
            return dt.strftime("%d/%m"), dt.strftime("%d/%m/%Y %H:%M")
        except Exception:  # noqa: BLE001
            return raw[:6], raw

    @staticmethod
    def _has_attachment(payload) -> bool:
        for part in payload.get("parts", []) or []:
            if part.get("filename"):
                return True
        return False

    # ── Lecture d'un message complet ────────────────────────────────
    def get_message(self, mid: str) -> dict:
        msg = (
            self.service.users()
            .messages()
            .get(userId="me", id=mid, format="full")
            .execute()
        )
        payload = msg.get("payload", {})
        headers = {h["name"]: h["value"] for h in payload.get("headers", [])}
        from_name, from_addr = parseaddr(headers.get("From", ""))
        body_text, body_html = self._extract_body(payload)
        attachments = self._list_attachments(payload)
        _, date_full = self._fmt_date(headers.get("Date", ""))
        return {
            "id": mid,
            "from_name": from_name or from_addr,
            "from_addr": from_addr,
            "to": headers.get("To", ""),
            "cc": headers.get("Cc", ""),
            "subject": headers.get("Subject", "(sans objet)"),
            "date": date_full,
            "body_html": body_html,
            "body_text": body_text,
            "attachments": attachments,
            "unread": "UNREAD" in msg.get("labelIds", []),
        }

    def _extract_body(self, payload):
        text, html = "", ""

        def walk(part):
            nonlocal text, html
            mime = part.get("mimeType", "")
            data = part.get("body", {}).get("data")
            if data and mime == "text/plain" and not text:
                text = self._decode(data)
            elif data and mime == "text/html" and not html:
                html = self._decode(data)
            for sub in part.get("parts", []) or []:
                walk(sub)

        walk(payload)
        return text, html

    @staticmethod
    def _list_attachments(payload):
        out = []

        def walk(part):
            if part.get("filename"):
                out.append(
                    {
                        "filename": part["filename"],
                        "size": part.get("body", {}).get("size", 0),
                        "mime": part.get("mimeType", ""),
                    }
                )
            for sub in part.get("parts", []) or []:
                walk(sub)

        walk(payload)
        return out

    @staticmethod
    def _decode(data: str) -> str:
        return base64.urlsafe_b64decode(data.encode()).decode("utf-8", errors="replace")

    # ── Actions ─────────────────────────────────────────────────────
    def mark_read(self, mid: str):
        try:
            self.service.users().messages().modify(
                userId="me", id=mid, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
        except Exception:  # noqa: BLE001
            pass

    def toggle_star(self, mid: str, on: bool):
        body = {"addLabelIds": ["STARRED"]} if on else {"removeLabelIds": ["STARRED"]}
        self.service.users().messages().modify(userId="me", id=mid, body=body).execute()

    # ── Envoi depuis le compte connecté ─────────────────────────────
    def send_message(self, to, subject, body, cc=None, attachments=None):
        """Envoie un e-mail via l'API Gmail (from = l'adresse connectée).

        ``to`` / ``cc`` : listes d'adresses. ``attachments`` : liste de
        tuples ``(nom, contenu_bytes, content_type)``.
        """
        from email import encoders
        from email.mime.base import MIMEBase
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        if attachments:
            mime = MIMEMultipart()
            mime.attach(MIMEText(body or "", "plain", "utf-8"))
            for name, data, ctype in attachments:
                maintype, _, subtype = (ctype or "application/octet-stream").partition(
                    "/"
                )
                part = MIMEBase(maintype, subtype or "octet-stream")
                part.set_payload(data)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", "attachment", filename=name)
                mime.attach(part)
        else:
            mime = MIMEText(body or "", "plain", "utf-8")

        mime["To"] = ", ".join(to)
        if cc:
            mime["Cc"] = ", ".join(cc)
        mime["From"] = self.account.email
        mime["Subject"] = subject

        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        return (
            self.service.users()
            .messages()
            .send(userId="me", body={"raw": raw})
            .execute()
        )
