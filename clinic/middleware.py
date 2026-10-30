from django.conf import settings
from django.utils import translation


class LanguageMiddleware:
    """Tilni cookie'dan oladi va model tarjima maydonlari uchun faollashtiradi."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.allowed = {code for code, _ in settings.LANGUAGES}

    def __call__(self, request):
        lang = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        if lang not in self.allowed or request.path.startswith("/panel/"):
            lang = settings.LANGUAGE_CODE
        translation.activate(lang)
        request.LANG = lang
        response = self.get_response(request)
        translation.deactivate()
        return response
