"""Xato sahifalari. Baza yoki statik fayllar ishlamasa ham ochilishi kerak."""
import logging

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import Resolver404, resolve

from .booking import format_phone
from .models import SiteSettings

log = logging.getLogger(__name__)

FALLBACK_BRAND = "Saragul Ahmedovna"
LANGS = {"uz": 0, "ru": 1, "en": 2}

MESSAGES = {
    400: (("So‘rov noto‘g‘ri", "Sahifa bu so‘rovni tushuna olmadi. Manzilni tekshirib, qayta urinib ko‘ring."),
          ("Неверный запрос", "Страница не смогла обработать запрос. Проверьте адрес и попробуйте снова."),
          ("Bad request", "This page could not process the request. Check the address and try again.")),
    403: (("Ruxsat yo‘q", "Bu sahifani ochish uchun sizda ruxsat yo‘q."),
          ("Доступ запрещён", "У вас нет прав для открытия этой страницы."),
          ("Access denied", "You do not have permission to open this page.")),
    404: (("Sahifa topilmadi", "Bu sahifa o‘chirilgan yoki manzil noto‘g‘ri yozilgan bo‘lishi mumkin."),
          ("Страница не найдена", "Возможно, страница удалена или адрес введён неверно."),
          ("Page not found", "This page may have been removed, or the address may be wrong.")),
    500: (("Serverda xatolik", "Muammo bizning tomonda. Bir ozdan keyin qayta urinib ko‘ring."),
          ("Ошибка на сервере", "Проблема на нашей стороне. Попробуйте ещё раз чуть позже."),
          ("Server error", "The problem is on our side. Please try again a little later.")),
    "csrf": (("Sahifa eskirgan", "Sahifa uzoq vaqt ochiq turgan. Yangilang va amalni qayta bajaring."),
             ("Страница устарела", "Страница была открыта слишком долго. Обновите её и повторите действие."),
             ("This page has expired", "This page was open for too long. Refresh it and try again.")),
}

LABELS = (
    {"home": "Bosh sahifa", "panel": "Panelga qaytish", "back": "Orqaga", "retry": "Sahifani yangilash",
     "help": "Yordam kerakmi?"},
    {"home": "На главную", "panel": "Вернуться в панель", "back": "Назад", "retry": "Обновить страницу",
     "help": "Нужна помощь?"},
    {"home": "Home", "panel": "Back to panel", "back": "Back", "retry": "Refresh the page",
     "help": "Need help?"},
)


def site_details():
    try:
        site = SiteSettings.load()
        return site.name, site.phone
    except Exception:  # baza ishlamayotgan bo'lishi mumkin
        log.warning("Xato sahifasi uchun sozlamalar o'qilmadi", exc_info=True)
        return FALLBACK_BRAND, ""


def error_response(request, key, status):
    lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME, "uz")
    index = LANGS.get(lang, 0)
    title, text = MESSAGES[key][index]
    labels = LABELS[index]
    in_panel = request.path.startswith("/panel/")
    brand, phone = site_details()
    html = render_to_string("errors/error.html", {
        "lang": lang if lang in LANGS else "uz", "code": status, "title": title, "text": text, "labels": labels,
        "brand": brand, "phone": phone, "phone_text": format_phone(phone), "retry": key in (500, "csrf"),
        "home_url": "/panel/" if in_panel else "/", "home_label": labels["panel" if in_panel else "home"],
    })
    return HttpResponse(html, status=status)


def bad_request(request, exception=None):
    return error_response(request, 400, 400)


def permission_denied(request, exception=None):
    return error_response(request, 403, 403)


def not_found(request, exception=None):
    return error_response(request, 404, 404)


def server_error(request):
    try:
        return error_response(request, 500, 500)
    except Exception:
        log.exception("Xato sahifasi ochilmadi")
        return HttpResponse("<h1>500</h1><p>Serverda xatolik. Keyinroq urinib ko'ring.</p>", status=500)


def csrf_failure(request, reason=""):
    return error_response(request, "csrf", 403)


def dev_not_found(request):
    """DEBUG rejimida ham dizayndagi 404: Django'ning texnik sahifasi o'rniga."""
    if not request.path.endswith("/"):
        try:
            match = resolve(request.path + "/")
        except Resolver404:
            match = None
        if match and match.func is not dev_not_found:
            return redirect(request.get_full_path(force_append_slash=True))
    return not_found(request)


def preview(request, name):
    """Faqat ishlab chiqishda: DEBUG yoqilganda Django xato sahifalarini ko'rsatmaydi."""
    key = "csrf" if name == "csrf" else int(name)
    return error_response(request, key, 403 if key == "csrf" else key)
