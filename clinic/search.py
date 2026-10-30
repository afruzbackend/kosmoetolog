"""Aqlli qidiruv: uch tilda, kirill-lotin farqisiz va xatolarga chidamli."""
import re
from difflib import SequenceMatcher

from .models import Doctor, Service

CYR = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "j", "з": "z",
    "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "s", "ч": "ch", "ш": "sh", "щ": "sh",
    "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya", "ў": "o", "қ": "q", "ғ": "g",
    "ҳ": "h",
}
APOSTROPHES = re.compile(r"[ʻʼ'`’‘]")


def normalize(text):
    """Yozilishdagi farqlarni yo'qotadi: Хиджама, xijoma, hijama bir xil asosga keladi."""
    value = APOSTROPHES.sub("", (text or "").lower())
    value = "".join(CYR.get(ch, ch) for ch in value)
    for src, dst in (("dzh", "j"), ("dj", "j"), ("kh", "h"), ("th", "t"), ("ph", "f"),
                     ("x", "h"), ("z", "s"), ("c", "s"), ("w", "v"), ("q", "k")):
        value = value.replace(src, dst)
    value = re.sub(r"[^a-z0-9 ]+", " ", value)
    value = re.sub(r"(.)\1+", r"\1", value)
    return re.sub(r"\s+", " ", value).strip()


def _score(query, hay):
    if not query:
        return 0
    position = hay.find(query)
    if position >= 0:
        boundary = position == 0 or hay[position - 1] == " "
        return 100 if boundary else 80
    words = hay.split()
    total = 0.0
    terms = query.split()
    for term in terms:
        best = 0.0
        for word in words:
            best = max(best, SequenceMatcher(None, term, word).ratio(),
                       SequenceMatcher(None, term, word[: len(term) + 1]).ratio())
        if best < 0.72:
            return 0
        total += best
    return 60 * total / len(terms)


def _service_hay(s):
    parts = [s.name_uz, s.name_ru, s.name_en, s.short_uz, s.short_ru, s.short_en, s.keywords,
             s.category.name_uz, s.category.name_ru, s.category.name_en]
    return normalize(" ".join(parts))


def _doctor_hay(d):
    return normalize(" ".join([d.name_uz, d.name_ru, d.name_en, d.specialty_uz, d.specialty_ru,
                               d.specialty_en]))


def search_services(query):
    q = normalize(query)
    rows = Service.objects.filter(is_active=True).select_related("category")
    scored = [(_score(q, _service_hay(s)), s) for s in rows]
    return [s for score, s in sorted(scored, key=lambda p: -p[0]) if score > 0]


def search_doctors(query):
    q = normalize(query)
    scored = [(_score(q, _doctor_hay(d)), d) for d in Doctor.objects.filter(is_active=True)]
    return [d for score, d in sorted(scored, key=lambda p: -p[0]) if score > 0]
