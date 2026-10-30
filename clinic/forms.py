import re

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordChangeForm

from .booking import normalize_phone, now_local
from .models import Appointment, Banner, Category, Client, Doctor, Review, Service, SiteSettings, TimeBlock

WEEKDAYS = [("0", "Du"), ("1", "Se"), ("2", "Ch"), ("3", "Pa"), ("4", "Ju"), ("5", "Sh"), ("6", "Ya")]


class PhoneField(forms.CharField):
    widget = forms.TextInput(attrs={"data-mask": "phone", "inputmode": "tel", "autocomplete": "tel",
                                    "placeholder": "+998 50 000 00 00"})

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return ""
        digits = normalize_phone(value)
        if not digits:
            raise forms.ValidationError("Raqamni to'liq kiriting: +998 50 000 00 00")
        return digits


class MoneyField(forms.IntegerField):
    widget = forms.TextInput(attrs={"data-mask": "money", "inputmode": "numeric"})

    def to_python(self, value):
        if isinstance(value, str):
            value = "".join(ch for ch in value if ch.isdigit())
        return super().to_python(value)


class TimeMaskInput(forms.TimeInput):
    def __init__(self):
        super().__init__(format="%H:%M", attrs={"data-mask": "time", "inputmode": "numeric", "placeholder": "09:00"})


class ImageRules:
    """Yuklanadigan rasmlar hajmini cheklaydi (formatni ImageField tekshiradi)."""

    def clean(self):
        cleaned = super().clean()
        for name, field in self.fields.items():
            upload = self.files.get(name)
            if isinstance(field, forms.ImageField) and upload and upload.size > settings.MAX_IMAGE_BYTES:
                self.add_error(name, "Rasm 5 MB dan oshmasligi kerak.")
        return cleaned


class HandleRules:
    """Telegram va Instagramga havola yozilsa ham faqat username saqlanadi."""

    def clean_handle(self, name):
        value = self.cleaned_data.get(name, "").strip()
        value = re.sub(r"^(https?://)?(www\.)?(t\.me|telegram\.me|instagram\.com)/", "", value)
        return value.split("?")[0].strip("/@ ")

    def clean_telegram(self):
        return self.clean_handle("telegram")

    def clean_instagram(self):
        return self.clean_handle("instagram")


class CategoryForm(ImageRules, forms.ModelForm):
    class Meta:
        model = Category
        fields = ["image", "name_uz", "name_ru", "name_en", "order"]


class DoctorForm(HandleRules, ImageRules, forms.ModelForm):
    phone = PhoneField(label="Telefon", required=False)
    days = forms.MultipleChoiceField(label="Ish kunlari", choices=WEEKDAYS,
                                     widget=forms.CheckboxSelectMultiple)
    login_username = forms.CharField(label="Panelga kirish logini", required=False, max_length=40,
                                     widget=forms.TextInput(attrs={"autocomplete": "off"}))
    login_password = forms.CharField(label="Parol", required=False, min_length=8,
                                     widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
                                     help_text="Kamida 8 belgi. Bo'sh qolsa, parol o'zgarmaydi.")

    field_order = ["name_uz", "name_ru", "name_en", "specialty_uz", "specialty_ru", "specialty_en",
                   "bio_uz", "bio_ru", "bio_en", "photo", "photo2", "experience", "phone", "telegram",
                   "instagram", "work_start", "work_end", "lunch_hour", "order", "days", "is_active",
                   "login_username", "login_password"]

    class Meta:
        model = Doctor
        fields = ["name_uz", "name_ru", "name_en", "specialty_uz", "specialty_ru", "specialty_en",
                  "bio_uz", "bio_ru", "bio_en", "experience", "photo", "photo2", "phone", "telegram",
                  "instagram", "work_start", "work_end", "lunch_hour", "is_active", "order"]
        widgets = {"work_start": TimeMaskInput(), "work_end": TimeMaskInput(), "lunch_hour": TimeMaskInput(),
                   "bio_uz": forms.Textarea(attrs={"rows": 4}), "bio_ru": forms.Textarea(attrs={"rows": 4}),
                   "bio_en": forms.Textarea(attrs={"rows": 4}),
                   "telegram": forms.TextInput(attrs={"placeholder": "username yoki t.me havolasi"}),
                   "instagram": forms.TextInput(attrs={"placeholder": "username yoki instagram havolasi"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["days"].initial = [d for d in self.instance.work_days.split(",") if d]
        if self.instance.pk and self.instance.user:
            self.fields["login_username"].initial = self.instance.user.username

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("work_start"), cleaned.get("work_end")
        if start and end and start >= end:
            self.add_error("work_end", "Ish tugashi boshlanishidan keyin bo'lishi kerak.")
        if "login_username" in self.fields:
            self.clean_login(cleaned)
        return cleaned

    def clean_login(self, cleaned):
        username = cleaned.get("login_username", "").strip()
        account = self.instance.user if self.instance.pk else None
        if not username:
            if cleaned.get("login_password"):
                self.add_error("login_username", "Parol uchun login kiriting.")
            return
        if not re.fullmatch(r"[\w.@+-]+", username):
            self.add_error("login_username", "Loginda faqat harf, raqam va . _ - belgilari bo'lsin.")
        taken = get_user_model().objects.filter(username=username)
        if account:
            taken = taken.exclude(pk=account.pk)
        if taken.exists():
            self.add_error("login_username", "Bu login band.")
        if not account and not cleaned.get("login_password"):
            self.add_error("login_password", "Yangi login uchun parol kiriting.")

    def save(self, commit=True):
        self.instance.work_days = ",".join(sorted(self.cleaned_data["days"]))
        doctor = super().save(commit)
        username = self.cleaned_data.get("login_username", "").strip()
        if username:
            account = doctor.user or get_user_model()(is_staff=True)
            account.username = username
            if self.cleaned_data.get("login_password"):
                account.set_password(self.cleaned_data["login_password"])
            account.save()
            if doctor.user_id != account.pk:
                doctor.user = account
                doctor.save(update_fields=["user"])
        return doctor


class ProfileForm(DoctorForm):
    """Doktor o'zi tahrirlaydigan maydonlar: login, faollik va tartib bosh adminda qoladi."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("login_username", "login_password", "is_active", "order"):
            del self.fields[name]


class ServiceForm(ImageRules, forms.ModelForm):
    price = MoneyField(label="Narx (so'm)", min_value=0)
    old_price = MoneyField(label="Eski narx (so'm)", required=False, min_value=0)

    class Meta:
        model = Service
        fields = ["name_uz", "name_ru", "name_en", "short_uz", "short_ru", "short_en",
                  "description_uz", "description_ru", "description_en", "category", "price",
                  "old_price", "image", "doctors", "keywords", "is_popular", "is_active", "order"]
        widgets = {"doctors": forms.CheckboxSelectMultiple,
                   "description_uz": forms.Textarea(attrs={"rows": 5}),
                   "description_ru": forms.Textarea(attrs={"rows": 5}),
                   "description_en": forms.Textarea(attrs={"rows": 5})}


class BannerForm(ImageRules, forms.ModelForm):
    class Meta:
        model = Banner
        fields = ["image", "title_uz", "title_ru", "title_en", "subtitle_uz", "subtitle_ru", "subtitle_en",
                  "badge", "link", "is_active", "order"]


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(label="Baho", coerce=int, widget=forms.RadioSelect,
                                    choices=[(n, str(n)) for n in range(1, 6)], initial=5)

    class Meta:
        model = Review
        fields = ["author", "text", "rating", "is_active"]
        widgets = {"text": forms.Textarea(attrs={"rows": 4})}


class PanelPasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        labels = {"old_password": "Joriy parol", "new_password1": "Yangi parol",
                  "new_password2": "Yangi parolni takrorlang"}
        for name, label in labels.items():
            self.fields[name].label = label
            self.fields[name].help_text = ""


class TimeBlockForm(forms.ModelForm):
    class Meta:
        model = TimeBlock
        fields = ["date", "doctor", "time", "reason"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"), "time": TimeMaskInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["doctor"].empty_label = "Butun markaz"


class ClientForm(forms.ModelForm):
    phone = PhoneField(label="Telefon")

    class Meta:
        model = Client
        fields = ["name", "phone", "note"]
        widgets = {"name": forms.TextInput(attrs={"data-mask": "name"}),
                   "note": forms.Textarea(attrs={"rows": 3})}


class SettingsForm(HandleRules, ImageRules, forms.ModelForm):
    phone = PhoneField(label="Telefon", required=False)
    phone2 = PhoneField(label="Qo'shimcha telefon", required=False)

    class Meta:
        model = SiteSettings
        fields = ["name", "logo", "tagline_uz", "tagline_ru", "tagline_en", "phone", "phone2",
                  "telegram", "instagram", "booking_days_ahead", "tg_bot_token", "tg_chat_id",
                  "address_uz", "address_ru", "address_en", "latitude", "longitude"]
        widgets = {"latitude": forms.TextInput(attrs={"id": "id_latitude"}),
                   "longitude": forms.TextInput(attrs={"id": "id_longitude"}),
                   "tg_bot_token": forms.PasswordInput(render_value=True, attrs={"autocomplete": "off"})}
        help_texts = {"tg_bot_token": "Yangi navbat xabarlari uchun, @BotFather beradi. Bo'sh qolsa, xabar yuborilmaydi.",
                      "tg_chat_id": "Xabar boradigan chat raqami."}


class AppointmentForm(forms.ModelForm):
    phone = PhoneField(label="Telefon")
    name = forms.CharField(label="Mijoz ismi", max_length=100,
                           widget=forms.TextInput(attrs={"data-mask": "name"}))
    price = MoneyField(label="Narx (so'm)", required=False, min_value=0)

    class Meta:
        model = Appointment
        fields = ["service", "doctor", "date", "time", "status", "price", "note"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
                   "time": TimeMaskInput()}

    def __init__(self, *args, own_doctor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(["phone", "name", "service", "doctor", "date", "time", "status", "price", "note"])
        if own_doctor:
            self.fields["doctor"].queryset = Doctor.objects.filter(pk=own_doctor.pk)
            self.fields["doctor"].initial = own_doctor.pk
            self.initial["doctor"] = own_doctor.pk
            self.fields["doctor"].widget = forms.HiddenInput()
            self.fields["service"].queryset = own_doctor.services.all()
        if self.instance.pk:
            self.fields["phone"].initial = self.instance.client.phone
            self.fields["name"].initial = self.instance.client.name

    def clean(self):
        cleaned = super().clean()
        doctor, day, hour = cleaned.get("doctor"), cleaned.get("date"), cleaned.get("time")
        if hour and (hour.minute or hour.second):
            self.add_error("time", "Navbat faqat to'liq soatda bo'ladi, masalan 14:00.")
        if doctor and day and hour and cleaned.get("status") != Appointment.Status.CANCELLED:
            clash = (Appointment.objects.filter(doctor=doctor, date=day, time=hour)
                     .exclude(status=Appointment.Status.CANCELLED).exclude(pk=self.instance.pk))
            if clash.exists():
                self.add_error("time", "Bu soatda mutaxassisda boshqa mijoz bor.")
        if cleaned.get("price") is None and cleaned.get("service"):
            cleaned["price"] = cleaned["service"].price
        return cleaned

    def save(self, commit=True):
        phone, name = self.cleaned_data["phone"], self.cleaned_data["name"].strip()
        client, _ = Client.objects.get_or_create(phone=phone, defaults={"name": name})
        if client.name != name:
            client.name = name
            client.save()
        self.instance.client = client
        if not self.instance.pk:
            self.instance.source = Appointment.Source.PANEL
        return super().save(commit)


class ReportFilter(forms.Form):
    date = forms.DateField(required=False)


def today():
    return now_local().date()
