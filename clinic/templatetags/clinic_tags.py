import os

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.utils.html import format_html

from ..booking import format_phone

register = template.Library()


@register.simple_tag
def asset(path):
    """Fayl o'zgarsa manzili ham o'zgaradi, brauzer eski CSS/JS'ni keshdan olmaydi."""
    found = finders.find(path)
    version = int(os.path.getmtime(found)) if found else 0
    return f"{static(path)}?v={version}"


@register.filter
def phone(value):
    return format_phone(value)


@register.filter
def money(value):
    if value in (None, ""):
        return ""
    return f"{int(value):,}".replace(",", " ")


@register.filter
def dotted(iso):
    """2026-10-30 -> 30.10.2026"""
    year, month, day = iso.split("-")
    return f"{day}.{month}.{year}"


@register.simple_tag
def icon(name, size=24):
    return format_html('<svg class="i ic" style="width:{}px;height:{}px" aria-hidden="true"><use href="#i-{}"/></svg>',
                       size, size, name)


@register.simple_tag
def brand(name, size=24):
    """Telegram va Instagramning asl logotiplari."""
    return format_html('<img class="brand" src="{}" width="{}" height="{}" alt="">',
                       static(f"img/brands/{name}.svg"), size, size)


@register.simple_tag
def flag(code, size=20):
    return format_html('<img class="flag" src="{}" width="{}" height="{}" alt="">',
                       static(f"img/flags/{code}.svg"), size, size)


@register.simple_tag(takes_context=True)
def query_with(context, **kwargs):
    """Joriy GET parametrlarini saqlagan holda bittasini almashtiradi."""
    params = context["request"].GET.copy()
    for key, value in kwargs.items():
        if value in (None, ""):
            params.pop(key, None)
        else:
            params[key] = value
    return params.urlencode()
