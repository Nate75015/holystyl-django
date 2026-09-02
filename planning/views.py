"""Vues web planning : grille jour/semaine/mois/année d'équipe + bon d'intervention."""

import calendar as _calendar
import json
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from equipe.models import Task, TeamMember
from operations.models import AffectationEngin, Machine
from exploitations.models import Exploitation
from parcelles.models import Parcelle

from .models import InterventionReport, PlanningTask


PALETTE = ["#335E8A", "#3B6D11", "#BA7517", "#3C3489", "#A32D2D", "#0E7490", "#7C3AED", "#B45309"]

#: Nombre de lignes de barres affichables dans une cellule du mois ; au-delà,
#: les tâches en trop sont résumées par un « +N ».
MONTH_MAX_LANES = 4

#: Les réservations de matériel ne sont pas assignées à un membre : une teinte
#: neutre les distingue des barres d'équipe, qui portent la couleur de chacun.
RESERVATION_COLOR = "#64748B"


def _member_colors(team_list):
    """Couleur distincte par membre : sa couleur perso si définie, sinon une
    couleur de palette stable (indexée sur l'ordre de l'équipe)."""
    default_color = (TeamMember._meta.get_field("color").default or "").lower()
    colors = {}
    for i, m in enumerate(team_list):
        custom = (m.color or "").strip()
        colors[m.id] = custom if custom and custom.lower() != default_color else PALETTE[i % len(PALETTE)]
    return colors


def _exploitation(request):
    return Exploitation.objects.filter(owner=request.user).first()


def _tasks_in_range(exploitation, members, start, end):
    """Tâches (sous-tâches comprises) chevauchant la fenêtre [start, end].

    Une tâche court de `start_date` à `due_date` ; si une seule des deux dates
    est saisie, elle tient lieu de début et de fin (tâche d'une journée).
    """
    if not (exploitation and members):
        return []
    return list(
        Task.objects.filter(exploitation=exploitation, assigned_to__in=members)
        .annotate(d_start=Coalesce("start_date", "due_date"), d_end=Coalesce("due_date", "start_date"))
        .filter(d_start__date__lte=end, d_end__date__gte=start)
        .select_related("assigned_to", "parent")
        .prefetch_related("subtasks", "parcelles")
        .order_by("d_start", "priority", "id")
    )


def _reservations_in_range(exploitation, start, end):
    """Réservations de matériel chevauchant la fenêtre [start, end].

    Sans date de fin, la réservation tient sur sa seule journée de début.
    """
    if not exploitation:
        return []
    return list(
        AffectationEngin.objects.filter(exploitation=exploitation)
        .annotate(d_end=Coalesce("date_fin", "date_debut"))
        .filter(date_debut__date__lte=end, d_end__date__gte=start)
        .select_related("machine", "parcelle")
        .order_by("date_debut", "id")
    )


def _reservation_payload(reservation):
    """Données de la réservation passées à la modale (attribut @click, donc JSON)."""
    debut, fin = reservation.periode
    return json.dumps(
        {
            "id": reservation.id,
            "machine": reservation.machine_id or "",
            "machine_nom": str(reservation.machine),
            "operation": reservation.operation,
            "start": timezone.localdate(debut).isoformat() if debut else "",
            "end": timezone.localdate(fin).isoformat() if fin else "",
            "parcelle": reservation.parcelle_id or "",
            "notes": reservation.notes,
        }
    )


def _payload(task):
    """Données de la tâche passées à la modale (attribut @click, donc JSON)."""
    debut, fin = task.periode
    return json.dumps(
        {
            "id": task.id,
            "title": task.title,
            "member": task.assigned_to_id or "",
            "start": timezone.localdate(debut).isoformat() if debut else "",
            "end": timezone.localdate(fin).isoformat() if fin else "",
            "priority": task.priority,
            "status": task.status,
            "description": task.description,
            "parcelles": [str(p.id) for p in task.parcelles.all()],
            "parent": task.parent.title if task.parent_id else "",
            "subtasks": [
                {
                    "id": st.id,
                    "title": st.title,
                    "done": st.is_done,
                    "member": st.assigned_to_id or "",
                    "date": timezone.localdate(st.due_date).isoformat() if st.due_date else "",
                }
                for st in sorted(task.subtasks.all(), key=lambda st: st.created_at)
            ],
        }
    )


def _decor_tache(colors):
    """Couleur, données de modale et nature d'une barre de tâche."""
    def decor(t):
        return {
            "color": (colors or {}).get(t.assigned_to_id, PALETTE[0]),
            "payload": _payload(t),
            "kind": "tache",
        }
    return decor


def _decor_reservation(r):
    """Idem pour une réservation de matériel, qui n'a pas de membre assigné."""
    return {"color": RESERVATION_COLOR, "payload": _reservation_payload(r), "kind": "reservation"}


def _bars(items, days, colors=None, max_lanes=None, decor=None):
    """Découpe tâches et réservations en barres continues sur la fenêtre `days`.

    Chaque barre occupe les colonnes de son début à sa fin (bornées à la
    fenêtre) et la première ligne libre, à la manière d'un agenda. Au-delà de
    `max_lanes` lignes, les barres du bas sont remplacées par un « +N » par jour.

    `decor` dit comment habiller un élément — couleur, données de modale,
    nature — pour que tâches et réservations partagent le même calcul de lignes
    sans se chevaucher.
    """
    n = len(days)
    first, last = days[0], days[-1]
    decor = decor or _decor_tache(colors)
    bars = []
    for t in items:
        debut, fin = t.periode
        if not (debut and fin):
            continue
        d0, d1 = timezone.localdate(debut), timezone.localdate(fin)
        if d1 < d0:
            d0, d1 = d1, d0
        if d1 < first or d0 > last:
            continue
        col = max(0, (d0 - first).days)
        col_end = min(n - 1, (d1 - first).days)
        bars.append(
            {
                "item": t,
                **decor(t),
                "col": col,
                "span": col_end - col + 1,
                "opens": d0 >= first,  # début réel visible (bord arrondi à gauche)
                "closes": d1 <= last,
                "date": max(d0, first).isoformat(),
            }
        )
    bars.sort(key=lambda b: (b["col"], -b["span"]))

    lanes = []  # lanes[i] = première colonne libre de la ligne i
    for b in bars:
        for i, free_from in enumerate(lanes):
            if b["col"] >= free_from:
                b["lane"] = i
                lanes[i] = b["col"] + b["span"]
                break
        else:
            b["lane"] = len(lanes)
            lanes.append(b["col"] + b["span"])

    if max_lanes is None or len(lanes) <= max_lanes:
        return {"bars": bars, "lanes": len(lanes), "more": [], "more_lane": None}

    # Débordement : on garde les lignes du haut, la dernière sert au « +N ».
    cap = max_lanes - 1
    hidden = defaultdict(int)
    for b in bars:
        if b["lane"] >= cap:
            for i in range(b["col"], b["col"] + b["span"]):
                hidden[i] += 1
    return {
        "bars": [b for b in bars if b["lane"] < cap],
        "lanes": max_lanes,
        "more": [{"col": col, "count": count, "date": days[col].isoformat()} for col, count in sorted(hidden.items())],
        "more_lane": cap,
    }


@login_required
def planning(request):
    exploitation = _exploitation(request)
    team_members = TeamMember.objects.filter(exploitation=exploitation) if exploitation else TeamMember.objects.none()

    today = timezone.localdate()

    # Vue (jour / semaine / mois / année) et date de référence (?vue=&date=YYYY-MM-DD).
    vue = request.GET.get("vue", "semaine")
    if vue not in ("jour", "semaine", "mois", "annee"):
        vue = "semaine"
    raw = request.GET.get("date")
    try:
        base = date.fromisoformat(raw) if raw else today
    except ValueError:
        base = today

    ctx = {
        "team_members": team_members,
        "today": today,
        "vue": vue,
        "anchor": base,
        "page_title": _("Planning"),
    }

    if vue == "jour":
        ctx.update(
            days=[base],
            ncols=1,
            label=base,
            prev_date=base - timedelta(days=1),
            next_date=base + timedelta(days=1),
            is_today_range=(base == today),
        )
    elif vue == "semaine":
        monday = base - timedelta(days=base.weekday())
        ctx.update(
            days=[monday + timedelta(days=i) for i in range(7)],
            ncols=7,
            week_start=monday,
            week_end=monday + timedelta(days=6),
            prev_date=monday - timedelta(days=7),
            next_date=monday + timedelta(days=7),
            is_today_range=(monday == today - timedelta(days=today.weekday())),
        )
    elif vue == "mois":
        first = base.replace(day=1)
        weeks = _calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month)
        team_list = list(team_members)
        member_color = _member_colors(team_list)
        month_tasks = _tasks_in_range(exploitation, team_list, weeks[0][0], weeks[-1][-1])
        month_reservations = _reservations_in_range(exploitation, weeks[0][0], weeks[-1][-1])
        # Un même calcul de lignes pour les deux : elles ne se chevauchent pas.
        decor_tache = _decor_tache(member_color)
        decor_mixte = lambda o: (_decor_reservation(o) if isinstance(o, AffectationEngin)
                                 else decor_tache(o))
        ctx.update(
            month_weeks=[
                {
                    "days": [{"date": d, "in_month": d.month == first.month} for d in week],
                    **_bars(month_tasks + month_reservations, week, member_color,
                            MONTH_MAX_LANES, decor=decor_mixte),
                }
                for week in weeks
            ],
            month_legend=[{"name": m.name, "color": member_color[m.id]} for m in team_list],
            month=first,
            current_month=first.month,
            prev_date=(first - timedelta(days=1)).replace(day=1),
            next_date=(first + timedelta(days=31)).replace(day=1),
            is_today_range=(first.year == today.year and first.month == today.month),
        )

    else:  # annee
        cal = _calendar.Calendar(firstweekday=0)
        months = [
            {"date": date(base.year, m, 1), "weeks": cal.monthdatescalendar(base.year, m)}
            for m in range(1, 13)
        ]
        team_list = list(team_members)
        member_color = _member_colors(team_list)
        # Pour chaque jour de l'année : les couleurs des membres occupés ce
        # jour-là, sur toute la durée de leurs tâches.
        day_colors = defaultdict(list)
        window_start, window_end = months[0]["weeks"][0][0], months[-1]["weeks"][-1][-1]
        annee_items = (_tasks_in_range(exploitation, team_list, window_start, window_end)
                       + _reservations_in_range(exploitation, window_start, window_end))
        for t in annee_items:
            debut, fin = t.periode
            d0, d1 = timezone.localdate(debut), timezone.localdate(fin)
            if d1 < d0:
                d0, d1 = d1, d0
            color = (RESERVATION_COLOR if isinstance(t, AffectationEngin)
                     else member_color.get(t.assigned_to_id, PALETTE[0]))
            d = max(d0, window_start)
            while d <= min(d1, window_end):
                if color not in day_colors[d]:
                    day_colors[d].append(color)
                d += timedelta(days=1)
        ctx.update(
            year_months=[
                {
                    "date": m["date"],
                    "weekdays": m["weeks"][0],
                    "weeks": [
                        [
                            {
                                "date": d,
                                "in_month": d.month == m["date"].month,
                                "colors": day_colors.get(d, [])[:3],
                            }
                            for d in week
                        ]
                        for week in m["weeks"]
                    ],
                }
                for m in months
            ],
            month_legend=[{"name": mb.name, "color": member_color[mb.id]} for mb in team_list],
            year=base.year,
            prev_date=date(base.year - 1, 1, 1),
            next_date=date(base.year + 1, 1, 1),
            is_today_range=(base.year == today.year),
        )

    # Vues jour / semaine : une ligne par membre, les tâches y sont posées en
    # barres continues sur leur période.
    if vue in ("jour", "semaine"):
        days = ctx["days"]
        team_list = list(team_members)
        tasks = _tasks_in_range(exploitation, team_list, days[0], days[-1])
        by_member = defaultdict(list)
        for t in tasks:
            by_member[t.assigned_to_id].append(t)
        rows = []
        for m in team_list:
            layout = _bars(by_member.get(m.id, []), days)
            rows.append(
                {
                    "member": m,
                    "cells": [{"date": d} for d in days],
                    "height": max(72, 18 + layout["lanes"] * 28),
                    **layout,
                }
            )
        ctx["rows"] = rows

        # Les réservations ne visent pas un membre mais un engin : elles ont
        # leur propre bande, une ligne par machine effectivement réservée.
        par_machine = defaultdict(list)
        for r in _reservations_in_range(exploitation, days[0], days[-1]):
            par_machine[r.machine_id].append(r)
        lignes_machines = []
        for lot in par_machine.values():
            layout = _bars(lot, days, decor=_decor_reservation)
            lignes_machines.append(
                {
                    "machine": lot[0].machine,
                    "cells": [{"date": d} for d in days],
                    "height": max(72, 18 + layout["lanes"] * 28),
                    **layout,
                }
            )
        lignes_machines.sort(key=lambda l: str(l["machine"]))
        ctx["machine_rows"] = lignes_machines

    ctx["priorities"] = Task.Priority.choices
    ctx["statuses"] = Task.Status.choices
    # Parcelles : la liste pour les pastilles, et leurs contours pour la carte
    # de sélection (les agriculteurs reconnaissent leurs parcelles à la forme,
    # pas à la référence cadastrale).
    parcelles = list(Parcelle.objects.filter(exploitation=exploitation)) if exploitation else []
    ctx["parcelles"] = parcelles
    ctx["parcelles_geojson"] = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": p.boundaries,
                "properties": {"id": p.pk, "name": p.name, "area": p.area},
            }
            for p in parcelles
            if p.boundaries
        ],
    }
    ctx["parcelles_mappables"] = sum(1 for p in parcelles if p.boundaries)
    ctx["machines"] = (list(Machine.objects.filter(exploitation=exploitation))
                       if exploitation else [])
    ctx["operations"] = AffectationEngin.Operation.choices
    return render(request, "planning/planning.html", ctx)


def _planning_url(request):
    """Retour à la grille en conservant vue et date."""
    vue = request.POST.get("vue") or "semaine"
    d = request.POST.get("date") or ""
    return f"{reverse('planning:planning')}?vue={vue}" + (f"&date={d}" if d else "")


def _aware(d):
    """Date (jour) → datetime aware à minuit, ou None."""
    return timezone.make_aware(datetime.combine(d, datetime.min.time())) if d else None


def _save_subtasks(task, request, exploitation):
    """Synchronise les tâches filles depuis le JSON du champ caché `subtasks`.

    Une sous-tâche est une tâche à part entière : elle a son assigné, sa date et
    son statut. Les lignes retirées côté modale sont supprimées.
    """
    try:
        rows = json.loads(request.POST.get("subtasks") or "[]")
    except json.JSONDecodeError:
        return
    if not isinstance(rows, list):
        return
    kept = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = (row.get("title") or "").strip()
        if not title:
            continue
        try:
            sub_id = int(row.get("id") or 0)
        except (TypeError, ValueError):
            sub_id = 0
        sub = Task.objects.filter(pk=sub_id, parent=task, exploitation=exploitation).first() if sub_id else None
        if sub is None:
            sub = Task(exploitation=exploitation, parent=task, created_by=request.user, priority=task.priority)
        sub.title = title[:255]
        if row.get("done"):
            sub.status = Task.Status.DONE
        elif sub.is_done:
            sub.status = Task.Status.TODO
        sub.assigned_to = (
            TeamMember.objects.filter(pk=row.get("member") or None, exploitation=exploitation).first() or task.assigned_to
        )
        d = parse_date(str(row.get("date") or ""))
        sub.start_date = sub.due_date = _aware(d)
        sub.save()
        kept.append(sub.pk)
    task.subtasks.exclude(pk__in=kept).delete()


def _save_task(task, request, exploitation):
    """Applique les champs POST à une tâche (création ou édition). False si invalide."""
    title = (request.POST.get("title") or "").strip()
    member = TeamMember.objects.filter(pk=request.POST.get("assigned_to"), exploitation=exploitation).first()
    if not (exploitation and title and member):
        return False
    # Période : début et fin. Une seule date saisie ⇒ tâche d'une journée.
    debut = parse_date(request.POST.get("start_date") or "")
    fin = parse_date(request.POST.get("due_date") or "")
    debut, fin = debut or fin, fin or debut
    if debut and fin and fin < debut:
        debut, fin = fin, debut
    priority = request.POST.get("priority")
    if priority not in Task.Priority.values:
        priority = Task.Priority.NORMALE
    status = request.POST.get("status")
    if status not in Task.Status.values:
        status = Task.Status.TODO
    task.title = title[:255]
    task.assigned_to = member
    task.start_date = _aware(debut)
    task.due_date = _aware(fin)
    task.priority = priority
    task.status = status
    task.description = (request.POST.get("description") or "").strip()
    # Parcelles : sélection multiple ; `parcelle` garde la première (API, espace employé).
    choisies = list(
        Parcelle.objects.filter(pk__in=request.POST.getlist("parcelles"), exploitation=exploitation).order_by("name")
    )
    task.parcelle = choisies[0] if choisies else None
    task.save()
    task.parcelles.set(choisies)
    _save_subtasks(task, request, exploitation)
    return True


@login_required
@require_POST
def task_create(request):
    exploitation = _exploitation(request)
    _save_task(Task(exploitation=exploitation, created_by=request.user), request, exploitation)
    return redirect(_planning_url(request))


@login_required
@require_POST
def task_edit(request, pk):
    exploitation = _exploitation(request)
    task = get_object_or_404(Task, pk=pk, exploitation=exploitation)
    _save_task(task, request, exploitation)
    return redirect(_planning_url(request))


@login_required
@require_POST
def task_delete(request, pk):
    exploitation = _exploitation(request)
    get_object_or_404(Task, pk=pk, exploitation=exploitation).delete()
    return redirect(_planning_url(request))


# ── Réservations de matériel ─────────────────────────────────────────


def _reservation_fields(request, exploitation):
    """Champs d'une réservation lus du POST, cloisonnés à l'exploitation.

    Machine et parcelle sont cherchées chez l'exploitant : un POST forgé ne
    peut pas réserver l'engin du voisin ni pointer sa parcelle.
    """
    machine = Machine.objects.filter(
        pk=request.POST.get("machine") or 0, exploitation=exploitation).first()
    if machine is None:
        return None

    operation = request.POST.get("operation") or AffectationEngin.Operation.AUTRE
    if operation not in AffectationEngin.Operation.values:
        operation = AffectationEngin.Operation.AUTRE

    debut = _aware(parse_date(request.POST.get("start") or ""))
    if debut is None:
        return None
    fin = _aware(parse_date(request.POST.get("end") or "")) or debut
    if fin < debut:
        debut, fin = fin, debut

    return {
        "machine": machine,
        "operation": operation,
        "date_debut": debut,
        "date_fin": fin,
        "parcelle": Parcelle.objects.filter(
            pk=request.POST.get("parcelle") or 0, exploitation=exploitation).first(),
        "notes": (request.POST.get("notes") or "").strip(),
    }


@login_required
@require_POST
def reservation_create(request):
    exploitation = _exploitation(request)
    champs = _reservation_fields(request, exploitation) if exploitation else None
    if champs:
        AffectationEngin.objects.create(
            exploitation=exploitation, created_by=request.user, **champs)
    else:
        messages.error(request, _("Réservation impossible : choisissez un matériel et une date."))
    return redirect(_planning_url(request))


@login_required
@require_POST
def reservation_edit(request, pk):
    exploitation = _exploitation(request)
    reservation = get_object_or_404(AffectationEngin, pk=pk, exploitation=exploitation)
    champs = _reservation_fields(request, exploitation)
    if champs:
        for champ, valeur in champs.items():
            setattr(reservation, champ, valeur)
        reservation.save()
    return redirect(_planning_url(request))


@login_required
@require_POST
def reservation_delete(request, pk):
    exploitation = _exploitation(request)
    get_object_or_404(AffectationEngin, pk=pk, exploitation=exploitation).delete()
    return redirect(_planning_url(request))


@login_required
def bon_intervention(request, task_id):
    """Bon d'intervention lié à une tâche planning (création/édition + signature)."""
    exploitation = _exploitation(request)
    task = get_object_or_404(PlanningTask, pk=task_id, exploitation=exploitation)
    report, _created = InterventionReport.objects.get_or_create(
        planning_task=task,
        exploitation=exploitation,
        defaults={
            "titre": task.titre,
            "intervention_type": task.type,
            "client_nom": task.client_nom,
            "technicien_nom": task.technicien_nom,
            "date_intervention": timezone.localdate(),
        },
    )

    if request.method == "POST":
        report.description_travaux = request.POST.get("description_travaux", "")
        report.observations = request.POST.get("observations", "")
        report.recommandations = request.POST.get("recommandations", "")
        report.signature_client_url = request.POST.get("signature_client_url", "")
        report.signature_client_nom = request.POST.get("signature_client_nom", "")
        report.signature_tech_url = request.POST.get("signature_tech_url", "")
        produits = request.POST.get("produits_utilises")
        if produits:
            try:
                report.produits_utilises = json.loads(produits)
            except json.JSONDecodeError:
                pass
        if request.POST.get("action") == "validate":
            report.statut = InterventionReport.Statut.VALIDE
        else:
            report.statut = InterventionReport.Statut.COMPLETE
        report.save()
        messages.success(request, _("Bon d'intervention enregistré."))
        return redirect("planning:planning")

    return render(
        request,
        "planning/bon_intervention.html",
        {"task": task, "report": report, "page_title": _("Bon d'intervention")},
    )
