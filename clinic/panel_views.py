"""Admin panel: bosh admin hammasini, doktor faqat o'z ishini boshqaradi."""
from datetime import timedelta
from functools import wraps
from io import BytesIO

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, Max, Q, Sum
from django.db.models.deletion import ProtectedError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .booking import format_phone, normalize_phone, now_local, parse_day, work_hours
from .forms import (AppointmentForm, BannerForm, CategoryForm, ClientForm, DoctorForm, PanelPasswordForm,
                    ProfileForm, ReviewForm, ServiceForm, SettingsForm, TimeBlockForm)
from .models import Appointment, Banner, Category, Client, Doctor, Review, Service, SiteSettings, TimeBlock
from .views import client_ip

Status = Appointment.Status
LANG_FLAGS = {"uz": "uz", "ru": "ru", "en": "gb"}


def form_layout(form):
    """Formani shablon uchun tayyorlaydi: _uz/_ru/_en maydonlar til yorliqlariga birlashadi."""
    layout, seen = [], {}
    for field in form:
        base, _, suffix = field.name.rpartition("_")
        if suffix in LANG_FLAGS:
            if base not in seen:
                seen[base] = {"type": "lang", "label": str(field.label).split(" (")[0], "fields": []}
                layout.append(seen[base])
            seen[base]["fields"].append({"code": suffix, "flag": LANG_FLAGS[suffix], "field": field})
            continue
        item = {"type": "field", "field": field}
        widget = field.field.widget
        if field.field.__class__.__name__ == "ImageField":
            item["type"] = "image"
            value = field.value()
            item["current"] = value.url if value and hasattr(value, "url") else ""
            owner = form.instance
            item["fallback"] = getattr(owner, f"{field.name}_url", "") or getattr(owner, "image_url", "")
        elif widget.__class__.__name__ in ("CheckboxSelectMultiple", "RadioSelect"):
            item["type"] = "checks"
            item["input"] = "radio" if widget.__class__.__name__ == "RadioSelect" else "checkbox"
        elif widget.__class__.__name__ == "CheckboxInput":
            item["type"] = "switch"
        layout.append(item)
    return layout


def own_doctor(request):
    """Doktor loginida uning profili. Bosh adminda None: hamma narsa ko'rinadi."""
    if request.user.is_superuser:
        return None
    return getattr(request.user, "doctor_profile", None)


def can_enter(user):
    if user.is_superuser:
        return True
    profile = getattr(user, "doctor_profile", None)
    return bool(user.is_staff and profile and profile.is_active)


def panel_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if not can_enter(request.user):
            logout(request)
            return redirect("panel:login")
        return view(request, *args, **kwargs)
    return wrapper


def main_required(view):
    """Faqat bosh admin uchun bo'limlar."""
    @wraps(view)
    @panel_required
    def wrapper(request, *args, **kwargs):
        if not request.user.is_superuser:
            messages.error(request, "Bu bo'lim faqat bosh admin uchun.")
            return redirect("panel:dashboard")
        return view(request, *args, **kwargs)
    return wrapper


def scoped(request, rows):
    """Doktor faqat o'z navbatlarini ko'radi."""
    doctor = own_doctor(request)
    return rows.filter(doctor=doctor) if doctor else rows


def login_view(request):
    if request.user.is_authenticated and can_enter(request.user):
        return redirect("panel:dashboard")
    error = ""
    if request.method == "POST":
        key = f"login:{client_ip(request)}"
        if cache.get(key, 0) >= 5:
            error = "Urinishlar ko'p. 5 daqiqadan keyin qayta urining."
        else:
            user = authenticate(request, username=request.POST.get("username", ""),
                                password=request.POST.get("password", ""))
            if user and can_enter(user):
                cache.delete(key)
                login(request, user)
                return redirect(safe_next(request, "panel:dashboard"))
            cache.add(key, 0, 300)
            cache.incr(key)
            error = "Login yoki parol noto'g'ri."
    return render(request, "panel/login.html", {"error": error})


@require_POST
def logout_view(request):
    logout(request)
    return redirect("panel:login")


def safe_next(request, fallback, *args):
    target = request.POST.get("next") or request.GET.get("next")
    if target and url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        return target
    return redirect(fallback, *args).url


def day_stats(day, doctor=None):
    rows = Appointment.objects.filter(date=day)
    clients = Client.objects.filter(created_at__date=day)
    if doctor:
        rows = rows.filter(doctor=doctor)
        clients = clients.filter(appointments__doctor=doctor).distinct()
    active = rows.exclude(status=Status.CANCELLED)
    return {
        "total": active.count(),
        "done": rows.filter(status=Status.DONE).count(),
        "waiting": rows.filter(status__in=[Status.NEW, Status.CONFIRMED]).count(),
        "cancelled": rows.filter(status=Status.CANCELLED).count(),
        "noshow": rows.filter(status=Status.NOSHOW).count(),
        "revenue": rows.filter(status=Status.DONE).aggregate(s=Sum("price"))["s"] or 0,
        "expected": active.exclude(status=Status.NOSHOW).aggregate(s=Sum("price"))["s"] or 0,
        "new_clients": clients.count(),
    }


@panel_required
def dashboard(request):
    today = now_local().date()
    base = scoped(request, Appointment.objects.select_related("client", "doctor", "service"))
    new_requests = base.filter(status=Status.NEW, date__gte=today).order_by("date", "time")[:8]
    todays = base.filter(date=today).exclude(status=Status.CANCELLED)
    return render(request, "panel/dashboard.html", {
        "section": "dashboard", "today": today, "stats": day_stats(today, own_doctor(request)),
        "todays": todays, "new_requests": new_requests,
    })


@panel_required
def calendar(request):
    day = parse_day(request.GET.get("date")) or now_local().date()
    own = own_doctor(request)
    doctors = [own] if own else list(Doctor.objects.filter(is_active=True))
    bookings = (scoped(request, Appointment.objects.filter(date=day)).exclude(status=Status.CANCELLED)
                .select_related("client", "service"))
    by_cell = {(a.doctor_id, a.time): a for a in bookings}
    blocks = TimeBlock.objects.filter(date=day)
    center_closed = any(b.doctor_id is None and b.time is None for b in blocks)
    blocked = {(b.doctor_id, b.time) for b in blocks}

    hours = sorted({h for d in doctors for h in work_hours(d)})
    rows = []
    for hour in hours:
        cells = []
        for doctor in doctors:
            state = "free"
            appointment = by_cell.get((doctor.id, hour))
            if appointment:
                state = "booked"
            elif (center_closed or day.weekday() not in doctor.work_day_set
                  or (doctor.id, None) in blocked or (doctor.id, hour) in blocked
                  or (None, hour) in blocked or hour not in work_hours(doctor)):
                state = "off"
            cells.append({"state": state, "appointment": appointment, "doctor": doctor})
        rows.append({"hour": hour, "cells": cells})
    return render(request, "panel/calendar.html", {
        "section": "calendar", "day": day, "doctors": doctors, "rows": rows,
        "prev": day - timedelta(days=1), "next": day + timedelta(days=1),
        "is_today": day == now_local().date(), "stats": day_stats(day, own),
    })


@panel_required
def appointments(request):
    q = request.GET.get("q", "").strip()
    rows = scoped(request, Appointment.objects.select_related("client", "doctor", "service"))
    rows = rows.order_by("-date", "-time")
    if q:
        digits = "".join(ch for ch in q if ch.isdigit())
        match = Q(client__search_text__contains=q.lower())
        if digits:
            match |= Q(code=digits) | Q(client__phone__contains=digits)
        rows = rows.filter(match)
    status = request.GET.get("status", "")
    doctor = request.GET.get("doctor", "")
    start, end = parse_day(request.GET.get("from")), parse_day(request.GET.get("to"))
    if status in Status.values:
        rows = rows.filter(status=status)
    if doctor.isdigit():
        rows = rows.filter(doctor_id=doctor)
    if start:
        rows = rows.filter(date__gte=start)
    if end:
        rows = rows.filter(date__lte=end)
    page = Paginator(rows, 25).get_page(request.GET.get("page"))
    return render(request, "panel/appointments.html", {
        "section": "appointments", "page": page, "q": q, "status": status, "doctor": doctor,
        "from": request.GET.get("from", ""), "to": request.GET.get("to", ""),
        "doctors": Doctor.objects.all(), "statuses": Status.choices,
    })


@panel_required
def appointment_form(request, pk=None):
    own = own_doctor(request)
    instance = None
    if pk:
        instance = get_object_or_404(scoped(request, Appointment.objects.select_related("client")), pk=pk)
    if request.method == "POST":
        form = AppointmentForm(request.POST, instance=instance, own_doctor=own)
        if form.is_valid():
            try:
                with transaction.atomic():
                    saved = form.save()
            except IntegrityError:
                form.add_error("time", "Bu soatda mutaxassisda boshqa mijoz bor.")
            else:
                messages.success(request, f"Navbat saqlandi: {saved.date:%d.%m.%Y} {saved.time:%H:%M}")
                return redirect(safe_next(request, "panel:calendar") if instance
                                else f"/panel/kalendar/?date={saved.date}")
    else:
        initial = {}
        if not instance:
            initial = {"date": request.GET.get("date") or now_local().date(),
                       "time": request.GET.get("time", ""), "doctor": request.GET.get("doctor", ""),
                       "status": Status.CONFIRMED}
        form = AppointmentForm(instance=instance, initial=initial, own_doctor=own)
    prices ={str(s.id): s.price for s in Service.objects.all()}
    return render(request, "panel/appointment_form.html", {
        "section": "calendar", "form": form, "instance": instance, "prices": prices,
    })


@panel_required
@require_POST
def appointment_status(request, pk):
    appointment = get_object_or_404(scoped(request, Appointment.objects.all()), pk=pk)
    status = request.POST.get("status")
    if status in Status.values:
        appointment.status = status
        try:
            with transaction.atomic():
                appointment.save(update_fields=["status"])
        except IntegrityError:
            messages.error(request, "Bu vaqtga boshqa mijoz yozilgan, holatni tiklab bo'lmaydi.")
    return redirect(safe_next(request, "panel:dashboard"))


@panel_required
def client_lookup(request):
    client = Client.objects.filter(phone=normalize_phone(request.GET.get("phone"))).first()
    return JsonResponse({"name": client.name if client else ""})


@panel_required
def clients(request):
    q = request.GET.get("q", "").strip()
    doctor = own_doctor(request)
    base = Client.objects.filter(appointments__doctor=doctor) if doctor else Client.objects.all()
    rows = base.annotate(
        visits=Count("appointments", filter=Q(appointments__status=Status.DONE)),
        spent=Sum("appointments__price", filter=Q(appointments__status=Status.DONE)),
        last=Max("appointments__date"),
    ).order_by("-last", "-created_at")
    if q:
        digits = "".join(ch for ch in q if ch.isdigit())
        match = Q(search_text__contains=q.lower())
        if digits:
            match |= Q(phone__contains=digits)
        rows = rows.filter(match)
    return render(request, "panel/clients.html", {
        "section": "clients", "q": q, "page": Paginator(rows, 25).get_page(request.GET.get("page")),
    })


@panel_required
def client_card(request, pk):
    client = get_object_or_404(Client, pk=pk)
    doctor = own_doctor(request)
    if doctor and not client.appointments.filter(doctor=doctor).exists():
        raise Http404
    form = ClientForm(request.POST or None, instance=client)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Mijoz ma'lumotlari saqlandi.")
        return redirect("panel:client", pk=pk)
    history = scoped(request, client.appointments.select_related("doctor", "service")).order_by("-date", "-time")
    done = history.filter(status=Status.DONE)
    return render(request, "panel/client.html", {
        "section": "clients", "client": client, "form": form, "history": history,
        "visits": done.count(), "spent": done.aggregate(s=Sum("price"))["s"] or 0,
    })


def report_rows(start, end, doctor=None):
    rows = Appointment.objects.filter(date__gte=start, date__lte=end)
    if doctor:
        rows = rows.filter(doctor=doctor)
    done = rows.filter(status=Status.DONE)
    by_doctor = (rows.exclude(status=Status.CANCELLED).values("doctor__name_uz")
                 .annotate(total=Count("id"), done=Count("id", filter=Q(status=Status.DONE)),
                           revenue=Sum("price", filter=Q(status=Status.DONE)))
                 .order_by("-revenue", "-total"))
    by_service = (done.values("service__name_uz").annotate(total=Count("id"), revenue=Sum("price"))
                  .order_by("-revenue"))
    return rows, done, by_doctor, by_service


@panel_required
def report(request):
    today = now_local().date()
    start = parse_day(request.GET.get("from")) or today
    end = parse_day(request.GET.get("to")) or start
    if end < start:
        start, end = end, start
    own = own_doctor(request)
    rows, done, by_doctor, by_service = report_rows(start, end, own)
    active = rows.exclude(status=Status.CANCELLED)
    new_clients = Client.objects.filter(created_at__date__gte=start, created_at__date__lte=end)
    if own:
        new_clients = new_clients.filter(appointments__doctor=own).distinct()
    summary = {
        "total": active.count(),
        "done": done.count(),
        "cancelled": rows.filter(status=Status.CANCELLED).count(),
        "noshow": rows.filter(status=Status.NOSHOW).count(),
        "revenue": done.aggregate(s=Sum("price"))["s"] or 0,
        "new_clients": new_clients.count(),
    }
    summary["average"] = summary["revenue"] // summary["done"] if summary["done"] else 0

    # So'nggi 30 kun tushumi: grafik uchun
    chart_start = end - timedelta(days=29)
    paid = scoped(request, Appointment.objects.filter(status=Status.DONE, date__gte=chart_start, date__lte=end))
    totals = dict(paid.values_list("date").annotate(s=Sum("price")))
    days = [chart_start + timedelta(days=i) for i in range(30)]
    peak = max(totals.values(), default=0) or 1
    chart = [{"date": d, "value": totals.get(d, 0), "height": round(totals.get(d, 0) * 100 / peak)}
             for d in days]
    return render(request, "panel/report.html", {
        "section": "report", "start": start, "end": end, "single": start == end, "summary": summary,
        "by_doctor": by_doctor, "by_service": by_service, "chart": chart, "chart_peak": peak,
        "has_chart": bool(totals),
        "rows": rows.select_related("client", "doctor", "service").order_by("date", "time"),
        "prev": start - timedelta(days=1), "next": start + timedelta(days=1),
        "week_start": today - timedelta(days=6), "month_start": today.replace(day=1), "today": today,
    })


@panel_required
def report_excel(request):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    today = now_local().date()
    start = parse_day(request.GET.get("from")) or today
    end = parse_day(request.GET.get("to")) or start
    rows, done, by_doctor, by_service = report_rows(start, end, own_doctor(request))

    book = Workbook()
    sheet = book.active
    sheet.title = "Navbatlar"
    header = ["Sana", "Soat", "Mijoz", "Telefon", "Xizmat", "Mutaxassis", "Holat", "Narx (so'm)"]
    sheet.append(header)
    for a in rows.select_related("client", "doctor", "service").order_by("date", "time"):
        sheet.append([a.date.strftime("%d.%m.%Y"), a.time.strftime("%H:%M"), a.client.name,
                      format_phone(a.client.phone), a.service.name_uz, a.doctor.name_uz,
                      a.get_status_display(), a.price])
    sheet.append([])
    sheet.append(["", "", "", "", "", "", "Tushum", done.aggregate(s=Sum("price"))["s"] or 0])

    fill = PatternFill("solid", fgColor="E0117F")
    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = fill
        cell.alignment = Alignment(horizontal="center")
    for letter, width in zip("ABCDEFGH", (12, 8, 26, 20, 26, 22, 16, 14)):
        sheet.column_dimensions[letter].width = width
    for row in sheet.iter_rows(min_col=8, max_col=8, min_row=2):
        row[0].number_format = "#,##0"

    summary = book.create_sheet("Mutaxassislar")
    summary.append(["Mutaxassis", "Navbatlar", "Bajarildi", "Tushum (so'm)"])
    for row in by_doctor:
        summary.append([row["doctor__name_uz"], row["total"], row["done"], row["revenue"] or 0])
    for cell in summary[1]:
        cell.font = Font(bold=True)
    summary.column_dimensions["A"].width = 26

    buffer = BytesIO()
    book.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="hisobot-{start}_{end}.xlsx"'
    return response


CRUD = {
    "shifokorlar": {
        "model": Doctor, "form": DoctorForm, "title": "Mutaxassislar", "one": "Mutaxassis", "section": "doctors",
        "columns": [("Rasm", "image_url", "image"), ("Ism", "name_uz", "text"),
                    ("Mutaxassislik", "specialty_uz", "text"), ("Telefon", "phone", "phone"),
                    ("Login", "login_name", "text"), ("Faol", "is_active", "bool")],
    },
    "xizmatlar": {
        "model": Service, "form": ServiceForm, "title": "Xizmatlar", "one": "Xizmat", "section": "services",
        "columns": [("Rasm", "image_url", "image"), ("Nomi", "name_uz", "text"), ("Kategoriya", "category", "text"),
                    ("Narx", "price", "money"), ("Ommabop", "is_popular", "bool"), ("Faol", "is_active", "bool")],
    },
    "kategoriyalar": {
        "model": Category, "form": CategoryForm, "title": "Kategoriyalar", "one": "Kategoriya", "section": "services",
        "columns": [("Rasm", "image_url", "image"), ("Nomi", "name_uz", "text"), ("Ruscha", "name_ru", "text"),
                    ("Inglizcha", "name_en", "text")],
    },
    "bannerlar": {
        "model": Banner, "form": BannerForm, "title": "Bannerlar", "one": "Banner", "section": "banners",
        "columns": [("Rasm", "image_url", "image"), ("Sarlavha", "title_uz", "text"), ("Tartib", "order", "text"),
                    ("Faol", "is_active", "bool")],
    },
    "sharhlar": {
        "model": Review, "form": ReviewForm, "title": "Sharhlar", "one": "Sharh", "section": "reviews",
        "columns": [("Mijoz", "author", "text"), ("Sharh", "text", "text"), ("Baho", "rating", "text"),
                    ("Faol", "is_active", "bool")],
    },
    "dam-olish": {
        "model": TimeBlock, "form": TimeBlockForm, "title": "Dam olish kunlari", "one": "Dam olish",
        "section": "blocks",
        "columns": [("Sana", "date", "text"), ("Mutaxassis", "doctor", "text"), ("Soat", "time", "text"),
                    ("Sabab", "reason", "text")],
    },
}


def crud_config(slug):
    config = CRUD.get(slug)
    if not config:
        raise Http404
    return config


@main_required
def crud_list(request, slug):
    config = crud_config(slug)
    rows = []
    for obj in config["model"].objects.all():
        rows.append({"pk": obj.pk, "cells": [
            {"kind": kind, "value": getattr(obj, attr)} for _, attr, kind in config["columns"]]})
    return render(request, "panel/crud_list.html", {
        "section": config["section"], "config": config, "slug": slug, "rows": rows,
        "headers": [label for label, _, _ in config["columns"]],
    })


@main_required
def crud_form(request, slug, pk=None):
    config = crud_config(slug)
    instance = get_object_or_404(config["model"], pk=pk) if pk else None
    form = config["form"](request.POST or None, request.FILES or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{config['one']} saqlandi.")
        return redirect("panel:crud", slug=slug)
    return render(request, "panel/crud_form.html", {
        "section": config["section"], "config": config, "slug": slug, "form": form,
        "instance": instance, "layout": form_layout(form),
    })


@main_required
@require_POST
def crud_delete(request, slug, pk):
    config = crud_config(slug)
    try:
        obj = get_object_or_404(config["model"], pk=pk)
        account = getattr(obj, "user", None)
        obj.delete()
        if account and not account.is_superuser:
            account.delete()
        messages.success(request, f"{config['one']} o'chirildi.")
    except ProtectedError:
        messages.error(request, "O'chirib bo'lmaydi: unga bog'langan navbatlar yoki xizmatlar bor. "
                                "Buning o'rniga «Faol» belgisini o'chiring.")
    return redirect("panel:crud", slug=slug)


@main_required
def settings_page(request):
    site = SiteSettings.load()
    form = SettingsForm(request.POST or None, request.FILES or None, instance=site)
    password_form = PanelPasswordForm(request.user)
    if request.method == "POST":
        if request.POST.get("form") == "password":
            form = SettingsForm(instance=site)
            password_form = PanelPasswordForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Parol yangilandi.")
                return redirect("panel:settings")
        elif form.is_valid():
            form.save()
            messages.success(request, "Sozlamalar saqlandi.")
            return redirect("panel:settings")
    return render(request, "panel/settings.html", {
        "section": "settings", "form": form, "layout": form_layout(form), "password_form": password_form,
    })


@panel_required
def profile(request):
    """Doktor o'z profili va parolini o'zi boshqaradi."""
    doctor = own_doctor(request)
    if not doctor:
        return redirect("panel:settings")
    form = ProfileForm(request.POST or None, request.FILES or None, instance=doctor)
    password_form = PanelPasswordForm(request.user)
    if request.method == "POST":
        if request.POST.get("form") == "password":
            form = ProfileForm(instance=doctor)
            password_form = PanelPasswordForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Parol yangilandi.")
                return redirect("panel:profile")
        elif form.is_valid():
            form.save()
            messages.success(request, "Profil saqlandi.")
            return redirect("panel:profile")
    return render(request, "panel/profile.html", {
        "section": "profile", "form": form, "layout": form_layout(form), "password_form": password_form,
    })
