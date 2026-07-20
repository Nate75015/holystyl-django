"""Vue web : centre de notifications."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from exploitations.models import Exploitation
from ia import llm

from .forms import NotificationRuleForm
from .models import Notification, NotificationRule

_REFORMULATE_PROMPT = (
    "Tu nommes des règles d'alerte agricoles dans une application de suivi d'exploitation. "
    "Reformule la saisie de l'agriculteur en un nom de règle court (6 mots maximum), clair "
    "et explicite, en français. "
    "IMPÉRATIF : conserve exactement le sujet et le sens de la saisie. N'invente aucune "
    "grandeur, aucun capteur ni aucune mesure qui n'y figure pas. Le type et la condition "
    "entre parenthèses ne sont qu'un contexte : ils ne doivent jamais remplacer le sujet. "
    "Corrige l'orthographe et la casse, notamment celle des noms de lieux. "
    "Réponds UNIQUEMENT par le nom, sans guillemets ni préambule ni point final."
)


def _exploitation(request):
    # Les lieux surveillés (villes météo) appartiennent à l'exploitation, pas à l'utilisateur.
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def center(request):
    exploitation = _exploitation(request)
    form = NotificationRuleForm(exploitation=exploitation)
    if request.method == "POST":
        form = NotificationRuleForm(request.POST, exploitation=exploitation)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.user = request.user
            rule.save()
            messages.success(request, _("Règle « %(r)s » créée.") % {"r": rule.name})
            return redirect("notifications:center")
    return render(
        request,
        "notifications/center.html",
        {
            "notifications": Notification.objects.filter(user=request.user)[:100],
            "rules": NotificationRule.objects.filter(user=request.user).select_related("ville"),
            "form": form,
            "page_title": _("Notifications"),
        },
    )


@login_required
@require_POST
def rule_edit(request, pk):
    """Modifie une règle (soumis depuis la modale de /notifications/)."""
    rule = get_object_or_404(NotificationRule, pk=pk, user=request.user)
    form = NotificationRuleForm(request.POST, instance=rule, exploitation=_exploitation(request))
    if form.is_valid():
        form.save()
        messages.success(request, _("Règle « %(r)s » modifiée.") % {"r": rule.name})
    else:
        messages.error(request, _("Modification impossible : vérifiez les champs."))
    return redirect("notifications:center")


@login_required
@require_POST
def rule_toggle(request, pk):
    """Active / désactive une règle sans la supprimer."""
    rule = get_object_or_404(NotificationRule, pk=pk, user=request.user)
    rule.enabled = not rule.enabled
    rule.save(update_fields=["enabled", "updated_at"])
    messages.success(
        request,
        _("Règle « %(r)s » activée.") % {"r": rule.name} if rule.enabled
        else _("Règle « %(r)s » désactivée.") % {"r": rule.name},
    )
    return redirect("notifications:center")


@login_required
@require_POST
def rule_delete(request, pk):
    """Supprime définitivement une règle (confirmation côté template)."""
    rule = get_object_or_404(NotificationRule, pk=pk, user=request.user)
    name = rule.name
    rule.delete()
    messages.success(request, _("Règle « %(r)s » supprimée.") % {"r": name})
    return redirect("notifications:center")


@login_required
@require_POST
def rule_reformulate(request):
    """Reformule le nom d'une règle via l'IA (repli : renvoie le texte original)."""
    name = (request.POST.get("name") or "").strip()
    if not name or not llm.is_configured():
        return JsonResponse({"name": name})
    # Le type et la condition affinent le nom proposé, sans être obligatoires.
    # str() : les libellés sont des proxies de traduction paresseux, non concaténables.
    context = ", ".join(
        str(label) for label in [
            dict(NotificationRule.Type.choices).get(request.POST.get("type")),
            dict(NotificationRule.ConditionType.choices).get(request.POST.get("condition_type")),
        ] if label
    )
    try:
        out = llm.generate_text(
            [
                {"role": "system", "content": _REFORMULATE_PROMPT},
                {"role": "user", "content": f"Règle ({context}) : {name[:500]}" if context else name[:500]},
            ],
            temperature=0.5,
        )
        return JsonResponse({"name": (out or name).strip()[:255]})
    except Exception:  # noqa: BLE001 — indispo IA → repli sur le nom saisi
        return JsonResponse({"name": name})
