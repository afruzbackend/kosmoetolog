from django.conf import settings
from django.utils.translation import get_language

from .i18n import Texts, client_texts
from .models import Doctor, SiteSettings

FLAGS = {"uz": "uz", "ru": "ru", "en": "gb"}


def site(request):
    lang = (get_language() or "uz")[:2]
    return {
        "site": SiteSettings.load(),
        "t": Texts(),
        "client_texts": client_texts(),
        "doctor_count": Doctor.objects.filter(is_active=True).count(),
        "is_main": getattr(request, "user", None) is not None and request.user.is_superuser,
        "lang": lang,
        "lang_flag": FLAGS.get(lang, "uz"),
        "lang_options": [(code, label, FLAGS[code]) for code, label in settings.LANGUAGES],
    }
