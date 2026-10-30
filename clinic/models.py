import random
from datetime import time

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.templatetags.static import static
from django.utils.translation import get_language


class Localized:
    """`obj.name` joriy tildagi `name_uz/ru/en` maydonini qaytaradi."""

    def __init__(self, base):
        self.base = base

    def __get__(self, obj, owner=None):
        if obj is None:
            return self
        lang = (get_language() or "uz")[:2]
        return getattr(obj, f"{self.base}_{lang}", "") or getattr(obj, f"{self.base}_uz", "")


class ImageMixin(models.Model):
    """Rasm yuklanmagan bo'lsa, static ichidagi standart rasm ko'rsatiladi."""

    default_image = models.CharField(max_length=120, blank=True, editable=False)

    class Meta:
        abstract = True

    @property
    def image_url(self):
        field = getattr(self, "image", None) or getattr(self, "photo", None)
        if field:
            return field.url
        return static(self.default_image or "img/placeholder.svg")


class SiteSettings(models.Model):
    name = models.CharField("Markaz nomi", max_length=80, default="Saragul Ahmedovna")
    logo = models.ImageField("Logotip", upload_to="site/", blank=True)
    tagline_uz = models.CharField("Shior (uz)", max_length=160, blank=True)
    tagline_ru = models.CharField("Shior (ru)", max_length=160, blank=True)
    tagline_en = models.CharField("Shior (en)", max_length=160, blank=True)
    phone = models.CharField("Telefon", max_length=12, blank=True)
    phone2 = models.CharField("Qo'shimcha telefon", max_length=12, blank=True)
    telegram = models.CharField("Telegram (username)", max_length=64, blank=True)
    instagram = models.CharField("Instagram (username)", max_length=64, blank=True)
    address_uz = models.CharField("Manzil (uz)", max_length=200, blank=True)
    address_ru = models.CharField("Manzil (ru)", max_length=200, blank=True)
    address_en = models.CharField("Manzil (en)", max_length=200, blank=True)
    latitude = models.DecimalField("Kenglik", max_digits=9, decimal_places=6, default=41.311081)
    longitude = models.DecimalField("Uzunlik", max_digits=9, decimal_places=6, default=69.240562)
    booking_days_ahead = models.PositiveSmallIntegerField("Necha kun oldinga navbat olinadi", default=30)
    tg_bot_token = models.CharField("Telegram bot token", max_length=80, blank=True)
    tg_chat_id = models.CharField("Telegram chat ID", max_length=32, blank=True)

    tagline = Localized("tagline")
    address = Localized("address")

    class Meta:
        verbose_name = "Sozlamalar"

    def __str__(self):
        return self.name

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def logo_url(self):
        return self.logo.url if self.logo else static("img/favicon.svg")

    @property
    def google_maps_url(self):
        return f"https://www.google.com/maps/search/?api=1&query={self.latitude},{self.longitude}"

    @property
    def yandex_maps_url(self):
        return f"https://yandex.uz/maps/?pt={self.longitude},{self.latitude}&z=16&l=map"

    @property
    def google_embed_url(self):
        return f"https://maps.google.com/maps?q={self.latitude},{self.longitude}&z=16&output=embed"

    @property
    def yandex_embed_url(self):
        return (f"https://yandex.uz/map-widget/v1/?ll={self.longitude},{self.latitude}"
                f"&z=16&pt={self.longitude},{self.latitude},pm2rdm")


class Category(ImageMixin):
    name_uz = models.CharField("Nomi (uz)", max_length=80)
    name_ru = models.CharField("Nomi (ru)", max_length=80, blank=True)
    name_en = models.CharField("Nomi (en)", max_length=80, blank=True)
    image = models.ImageField("Rasm", upload_to="categories/", blank=True)
    order = models.PositiveSmallIntegerField("Tartib", default=0)

    name = Localized("name")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Kategoriya"

    def __str__(self):
        return self.name_uz


class Doctor(ImageMixin):
    name_uz = models.CharField("Ism (uz)", max_length=100)
    name_ru = models.CharField("Ism (ru)", max_length=100, blank=True)
    name_en = models.CharField("Ism (en)", max_length=100, blank=True)
    specialty_uz = models.CharField("Mutaxassislik (uz)", max_length=120)
    specialty_ru = models.CharField("Mutaxassislik (ru)", max_length=120, blank=True)
    specialty_en = models.CharField("Mutaxassislik (en)", max_length=120, blank=True)
    bio_uz = models.TextField("Haqida (uz)", blank=True)
    bio_ru = models.TextField("Haqida (ru)", blank=True)
    bio_en = models.TextField("Haqida (en)", blank=True)
    experience = models.PositiveSmallIntegerField("Tajriba (yil)", default=1)
    photo = models.ImageField("Asosiy rasm", upload_to="doctors/", blank=True)
    photo2 = models.ImageField("Ikkinchi rasm", upload_to="doctors/", blank=True)
    default_image2 = models.CharField(max_length=120, blank=True, editable=False)
    phone = models.CharField("Telefon", max_length=12, blank=True)
    telegram = models.CharField("Telegram", max_length=64, blank=True)
    instagram = models.CharField("Instagram", max_length=64, blank=True)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="doctor_profile", editable=False)
    work_days =models.CharField("Ish kunlari", max_length=20, default="0,1,2,3,4,5")
    work_start = models.TimeField("Ish boshlanishi", default=time(9, 0))
    work_end = models.TimeField("Ish tugashi", default=time(18, 0))
    lunch_hour = models.TimeField("Tushlik soati", null=True, blank=True, default=time(13, 0))
    is_active = models.BooleanField("Faol", default=True)
    order = models.PositiveSmallIntegerField("Tartib", default=0)

    name = Localized("name")
    specialty = Localized("specialty")
    bio = Localized("bio")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Mutaxassis"

    def __str__(self):
        return self.name_uz

    @property
    def login_name(self):
        return self.user.username if self.user else "—"

    @property
    def photo2_url(self):
        if self.photo2:
            return self.photo2.url
        return static(self.default_image2) if self.default_image2 else ""

    @property
    def work_day_set(self):
        return {int(d) for d in self.work_days.split(",") if d.strip().isdigit()}


class Service(ImageMixin):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="services",
                                 verbose_name="Kategoriya")
    name_uz = models.CharField("Nomi (uz)", max_length=120)
    name_ru = models.CharField("Nomi (ru)", max_length=120, blank=True)
    name_en = models.CharField("Nomi (en)", max_length=120, blank=True)
    short_uz = models.CharField("Qisqa tavsif (uz)", max_length=160, blank=True)
    short_ru = models.CharField("Qisqa tavsif (ru)", max_length=160, blank=True)
    short_en = models.CharField("Qisqa tavsif (en)", max_length=160, blank=True)
    description_uz = models.TextField("To'liq tavsif (uz)", blank=True)
    description_ru = models.TextField("To'liq tavsif (ru)", blank=True)
    description_en = models.TextField("To'liq tavsif (en)", blank=True)
    keywords = models.CharField("Qidiruv so'zlari", max_length=240, blank=True,
                                help_text="Vergul bilan: akne, husnbuzar, ugri")
    price = models.PositiveIntegerField("Narx (so'm)")
    old_price = models.PositiveIntegerField("Eski narx (so'm)", null=True, blank=True)
    image = models.ImageField("Rasm", upload_to="services/", blank=True)
    doctors =models.ManyToManyField(Doctor, related_name="services", verbose_name="Mutaxassislar")
    is_popular = models.BooleanField("Ommabop", default=False)
    is_active = models.BooleanField("Faol", default=True)
    order = models.PositiveSmallIntegerField("Tartib", default=0)

    name = Localized("name")
    short = Localized("short")
    description = Localized("description")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Xizmat"

    def __str__(self):
        return self.name_uz

    @property
    def discount(self):
        if self.old_price and self.old_price > self.price:
            return round((self.old_price - self.price) * 100 / self.old_price)
        return 0


class Banner(ImageMixin):
    image = models.ImageField("Rasm", upload_to="banners/", blank=True)
    title_uz = models.CharField("Sarlavha (uz)", max_length=120)
    title_ru = models.CharField("Sarlavha (ru)", max_length=120, blank=True)
    title_en = models.CharField("Sarlavha (en)", max_length=120, blank=True)
    subtitle_uz = models.CharField("Matn (uz)", max_length=200, blank=True)
    subtitle_ru = models.CharField("Matn (ru)", max_length=200, blank=True)
    subtitle_en = models.CharField("Matn (en)", max_length=200, blank=True)
    badge = models.CharField("Belgi (masalan: -20%)", max_length=20, blank=True)
    link = models.CharField("Havola", max_length=200, blank=True, default="/navbat/")
    is_active = models.BooleanField("Faol", default=True)
    order = models.PositiveSmallIntegerField("Tartib", default=0)

    title = Localized("title")
    subtitle = Localized("subtitle")

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Banner"

    def __str__(self):
        return self.title_uz


class Review(models.Model):
    author = models.CharField("Mijoz ismi", max_length=80)
    text = models.TextField("Sharh")
    rating = models.PositiveSmallIntegerField("Baho (1-5)", default=5)
    is_active = models.BooleanField("Faol", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Sharh"

    def __str__(self):
        return self.author

    @property
    def stars(self):
        return range(self.rating)


class Client(models.Model):
    phone = models.CharField("Telefon", max_length=12, unique=True)
    name = models.CharField("Ism", max_length=100)
    note = models.TextField("Izoh", blank=True)
    search_text = models.CharField(max_length=140, blank=True, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Mijoz"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        # SQLite kirill harflarida katta-kichik harfni farqlaydi, shuning uchun alohida ustun
        self.search_text = f"{self.name} {self.phone}".lower()
        super().save(*args, **kwargs)


def make_code():
    return f"{random.randint(0, 999999):06d}"


class Appointment(models.Model):
    class Status(models.TextChoices):
        NEW = "new", "Yangi"
        CONFIRMED = "confirmed", "Tasdiqlangan"
        DONE = "done", "Bajarildi"
        NOSHOW = "noshow", "Kelmadi"
        CANCELLED = "cancelled", "Bekor qilindi"

    class Source(models.TextChoices):
        SITE = "site", "Sayt"
        PANEL = "panel", "Administrator"

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="appointments",
                               verbose_name="Mijoz")
    doctor = models.ForeignKey(Doctor, on_delete=models.PROTECT, related_name="appointments",
                               verbose_name="Mutaxassis")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="appointments",
                                verbose_name="Xizmat")
    date = models.DateField("Sana", db_index=True)
    time = models.TimeField("Soat")
    status = models.CharField("Holat", max_length=12, choices=Status.choices, default=Status.NEW)
    price = models.PositiveIntegerField("Narx (so'm)", default=0)
    note = models.CharField("Izoh", max_length=240, blank=True)
    code = models.CharField("Kod", max_length=6, default=make_code, db_index=True)
    source = models.CharField(max_length=8, choices=Source.choices, default=Source.SITE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["date", "time"]
        verbose_name = "Navbat"
        constraints = [
            # Bir mutaxassisda bir soatga faqat bitta mijoz
            models.UniqueConstraint(
                fields=["doctor", "date", "time"],
                condition=~Q(status="cancelled"),
                name="one_client_per_doctor_hour",
            ),
        ]

    def __str__(self):
        return f"{self.date} {self.time:%H:%M} {self.client}"


class TimeBlock(models.Model):
    """Dam olish kuni yoki band soat. Mutaxassis tanlanmasa, butun markazga tegishli."""

    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, null=True, blank=True,
                               related_name="blocks", verbose_name="Mutaxassis")
    date = models.DateField("Sana", db_index=True)
    time = models.TimeField("Soat", null=True, blank=True, help_text="Bo'sh qoldirilsa — butun kun")
    reason = models.CharField("Sabab", max_length=120, blank=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "Dam olish"

    def __str__(self):
        return f"{self.date} {self.reason}"
