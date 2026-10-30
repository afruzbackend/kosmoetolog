import json
import re
import tempfile
from datetime import time, timedelta
from io import BytesIO, StringIO
from unittest import mock

from PIL import Image
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import Client as HttpClient, RequestFactory, TestCase
from django.urls import reverse

from . import errors
from .booking import BookingError, book, day_slots, format_phone, normalize_phone, now_local
from .models import Appointment, Banner, Category, Client, Doctor, Service, SiteSettings, TimeBlock
from .search import normalize, search_services


def next_workday(offset=1):
    day = now_local().date() + timedelta(days=offset)
    while day.weekday() == 6:
        day += timedelta(days=1)
    return day


class Base(TestCase):
    def setUp(self):
        cache.clear()
        self.cat = Category.objects.create(name_uz="Yuz", name_ru="Лицо", name_en="Face")
        self.d1 = Doctor.objects.create(name_uz="Dr. A", specialty_uz="Kosmetolog")
        self.d2 = Doctor.objects.create(name_uz="Dr. B", specialty_uz="Hijoma")
        self.s1 = Service.objects.create(category=self.cat, name_uz="Mezoterapiya", name_ru="Мезотерапия",
                                         name_en="Mesotherapy", price=350000)
        self.s2 = Service.objects.create(category=self.cat, name_uz="Hijoma", name_ru="Хиджама",
                                         name_en="Hijama", price=200000, keywords="cupping")
        self.s1.doctors.add(self.d1, self.d2)
        self.s2.doctors.add(self.d2)
        self.day = next_workday()

    def book(self, doctor=None, hour=time(10, 0), phone="+998 90 123 45 67", service=None):
        return book(service=service or self.s1, doctor=doctor or self.d1, day=self.day, hour=hour,
                    name="Aziza", phone=phone)


class BookingTests(Base):
    def test_one_client_per_hour_per_doctor(self):
        self.book()
        with self.assertRaises(BookingError) as ctx:
            self.book(phone="+998 91 111 22 33")
        self.assertEqual(ctx.exception.code, "slot_taken")

    def test_doctors_have_separate_queues(self):
        self.book(doctor=self.d1)
        self.book(doctor=self.d2, phone="+998 91 111 22 33")
        self.assertEqual(Appointment.objects.count(), 2)

    def test_database_blocks_double_booking(self):
        first = self.book()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appointment.objects.create(client=first.client, doctor=first.doctor, service=first.service,
                                       date=first.date, time=first.time)

    def test_cancelled_slot_becomes_free(self):
        appointment = self.book()
        appointment.status = Appointment.Status.CANCELLED
        appointment.save()
        self.book(phone="+998 91 111 22 33")

    def test_lunch_and_day_off_excluded(self):
        times = [s["time"] for s in day_slots(self.d1, self.day)]
        self.assertNotIn("13:00", times)
        self.assertEqual(times[0], "09:00")
        self.assertEqual(times[-1], "17:00")
        TimeBlock.objects.create(date=self.day)
        self.assertEqual(day_slots(self.d1, self.day), [])

    def test_blocked_hour(self):
        TimeBlock.objects.create(date=self.day, doctor=self.d1, time=time(10, 0))
        with self.assertRaises(BookingError):
            self.book()
        self.book(doctor=self.d2)

    def test_doctor_must_perform_service(self):
        with self.assertRaises(BookingError) as ctx:
            self.book(doctor=self.d1, service=self.s2)
        self.assertEqual(ctx.exception.code, "bad_doctor")

    def test_limit_per_phone(self):
        for hour in (9, 10, 11):
            self.book(hour=time(hour, 0))
        with self.assertRaises(BookingError) as ctx:
            self.book(hour=time(12, 0))
        self.assertEqual(ctx.exception.code, "too_many")

    def test_past_hours_not_bookable(self):
        yesterday = now_local().date() - timedelta(days=1)
        self.assertFalse(any(s["free"] for s in day_slots(self.d1, yesterday)))

    def test_phone_format(self):
        self.assertEqual(normalize_phone("+998 50 000 00 00"), "998500000000")
        self.assertEqual(normalize_phone("50 000 00 00"), "998500000000")
        self.assertEqual(normalize_phone("+998 50"), "")
        self.assertEqual(format_phone("998500000000"), "+998 50 000 00 00")


class SearchTests(Base):
    def test_equal_spelling(self):
        self.assertEqual(normalize("Хиджама")[:2], normalize("hijama")[:2])

    def test_finds_across_languages_and_typos(self):
        for query in ("hijoma", "xijoma", "хиджама", "hijama", "cupping", "ХИДЖАМА"):
            self.assertIn(self.s2, search_services(query), query)
        for query in ("mezoterapiya", "мезотерапия", "mesotherapy", "mezoterpiya", "mezaterpiy"):
            self.assertIn(self.s1, search_services(query), query)

    def test_no_false_match(self):
        self.assertEqual(search_services("velosiped"), [])


class SeedTests(TestCase):
    def test_seed_creates_real_profile(self):
        call_command("seed", verbosity=0, stdout=StringIO())
        site = SiteSettings.load()
        self.assertEqual(site.phone, "998935145177")
        doctor = Doctor.objects.first()
        self.assertEqual(doctor.experience, 16)
        self.assertIn("saragul.jpg", doctor.image_url)
        self.assertEqual(Doctor.objects.count(), 1)
        self.assertEqual(doctor.services.count(), 10)
        self.assertFalse(Service.objects.exclude(old_price=None).exists())
        self.assertIn("/photos/", Category.objects.first().image_url)
        self.assertEqual(self.client.get("/").status_code, 200)


class DemoTests(Base):
    def test_demo_adds_and_clears_only_samples(self):
        real = self.book()
        call_command("demo", stdout=StringIO())
        self.assertGreater(Appointment.objects.count(), 50)
        self.assertEqual(Client.objects.filter(note__startswith="Namuna").count(), 14)
        call_command("demo", stdout=StringIO())  # qayta ishga tushirilsa, ikkilanmaydi
        self.assertEqual(Client.objects.filter(note__startswith="Namuna").count(), 14)
        call_command("demo", "--clear", stdout=StringIO())
        self.assertEqual(list(Appointment.objects.all()), [real])
        self.assertEqual(Client.objects.count(), 1)


class PublicViewTests(Base):
    def test_pages_render_in_three_languages(self):
        paths = ["/", "/xizmatlar/", f"/xizmat/{self.s1.id}/", f"/shifokor/{self.d1.id}/", "/navbat/", "/navbatim/"]
        for lang in ("uz", "ru", "en"):
            self.client.cookies["lang"] = lang
            for path in paths:
                self.assertEqual(self.client.get(path).status_code, 200, (lang, path))
        self.client.cookies["lang"] = "ru"
        self.assertContains(self.client.get("/xizmatlar/"), "Мезотерапия")

    def test_login_button_is_visible_in_all_languages(self):
        for lang, label in (("uz", "Kirish"), ("ru", "Войти"), ("en", "Log in")):
            self.client.cookies["lang"] = lang
            page = self.client.get("/")
            self.assertContains(page, 'class="login-btn"')
            self.assertContains(page, label)
            self.assertContains(page, 'href="/panel/"')

    def test_css_and_js_links_are_versioned(self):
        for page in (self.client.get("/"), self.client.get(reverse("panel:login"))):
            html = page.content.decode()
            links = re.findall(r'(?:href|src)="(/static/(?:css|js)/[^"]+)"', html)
            self.assertTrue(links)
            for link in links:
                self.assertRegex(link, r"\?v=[1-9]\d+$")

    def test_language_redirect_is_safe(self):
        response = self.client.get("/til/ru/?next=https://evil.example/")
        self.assertEqual(response["Location"], "/")
        self.assertEqual(response.cookies["lang"].value, "ru")

    def test_catalog_filters(self):
        response = self.client.get("/xizmatlar/", {"max": "250 000"})
        self.assertEqual(response.context["services"], [self.s2])
        response = self.client.get("/xizmatlar/", {"sort": "cheap"})
        self.assertEqual(response.context["services"][0], self.s2)

    def payload(self, **extra):
        return {"service": self.s1.id, "doctor": self.d1.id, "date": self.day.isoformat(), "time": "10:00",
                "name": "Aziza", "phone": "+998 90 123 45 67", **extra}

    def post_book(self, **extra):
        return self.client.post("/api/book/", json.dumps(self.payload(**extra)), content_type="application/json")

    def test_book_api_and_lookup_cancel(self):
        response = self.post_book()
        self.assertEqual(response.status_code, 200)
        code = response.json()["code"]
        self.assertEqual(self.post_book(phone="+998 91 000 00 00").status_code, 409)

        found = self.client.post("/navbatim/", {"phone": "+998 90 123 45 67", "code": code})
        self.assertEqual(found.context["found"].code, code)
        wrong = self.client.post("/navbatim/", {"phone": "+998 91 111 11 11", "code": code})
        self.assertIsNone(wrong.context["found"])

        self.client.post("/navbatim/", {"phone": "998901234567", "code": code, "action": "cancel"})
        self.assertEqual(Appointment.objects.get().status, Appointment.Status.CANCELLED)

    def test_honeypot_blocks_bots(self):
        self.assertEqual(self.post_book(website="spam").status_code, 400)
        self.assertEqual(Appointment.objects.count(), 0)

    def test_bad_phone_rejected(self):
        self.assertEqual(self.post_book(phone="+998 90").status_code, 409)

    def test_slots_api(self):
        self.book()
        slots = self.client.get("/api/slots/", {"doctor": self.d1.id, "date": self.day.isoformat()}).json()["slots"]
        ten = next(s for s in slots if s["time"] == "10:00")
        self.assertFalse(ten["free"])


class RoleTests(Base):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.main = User.objects.create_superuser("glavniy", password="pass-for-tests-1")
        self.account = User.objects.create_user("doktor", password="pass-for-tests-2", is_staff=True)
        self.d1.user = self.account
        self.d1.save()
        self.mine = self.book(doctor=self.d1)
        self.other = self.book(doctor=self.d2, phone="+998 91 111 22 33")

    def test_doctor_login_works_and_inactive_is_blocked(self):
        response = self.client.post(reverse("panel:login"), {"username": "doktor", "password": "pass-for-tests-2"})
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        self.d1.is_active = False
        self.d1.save()
        response = self.client.post(reverse("panel:login"), {"username": "doktor", "password": "pass-for-tests-2"})
        self.assertEqual(response.status_code, 200)

    def test_account_without_profile_cannot_enter(self):
        get_user_model().objects.create_user("begona", password="pass-for-tests-3", is_staff=True)
        response = self.client.post(reverse("panel:login"), {"username": "begona", "password": "pass-for-tests-3"})
        self.assertEqual(response.status_code, 200)

    def test_doctor_sees_only_own_data(self):
        self.client.force_login(self.account)
        rows = self.client.get(reverse("panel:appointments")).context["page"].object_list
        self.assertEqual(list(rows), [self.mine])
        clients = self.client.get(reverse("panel:clients")).context["page"].object_list
        self.assertEqual([c.pk for c in clients], [self.mine.client_id])
        doctors = self.client.get(reverse("panel:calendar"), {"date": self.day.isoformat()}).context["doctors"]
        self.assertEqual(doctors, [self.d1])

    def test_doctor_cannot_touch_other_doctor(self):
        self.client.force_login(self.account)
        self.assertEqual(self.client.get(reverse("panel:appointment", args=[self.other.id])).status_code, 404)
        url = reverse("panel:appointment_status", args=[self.other.id])
        self.assertEqual(self.client.post(url, {"status": "cancelled"}).status_code, 404)
        self.assertEqual(self.client.get(reverse("panel:client", args=[self.other.client_id])).status_code, 404)
        self.other.refresh_from_db()
        self.assertEqual(self.other.status, "new")

    def test_doctor_cannot_book_for_other_doctor(self):
        self.client.force_login(self.account)
        data = {"phone": "+998 93 000 11 22", "name": "Malika", "service": self.s1.id, "doctor": self.d2.id,
                "date": self.day.isoformat(), "time": "15:00", "status": "confirmed"}
        self.assertEqual(self.client.post(reverse("panel:appointment_new"), data).status_code, 200)
        self.assertFalse(Appointment.objects.filter(time=time(15, 0)).exists())
        data["doctor"] = self.d1.id
        self.assertEqual(self.client.post(reverse("panel:appointment_new"), data).status_code, 302)

    def test_main_sections_are_closed_for_doctor(self):
        self.client.force_login(self.account)
        for url in (reverse("panel:settings"), reverse("panel:crud", args=["xizmatlar"]),
                    reverse("panel:crud_new", args=["shifokorlar"]), reverse("panel:crud_edit", args=["shifokorlar", self.d1.id])):
            self.assertRedirects(self.client.get(url), reverse("panel:dashboard"))
        self.assertEqual(self.client.post(reverse("panel:crud_delete", args=["xizmatlar", self.s1.id])).status_code, 302)
        self.assertTrue(Service.objects.filter(pk=self.s1.id).exists())

    def test_report_is_scoped(self):
        for appointment in (self.mine, self.other):
            appointment.status = "done"
            appointment.save()
        self.client.force_login(self.account)
        summary = self.client.get(reverse("panel:report"), {"from": self.day.isoformat()}).context["summary"]
        self.assertEqual(summary["revenue"], self.mine.price)
        self.client.force_login(self.main)
        summary = self.client.get(reverse("panel:report"), {"from": self.day.isoformat()}).context["summary"]
        self.assertEqual(summary["revenue"], self.mine.price + self.other.price)

    def test_profile_edit_keeps_admin_fields(self):
        self.client.force_login(self.account)
        data = {"name_uz": "Yangi Ism", "specialty_uz": "Kosmetolog", "experience": 3, "work_start": "09:00",
                "work_end": "18:00", "days": ["0"], "phone": "+998 93 514 51 77", "telegram": "https://t.me/sora/",
                "instagram": "@sora", "is_active": "", "order": 9, "login_username": "buzuq"}
        self.assertEqual(self.client.post(reverse("panel:profile"), data).status_code, 302)
        self.d1.refresh_from_db()
        self.account.refresh_from_db()
        self.assertEqual((self.d1.name_uz, self.d1.telegram, self.d1.instagram), ("Yangi Ism", "sora", "sora"))
        self.assertEqual(self.d1.phone, "998935145177")
        self.assertTrue(self.d1.is_active)
        self.assertEqual(self.account.username, "doktor")

    def base_data(self, **extra):
        return {"name_uz": "Yangi Mutaxassis", "specialty_uz": "Kosmetolog", "experience": 2, "work_start": "09:00",
                "work_end": "18:00", "days": ["0", "1"], "is_active": "on", "order": 3, **extra}

    def test_main_creates_specialist_with_login_and_photos(self):
        self.client.force_login(self.main)
        def image(name):
            buffer = BytesIO()
            Image.new("RGB", (20, 20), "#E0117F").save(buffer, "PNG")
            return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")
        data = self.base_data(login_username="nigora", login_password="Yaxshi-parol-5", phone="+998 90 111 22 33",
                              telegram="nigora", instagram="https://instagram.com/nigora/", photo=image("a.png"),
                              photo2=image("b.png"))
        with self.settings(MEDIA_ROOT=tempfile.mkdtemp()):
            self.assertEqual(self.client.post(reverse("panel:crud_new", args=["shifokorlar"]), data).status_code, 302)
            doctor = Doctor.objects.get(name_uz="Yangi Mutaxassis")
            self.assertTrue(doctor.photo and doctor.photo2)
            self.assertIn("/media/doctors/", doctor.photo2_url)
            self.assertEqual(doctor.instagram, "nigora")
            self.client.logout()
            login = {"username": "nigora", "password": "Yaxshi-parol-5"}
            self.assertEqual(self.client.post(reverse("panel:login"), login).status_code, 302)
            self.assertEqual(self.client.get(reverse("panel:profile")).status_code, 200)

    def test_login_rules_in_specialist_form(self):
        self.client.force_login(self.main)
        url = reverse("panel:crud_new", args=["shifokorlar"])
        self.assertContains(self.client.post(url, self.base_data(login_username="doktor", login_password="Yaxshi-parol-5")), "Bu login band")
        self.assertContains(self.client.post(url, self.base_data(login_username="yangi")), "parol kiriting")
        self.assertContains(self.client.post(url, self.base_data(login_password="Yaxshi-parol-5")), "login kiriting")

    def test_deleting_specialist_removes_login(self):
        self.client.force_login(self.main)
        Appointment.objects.filter(doctor=self.d1).delete()
        self.client.post(reverse("panel:crud_delete", args=["shifokorlar", self.d1.id]))
        self.assertFalse(get_user_model().objects.filter(username="doktor").exists())

    def test_public_shows_specialist_contacts_and_logos(self):
        self.d1.phone, self.d1.telegram, self.d1.instagram = "998935145177", "sora", "saragul"
        self.d1.save()
        page = self.client.get(f"/shifokor/{self.d1.id}/")
        self.assertContains(page, "https://t.me/sora")
        self.assertContains(page, "img/brands/instagram.svg")


class ErrorPageTests(Base):
    def test_404_in_three_languages(self):
        for lang, title in (("uz", "Sahifa topilmadi"), ("ru", "Страница не найдена"), ("en", "Page not found")):
            self.client.cookies["lang"] = lang
            page = self.client.get("/yoq-sahifa/")
            self.assertContains(page, title, status_code=404)

    def test_panel_404_returns_to_panel(self):
        page = self.client.get("/panel/yoq/")
        self.assertContains(page, "Panelga qaytish", status_code=404)
        self.assertContains(page, 'href="/panel/"', status_code=404)

    def test_unknown_host_shows_400_page(self):
        page = self.client.get("/", HTTP_HOST="evil.example")
        self.assertContains(page, "So‘rov noto‘g‘ri", status_code=400)

    def test_csrf_failure_page(self):
        client = HttpClient(enforce_csrf_checks=True)
        page = client.post(reverse("panel:login"), {"username": "a", "password": "b"})
        self.assertContains(page, "Sahifa eskirgan", status_code=403)
        self.assertContains(page, "Sahifani yangilash", status_code=403)

    def test_permission_denied_page(self):
        response = errors.permission_denied(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 403)
        self.assertIn("Ruxsat yo‘q", response.content.decode())

    def test_server_error_page_when_view_crashes(self):
        client = HttpClient(raise_request_exception=False)
        with mock.patch("clinic.views.search_services", side_effect=RuntimeError("buzildi")):
            page = client.get("/xizmatlar/", {"q": "a"})
        self.assertContains(page, "Serverda xatolik", status_code=500)
        self.assertNotContains(page, "buzildi", status_code=500)

    def test_server_error_page_survives_broken_database(self):
        with mock.patch("clinic.errors.SiteSettings.load", side_effect=RuntimeError("baza yo'q")):
            response = errors.server_error(RequestFactory().get("/"))
        html = response.content.decode()
        self.assertEqual(response.status_code, 500)
        self.assertIn("Saragul Ahmedovna", html)
        self.assertNotIn("tel:+", html)

    def test_dev_not_found_keeps_slash_redirect(self):
        factory = RequestFactory()
        self.assertContains(errors.dev_not_found(factory.get("/ansfdoinfgs")), "Sahifa topilmadi", status_code=404)
        response = errors.dev_not_found(factory.get("/navbat", {"service": "1"}))
        self.assertEqual((response.status_code, response["Location"]), (302, "/navbat/?service=1"))

    def test_error_page_has_no_static_dependency(self):
        html = self.client.get("/yoq-sahifa/").content.decode()
        self.assertNotIn("/static/", html)
        self.assertIn("<style>", html)


class PanelTests(Base):
    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_superuser("boss", password="pass-for-tests-1")

    def login(self):
        self.client.force_login(self.user)

    def test_panel_requires_login(self):
        for name in ("dashboard", "calendar", "appointments", "clients", "report", "settings"):
            response = self.client.get(reverse(f"panel:{name}"))
            self.assertEqual(response.status_code, 302, name)

    def test_login_lockout(self):
        for _ in range(5):
            self.client.post(reverse("panel:login"), {"username": "boss", "password": "bad"})
        response = self.client.post(reverse("panel:login"), {"username": "boss", "password": "pass-for-tests-1"})
        self.assertContains(response, "Urinishlar ko")

    def test_all_pages_open(self):
        self.login()
        appointment = self.book()
        names = ["dashboard", "calendar", "appointments", "clients", "report", "settings", "appointment_new"]
        for name in names:
            self.assertEqual(self.client.get(reverse(f"panel:{name}")).status_code, 200, name)
        self.assertEqual(self.client.get(reverse("panel:appointment", args=[appointment.id])).status_code, 200)
        self.assertEqual(self.client.get(reverse("panel:client", args=[appointment.client_id])).status_code, 200)
        for slug in ("shifokorlar", "xizmatlar", "kategoriyalar", "bannerlar", "sharhlar", "dam-olish"):
            self.assertEqual(self.client.get(reverse("panel:crud", args=[slug])).status_code, 200, slug)
            self.assertEqual(self.client.get(reverse("panel:crud_new", args=[slug])).status_code, 200, slug)
        self.assertEqual(self.client.get(reverse("panel:crud_edit", args=["shifokorlar", self.d1.id])).status_code, 200)

    def test_panel_booking_blocks_conflict(self):
        self.login()
        self.book()
        data = {"phone": "+998 93 000 11 22", "name": "Malika", "service": self.s1.id, "doctor": self.d1.id,
                "date": self.day.isoformat(), "time": "10:00", "status": "confirmed", "price": "350 000"}
        response = self.client.post(reverse("panel:appointment_new"), data)
        self.assertContains(response, "boshqa mijoz bor")
        data["time"] = "11:00"
        self.assertEqual(self.client.post(reverse("panel:appointment_new"), data).status_code, 302)
        created = Appointment.objects.get(time=time(11, 0))
        self.assertEqual(created.price, 350000)
        self.assertEqual(created.client.phone, "998930001122")

    def test_status_and_report(self):
        self.login()
        appointment = self.book()
        self.client.post(reverse("panel:appointment_status", args=[appointment.id]), {"status": "done"})
        response = self.client.get(reverse("panel:report"), {"from": self.day.isoformat()})
        self.assertEqual(response.context["summary"]["revenue"], 350000)
        excel = self.client.get(reverse("panel:report_excel"), {"from": self.day.isoformat()})
        self.assertEqual(excel.status_code, 200)
        self.assertTrue(excel.content.startswith(b"PK"))

    def test_client_search_cyrillic(self):
        self.login()
        client = Client.objects.create(name="Азиза Юсупова", phone="998901112233")
        response = self.client.get(reverse("panel:clients"), {"q": "азиза"})
        self.assertIn(client, list(response.context["page"].object_list))

    def test_settings_save_phone_mask(self):
        self.login()
        data = {"name": "Nafis", "phone": "+998 50 000 00 00", "latitude": "41.300000", "longitude": "69.250000",
                "booking_days_ahead": 30}
        response = self.client.post(reverse("panel:settings"), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(SiteSettings.load().phone, "998500000000")

    def test_rejects_non_image_upload(self):
        self.login()
        banner = Banner.objects.create(title_uz="A")
        upload = SimpleUploadedFile("x.svg", b"<svg onload=alert(1)>", content_type="image/svg+xml")
        data = {"title_uz": "A", "image": upload, "link": "/navbat/", "order": 0}
        response = self.client.post(reverse("panel:crud_edit", args=["bannerlar", banner.id]), data)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Banner.objects.get().image)

    def test_doctor_form_saves_days_and_hours(self):
        self.login()
        data = {"name_uz": "Dr. A", "specialty_uz": "Kosmetolog", "experience": 5, "work_start": "10:00",
                "work_end": "16:00", "days": ["0", "2"], "is_active": "on", "order": 0}
        response = self.client.post(reverse("panel:crud_edit", args=["shifokorlar", self.d1.id]), data)
        self.assertEqual(response.status_code, 302)
        self.d1.refresh_from_db()
        self.assertEqual(self.d1.work_day_set, {0, 2})
        self.assertEqual(self.d1.work_start, time(10, 0))

    def test_service_form_money_mask(self):
        self.login()
        data = {"name_uz": "Yangi", "category": self.cat.id, "price": "1 250 000", "doctors": [self.d1.id],
                "order": 0, "is_active": "on"}
        self.assertEqual(self.client.post(reverse("panel:crud_new", args=["xizmatlar"]), data).status_code, 302)
        self.assertEqual(Service.objects.get(name_uz="Yangi").price, 1250000)

    def test_review_form_and_home_section(self):
        self.login()
        data = {"author": "Aziza", "text": "Rahmat", "rating": "4", "is_active": "on"}
        self.assertEqual(self.client.post(reverse("panel:crud_new", args=["sharhlar"]), data).status_code, 302)
        self.assertContains(self.client.get("/"), "Rahmat")

    def test_category_form_and_block_form(self):
        self.login()
        data = {"name_uz": "Tana", "order": 1}
        self.assertEqual(self.client.post(reverse("panel:crud_new", args=["kategoriyalar"]), data).status_code, 302)
        data = {"date": self.day.isoformat(), "reason": "Bayram"}
        self.assertEqual(self.client.post(reverse("panel:crud_new", args=["dam-olish"]), data).status_code, 302)
        self.assertEqual(day_slots(self.d1, self.day), [])

    def test_password_change(self):
        self.login()
        data = {"form": "password", "old_password": "pass-for-tests-1", "new_password1": "Yangi-parol-77",
                "new_password2": "Yangi-parol-77"}
        self.assertEqual(self.client.post(reverse("panel:settings"), data).status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Yangi-parol-77"))

    def test_image_replace_and_restore(self):
        self.login()
        banner = Banner.objects.create(title_uz="A", default_image="img/banners/banner1.svg")
        buffer = BytesIO()
        Image.new("RGB", (40, 20), "#E0117F").save(buffer, "PNG")
        upload = SimpleUploadedFile("yangi.png", buffer.getvalue(), content_type="image/png")
        data = {"title_uz": "A", "image": upload, "link": "/navbat/", "order": 0, "is_active": "on"}
        with self.settings(MEDIA_ROOT=tempfile.mkdtemp()):
            url = reverse("panel:crud_edit", args=["bannerlar", banner.id])
            self.assertEqual(self.client.post(url, data).status_code, 302)
            banner.refresh_from_db()
            self.assertIn("/media/banners/", banner.image_url)
            self.assertContains(self.client.get("/"), "/media/banners/")
            data = {"title_uz": "A", "image-clear": "on", "link": "/navbat/", "order": 0, "is_active": "on"}
            self.assertEqual(self.client.post(url, data).status_code, 302)
            banner.refresh_from_db()
            self.assertIn("banner1.svg", banner.image_url)

    def test_delete_protected_doctor_shows_message(self):
        self.login()
        self.book()
        response = self.client.post(reverse("panel:crud_delete", args=["shifokorlar", self.d1.id]), follow=True)
        self.assertContains(response, "bog")
        self.assertTrue(Doctor.objects.filter(pk=self.d1.id).exists())
