import json
from datetime import timedelta

from django.conf import settings
from django.core.cache import cache
from django.db.models import Max, Min
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.templatetags.static import static
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from .booking import (BookingError, book, day_slots, month_status, next_free, normalize_phone,
                      now_local, parse_day, parse_hour)
from .i18n import Texts
from .models import Appointment, Banner, Category, Doctor, Review, Service
from .search import search_doctors, search_services


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "")


def throttled(request, scope, limit, seconds):
    """So'rovlar sonini cheklaydi. Limitdan oshsa True qaytaradi."""
    key = f"rate:{scope}:{client_ip(request)}"
    cache.add(key, 0, seconds)
    return cache.incr(key) > limit


def active_services():
    return Service.objects.filter(is_active=True).select_related("category")


def active_doctors():
    return Doctor.objects.filter(is_active=True)


def home(request):
    return render(request, "site/home.html", {
        "banners": Banner.objects.filter(is_active=True),
        "categories": Category.objects.all(),
        "popular": active_services().filter(is_popular=True)[:8],
        "doctors": active_doctors(),
        "reviews": Review.objects.filter(is_active=True)[:6],
    })


def catalog(request):
    q = request.GET.get("q", "").strip()
    category = request.GET.get("category", "")
    doctor = request.GET.get("doctor", "")
    sort = request.GET.get("sort", "popular")
    bounds = Service.objects.filter(is_active=True).aggregate(low=Min("price"), high=Max("price"))

    services = search_services(q) if q else list(active_services())
    if category.isdigit():
        services = [s for s in services if s.category_id == int(category)]
    if doctor.isdigit():
        allowed = set(Service.objects.filter(doctors=doctor).values_list("id", flat=True))
        services = [s for s in services if s.id in allowed]

    def price_param(name):
        digits = "".join(ch for ch in request.GET.get(name, "") if ch.isdigit())
        return int(digits) if digits else None

    low, high = price_param("min"), price_param("max")
    if low is not None:
        services = [s for s in services if s.price >= low]
    if high is not None:
        services = [s for s in services if s.price <= high]

    if sort == "cheap":
        services.sort(key=lambda s: s.price)
    elif sort == "expensive":
        services.sort(key=lambda s: -s.price)
    elif sort == "discount":
        services = sorted((s for s in services if s.discount), key=lambda s: -s.discount)
    elif not q:
        services.sort(key=lambda s: (not s.is_popular, s.order))

    t = Texts()
    return render(request, "site/catalog.html", {
        "services": services,
        "categories": Category.objects.all(),
        "doctors": active_doctors(),
        "q": q,
        "selected_category": category,
        "selected_doctor": doctor,
        "sort": sort,
        "sort_options": [("popular", t["sort_popular"]), ("cheap", t["sort_cheap"]),
                         ("expensive", t["sort_expensive"]), ("discount", t["sort_discount"])],
        "min_value": low if low is not None else "",
        "max_value": high if high is not None else "",
        "price_low": bounds["low"] or 0,
        "price_high": bounds["high"] or 0,
    })


def service_detail(request, pk):
    service = get_object_or_404(active_services(), pk=pk)
    doctors = [(d, next_free(d)) for d in service.doctors.filter(is_active=True)]
    related = active_services().filter(category=service.category).exclude(pk=pk)[:4]
    return render(request, "site/service.html", {
        "service": service, "doctors": doctors, "related": related,
    })


def doctor_detail(request, pk):
    doctor = get_object_or_404(active_doctors(), pk=pk)
    return render(request, "site/doctor.html", {
        "doctor": doctor,
        "services": doctor.services.filter(is_active=True),
        "free": next_free(doctor),
    })


def booking_page(request):
    services = active_services().prefetch_related("doctors")
    data = [{
        "id": s.id, "name": s.name, "short": s.short, "price": s.price, "image": s.image_url,
        "category": s.category_id, "doctors": [d.id for d in s.doctors.all()],
    } for s in services]
    return render(request, "site/booking.html", {
        "services_json": data,
        "categories": Category.objects.all(),
        "preselect": {
            "service": request.GET.get("service", ""),
            "doctor": request.GET.get("doctor", ""),
        },
    })


def lookup(request):
    found = None
    error = False
    cancelled = False
    if request.method == "POST":
        if throttled(request, "lookup", 20, 600):
            raise Http404
        phone = normalize_phone(request.POST.get("phone"))
        code = request.POST.get("code", "").strip()
        found = (Appointment.objects.filter(client__phone=phone, code=code)
                 .select_related("doctor", "service").order_by("-date").first()) if phone else None
        error = found is None
        if found and request.POST.get("action") == "cancel" and can_cancel(found):
            found.status = Appointment.Status.CANCELLED
            found.save(update_fields=["status"])
            cancelled = True
    return render(request, "site/lookup.html", {
        "found": found, "error": error, "cancelled": cancelled,
        "can_cancel": bool(found and can_cancel(found)),
        "status_label": Texts()[f"st_{found.status}"] if found else "",
    })


def can_cancel(appointment):
    active = appointment.status in (Appointment.Status.NEW, Appointment.Status.CONFIRMED)
    return active and appointment.date >= now_local().date()


def set_language(request, code):
    target = request.GET.get("next", "/")
    if not url_has_allowed_host_and_scheme(target, allowed_hosts={request.get_host()}):
        target = "/"
    response = HttpResponseRedirect(target)
    if code in dict(settings.LANGUAGES):
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, code, max_age=31536000, samesite="Lax")
    return response


@require_GET
def api_search(request):
    q = request.GET.get("q", "").strip()[:60]
    if not q:
        return JsonResponse({"services": [], "doctors": []})
    return JsonResponse({
        "services": [{"id": s.id, "name": s.name, "price": s.price, "image": s.image_url,
                      "category": s.category.name} for s in search_services(q)[:6]],
        "doctors": [{"id": d.id, "name": d.name, "specialty": d.specialty, "image": d.image_url}
                    for d in search_doctors(q)[:3]],
    })


@require_GET
def api_doctors(request):
    service = get_object_or_404(Service, pk=request.GET.get("service") or 0, is_active=True)
    result = []
    for doctor in service.doctors.filter(is_active=True):
        result.append({"id": doctor.id, "name": doctor.name, "specialty": doctor.specialty,
                       "experience": doctor.experience, "image": doctor.image_url,
                       "next": next_free(doctor)})
    return JsonResponse({"doctors": result})


@require_GET
def api_month(request):
    doctor = get_object_or_404(active_doctors(), pk=request.GET.get("doctor") or 0)
    try:
        year, month = [int(x) for x in request.GET.get("month", "").split("-")]
        if not 2000 < year < 2100 or not 1 <= month <= 12:
            raise ValueError
    except ValueError:
        today = now_local().date()
        year, month = today.year, today.month
    return JsonResponse({"days": month_status(doctor, year, month)})


@require_GET
def api_slots(request):
    doctor = get_object_or_404(Doctor, pk=request.GET.get("doctor") or 0)
    day = parse_day(request.GET.get("date"))
    if not day:
        return JsonResponse({"slots": []})
    return JsonResponse({"slots": day_slots(doctor, day)})


@require_POST
def api_book(request):
    t = Texts()
    if throttled(request, "book", 12, 3600):
        return JsonResponse({"error": t["err_rate"]}, status=429)
    try:
        data = json.loads(request.body or "{}")
    except ValueError:
        return JsonResponse({"error": t["err_network"]}, status=400)
    if data.get("website"):  # botlar uchun yashirin maydon
        return JsonResponse({"error": t["err_rate"]}, status=400)

    service = Service.objects.filter(pk=data.get("service") or 0).first()
    doctor = Doctor.objects.filter(pk=data.get("doctor") or 0).first()
    day = parse_day(data.get("date"))
    hour = parse_hour(data.get("time"))
    if not (service and doctor and day and hour):
        return JsonResponse({"error": t["err_slot_taken"]}, status=400)
    try:
        appointment = book(service=service, doctor=doctor, day=day, hour=hour,
                           name=data.get("name"), phone=data.get("phone"),
                           note=str(data.get("note") or ""))
    except BookingError as exc:
        return JsonResponse({"error": t[f"err_{exc.code}"], "code": exc.code}, status=409)
    return JsonResponse({
        "code": appointment.code,
        "date": appointment.date.isoformat(),
        "time": appointment.time.strftime("%H:%M"),
        "end": (now_local().replace(hour=hour.hour, minute=hour.minute) + timedelta(hours=1)).strftime("%H:%M"),
    })


def robots(request):
    from django.http import HttpResponse
    return HttpResponse("User-agent: *\nDisallow: /panel/\n", content_type="text/plain")


def favicon(request):
    return HttpResponseRedirect(static("img/favicon.svg"))
