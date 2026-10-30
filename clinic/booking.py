"""Navbat mantig'i: har bir shifokor uchun alohida, soatiga bitta mijoz."""
import logging
import threading
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from .models import Appointment, Client, SiteSettings, TimeBlock

log = logging.getLogger(__name__)

MAX_ACTIVE_PER_PHONE = 3


class BookingError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def now_local():
    return timezone.localtime()


def normalize_phone(value):
    """Har qanday yozuvdan 998XXXXXXXXX ko'rinishini qaytaradi, noto'g'ri bo'lsa bo'sh satr."""
    digits = "".join(ch for ch in (value or "") if ch.isdigit())
    if len(digits) == 9:
        digits = "998" + digits
    return digits if len(digits) == 12 and digits.startswith("998") else ""


def format_phone(digits):
    d = digits or ""
    if len(d) != 12:
        return d
    return f"+{d[:3]} {d[3:5]} {d[5:8]} {d[8:10]} {d[10:]}"


def work_hours(doctor):
    """Shifokorning kunlik 1 soatlik slotlari (tushlikdan tashqari)."""
    hours = []
    current = datetime.combine(date.min, doctor.work_start)
    end = datetime.combine(date.min, doctor.work_end)
    while current + timedelta(hours=1) <= end:
        if current.time() != doctor.lunch_hour:
            hours.append(current.time())
        current += timedelta(hours=1)
    return hours


def _blocks(doctor, day):
    rows = TimeBlock.objects.filter(Q(doctor=doctor) | Q(doctor__isnull=True), date=day)
    whole_day = any(b.time is None for b in rows)
    return whole_day, {b.time for b in rows if b.time}


def day_slots(doctor, day):
    """Kun slotlari: [{"time": "09:00", "free": True}, ...]. Dam olish kunida bo'sh ro'yxat."""
    if day.weekday() not in doctor.work_day_set:
        return []
    whole_day, blocked = _blocks(doctor, day)
    if whole_day:
        return []
    taken = set(
        Appointment.objects.filter(doctor=doctor, date=day)
        .exclude(status=Appointment.Status.CANCELLED)
        .values_list("time", flat=True)
    )
    now = now_local()
    slots = []
    for hour in work_hours(doctor):
        past = day < now.date() or (day == now.date() and hour <= now.time())
        slots.append({"time": hour.strftime("%H:%M"),
                      "free": not past and hour not in taken and hour not in blocked})
    return slots


def month_status(doctor, year, month):
    """Oy kalendari uchun: har bir kun holati free / full / off / past."""
    settings = SiteSettings.load()
    today = now_local().date()
    last = today + timedelta(days=settings.booking_days_ahead)
    result = {}
    day = date(year, month, 1)
    while day.month == month:
        key = day.isoformat()
        if day < today or day > last:
            result[key] = "past"
        else:
            slots = day_slots(doctor, day)
            if not slots:
                result[key] = "off"
            else:
                result[key] = "free" if any(s["free"] for s in slots) else "full"
        day += timedelta(days=1)
    return result


def next_free(doctor, days=14):
    """Eng yaqin bo'sh vaqt."""
    today = now_local().date()
    for offset in range(days):
        day = today + timedelta(days=offset)
        for slot in day_slots(doctor, day):
            if slot["free"]:
                return {"date": day.isoformat(), "time": slot["time"]}
    return None


def book(*, service, doctor, day, hour, name, phone, note="", source=Appointment.Source.SITE):
    """Navbatni yaratadi. Bir vaqtda ikki so'rov kelsa ham UniqueConstraint himoya qiladi."""
    phone = normalize_phone(phone)
    name = " ".join((name or "").split())
    if len(name) < 2:
        raise BookingError("bad_name")
    if not phone:
        raise BookingError("bad_phone")
    if not service.doctors.filter(pk=doctor.pk).exists():
        raise BookingError("bad_doctor")
    if not doctor.is_active or not service.is_active:
        raise BookingError("bad_doctor")

    value = hour.strftime("%H:%M")
    free = {s["time"] for s in day_slots(doctor, day) if s["free"]}
    if value not in free:
        raise BookingError("slot_taken")

    if source == Appointment.Source.SITE:
        limit = now_local().date() + timedelta(days=SiteSettings.load().booking_days_ahead)
        if day > limit:
            raise BookingError("slot_taken")
        active = Appointment.objects.filter(
            client__phone=phone, date__gte=now_local().date(),
            status__in=[Appointment.Status.NEW, Appointment.Status.CONFIRMED],
        ).count()
        if active >= MAX_ACTIVE_PER_PHONE:
            raise BookingError("too_many")

    try:
        with transaction.atomic():
            client, created = Client.objects.get_or_create(phone=phone, defaults={"name": name})
            if not created and client.name != name:
                client.name = name
                client.save()
            appointment = Appointment.objects.create(
                client=client, doctor=doctor, service=service, date=day, time=hour,
                price=service.price, note=note[:240], source=source,
            )
    except IntegrityError as exc:
        raise BookingError("slot_taken") from exc
    notify_telegram(appointment)
    return appointment


def notify_telegram(appointment):
    """Yangi navbat haqida Telegram xabari. Sozlanmagan bo'lsa jim o'tadi."""
    settings = SiteSettings.load()
    if not settings.tg_bot_token or not settings.tg_chat_id:
        return
    text = (f"🌸 Yangi navbat\n{appointment.date:%d.%m.%Y} {appointment.time:%H:%M}\n"
            f"{appointment.client.name} {format_phone(appointment.client.phone)}\n"
            f"{appointment.service.name_uz} — {appointment.doctor.name_uz}")
    url = f"https://api.telegram.org/bot{settings.tg_bot_token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": settings.tg_chat_id, "text": text}).encode()

    def send():
        try:
            urllib.request.urlopen(url, data=data, timeout=5).read()
        except Exception:  # xabar ketmasa ham navbat saqlanib qoladi
            log.warning("Telegram xabari yuborilmadi", exc_info=True)

    threading.Thread(target=send, daemon=True).start()


def parse_day(value):
    try:
        return datetime.strptime(value or "", "%Y-%m-%d").date()
    except ValueError:
        return None


def parse_hour(value):
    try:
        return datetime.strptime(value or "", "%H:%M").time()
    except ValueError:
        return None
