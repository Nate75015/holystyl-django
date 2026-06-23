"""Vues web parcelles : liste, wizard de création, détail, édition, suppression."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _

from exploitations.models import Exploitation

from .forms import ParcelleForm
from .models import Parcelle


def _exploitation_or_redirect(request):
    return Exploitation.objects.filter(owner=request.user).first()


@login_required
def parcelle_list(request):
    exploitation = _exploitation_or_redirect(request)
    parcelles = (
        Parcelle.objects.filter(exploitation=exploitation) if exploitation else Parcelle.objects.none()
    )
    return render(
        request,
        "parcelles/list.html",
        {"parcelles": parcelles, "needs_onboarding": exploitation is None, "page_title": _("Parcelles")},
    )


@login_required
def parcelle_create(request):
    exploitation = _exploitation_or_redirect(request)
    if exploitation is None:
        messages.info(request, _("Configurez d'abord votre exploitation."))
        return redirect("exploitations:settings")

    if request.method == "POST":
        form = ParcelleForm(request.POST)
        if form.is_valid():
            parcelle = form.save(commit=False)
            parcelle.exploitation = exploitation
            parcelle.save()
            messages.success(request, _("Parcelle créée."))
            return redirect("parcelles:detail", pk=parcelle.pk)
    else:
        form = ParcelleForm()

    return render(
        request,
        "parcelles/form.html",
        {"form": form, "page_title": _("Nouvelle parcelle"), "is_create": True},
    )


@login_required
def parcelle_detail(request, pk):
    exploitation = _exploitation_or_redirect(request)
    parcelle = get_object_or_404(Parcelle, pk=pk, exploitation=exploitation)
    return render(
        request,
        "parcelles/detail.html",
        {"parcelle": parcelle, "page_title": parcelle.name},
    )


@login_required
def parcelle_edit(request, pk):
    exploitation = _exploitation_or_redirect(request)
    parcelle = get_object_or_404(Parcelle, pk=pk, exploitation=exploitation)
    if request.method == "POST":
        form = ParcelleForm(request.POST, instance=parcelle)
        if form.is_valid():
            form.save()
            messages.success(request, _("Parcelle mise à jour."))
            return redirect("parcelles:detail", pk=parcelle.pk)
    else:
        form = ParcelleForm(instance=parcelle)
    return render(
        request,
        "parcelles/form.html",
        {"form": form, "parcelle": parcelle, "page_title": _("Modifier %(n)s") % {"n": parcelle.name}},
    )


@login_required
def parcelle_delete(request, pk):
    exploitation = _exploitation_or_redirect(request)
    parcelle = get_object_or_404(Parcelle, pk=pk, exploitation=exploitation)
    if request.method == "POST":
        parcelle.delete()
        messages.success(request, _("Parcelle supprimée."))
        return redirect("parcelles:list")
    return render(request, "parcelles/confirm_delete.html", {"parcelle": parcelle})
