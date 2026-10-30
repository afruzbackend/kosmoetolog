"""Boshlang'ich ma'lumotlar. Bosh admin paroli ADMIN_PASSWORD yoki tasodifiy yaratiladi."""
import os
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from clinic.models import Banner, Category, Doctor, Service, SiteSettings

ADMIN_USERNAME = "glavniy"

SITE = {
    "name": "Saragul Ahmedovna",
    "phone": "998935145177",
    "tagline_uz": "Tibbiy ma’lumotli kosmetolog, 16 yillik tajriba",
    "tagline_ru": "Косметолог с медицинским образованием, стаж 16 лет",
    "tagline_en": "Cosmetologist with a medical education, 16 years of experience",
    "address_uz": "Toshkent, Chilonzor 7-kvartal, 25-uy, «Shedevr» saloni",
    "address_ru": "Ташкент, Чилонзор 7-квартал, дом 25, салон «Шедевр»",
    "address_en": "Shedevr salon, 25 Chilonzor 7th quarter, Tashkent",
    "latitude": "41.298452",
    "longitude": "69.212104",
    "instagram": "saragulahmedovna",
    "telegram": "sora_kosmetolog",
}

CATEGORIES = [
    ("face", "Yuz parvarishi", "Уход за лицом", "Facial care", "oxy"),
    ("inject", "Inyeksion muolajalar", "Инъекционные процедуры", "Injectables", "bio"),
    ("hijama", "An’anaviy tibbiyot", "Традиционная медицина", "Traditional medicine", "hijama"),
    ("body", "Tana va relaks", "Тело и релакс", "Body & relax", "massage"),
]

SERVICES = [
    {"key": "meso", "cat": "inject", "price": 350000, "old": None, "popular": True,
     "uz": ("Mezoterapiya", "Terini namlantirish va yangilash"), "ru": ("Мезотерапия", "Увлажнение и обновление кожи"), "en": ("Mesotherapy", "Hydrates and renews the skin"),
     "keywords": "meso, mezo, vitamin, namlik, увлажнение", "desc": ("Vitamin va gialuron kislotasi kokteyllari terining o‘rta qatlamiga mikroinyeksiya orqali yuboriladi. Teri tiniqlashadi, namlik qaytadi.", "Витаминные и гиалуроновые коктейли вводятся в средний слой кожи микроинъекциями. Кожа становится чище и увлажнённее.", "Vitamin and hyaluronic cocktails are delivered into the mid-layer of the skin by micro-injections. Skin looks clearer and more hydrated.")},
    {"key": "bio", "cat": "inject", "price": 650000, "old": None, "popular": True,
     "uz": ("Biorevitalizatsiya", "Chuqur namlik va elastiklik"), "ru": ("Биоревитализация", "Глубокое увлажнение и упругость"), "en": ("Biorevitalization", "Deep hydration and elasticity"),
     "keywords": "gialuron, hyaluron, ajin, морщины", "desc": ("Gialuron kislotasi asosidagi muolaja teri elastikligini tiklaydi va mayda ajinlarni kamaytiradi.", "Процедура на основе гиалуроновой кислоты возвращает упругость и уменьшает мелкие морщины.", "A hyaluronic acid treatment that restores elasticity and softens fine lines.")},
    {"key": "plasma", "cat": "inject", "price": 500000, "old": None, "popular": False,
     "uz": ("Plazmolifting", "O‘z plazmangiz bilan yoshartirish"), "ru": ("Плазмолифтинг", "Омоложение собственной плазмой"), "en": ("Plasma lifting", "Rejuvenation with your own plasma"),
     "keywords": "plazma, prp, soch, волосы", "desc": ("Qondan olingan plazma teriga yuboriladi va tiklanish jarayonlarini faollashtiradi.", "Плазма из крови вводится в кожу и запускает процессы восстановления.", "Plasma from your blood is injected into the skin to activate natural repair.")},
    {"key": "clean", "cat": "face", "price": 250000, "old": None, "popular": True,
     "uz": ("Yuz chistkasi", "Chuqur tozalash va parvarish"), "ru": ("Чистка лица", "Глубокое очищение и уход"), "en": ("Facial cleansing", "Deep cleansing and care"),
     "keywords": "chistka, tozalash, akne, husnbuzar, ugri, чистка, прыщи, acne", "desc": ("Teri poralari tozalanadi, qora nuqtalar olib tashlanadi, tinchlantiruvchi niqob bilan yakunlanadi.", "Поры очищаются, удаляются чёрные точки, в конце успокаивающая маска.", "Pores are cleansed, blackheads removed, and the visit ends with a calming mask.")},
    {"key": "peel", "cat": "face", "price": 300000, "old": None, "popular": True,
     "uz": ("Kimyoviy piling", "Teri rangini tekislash"), "ru": ("Химический пилинг", "Выравнивание тона кожи"), "en": ("Chemical peel", "Evens out skin tone"),
     "keywords": "piling, peeling, pigment, dog, пятна", "desc": ("Meva kislotalari yordamida terining yuqori qatlami yangilanadi, dog‘lar yengillashadi.", "Фруктовые кислоты обновляют верхний слой кожи и осветляют пятна.", "Fruit acids renew the top layer of the skin and lighten marks.")},
    {"key": "oxy", "cat": "face", "price": 280000, "old": None, "popular": True,
     "uz": ("Kislorodli parvarish", "Teriga yangi nafas"), "ru": ("Кислородный уход", "Свежее дыхание для кожи"), "en": ("Oxygen facial", "Fresh breath for your skin"),
     "keywords": "kislorod, oxygen, кислород", "desc": ("Kislorod va faol moddalar teriga kiritiladi, charchagan teri tetiklashadi.", "Кислород и активные вещества насыщают кожу и снимают усталость.", "Oxygen and actives infuse the skin and refresh a tired look.")},
    {"key": "mask", "cat": "face", "price": 150000, "old": None, "popular": False,
     "uz": ("Alginat niqob", "Tinchlantirish va tortish"), "ru": ("Альгинатная маска", "Успокоение и лифтинг"), "en": ("Alginate mask", "Calming and lifting"),
     "keywords": "niqob, maska, маска, mask", "desc": ("Dengiz o‘tlari asosidagi niqob terini tinchlantiradi va yumshoq tortish effektini beradi.", "Маска на основе водорослей успокаивает кожу и даёт мягкий лифтинг.", "A seaweed-based mask that calms the skin and gives a gentle lift.")},
    {"key": "hijama", "cat": "hijama", "price": 200000, "old": None, "popular": True,
     "uz": ("Hijoma", "An’anaviy qon olish muolajasi"), "ru": ("Хиджама", "Традиционное кровопускание"), "en": ("Hijama", "Traditional cupping therapy"),
     "keywords": "hijoma, xijoma, hijama, cupping, банки, kupa", "desc": ("Maxsus bankalar yordamida bajariladigan an’anaviy muolaja. Bir martalik steril asboblar ishlatiladi.", "Традиционная процедура со специальными банками. Используются одноразовые стерильные инструменты.", "A traditional treatment with special cups, using single-use sterile instruments.")},
    {"key": "hijama2", "cat": "hijama", "price": 260000, "old": None, "popular": True,
     "uz": ("Bel va bo‘yin hijomasi", "Yelka, bo‘yin va bel sohasi"), "ru": ("Хиджама спины и шеи", "Плечи, шея и поясница"), "en": ("Back & neck hijama", "Shoulders, neck and lower back"),
     "keywords": "bel, boyin, yelka, спина, шея, back", "desc": ("Bel, bo‘yin va yelka sohasiga mo‘ljallangan hijoma muolajasi.", "Хиджама для зоны спины, шеи и плеч.", "Hijama focused on the back, neck and shoulders.")},
    {"key": "massage", "cat": "body", "price": 180000, "old": None, "popular": True,
     "uz": ("Yuz massaji", "Limfa drenaj va bo‘shashish"), "ru": ("Массаж лица", "Лимфодренаж и расслабление"), "en": ("Facial massage", "Lymph drainage and relaxation"),
     "keywords": "massaj, массаж, massage, relaks", "desc": ("Yuz va bo‘yin massaji shishlarni kamaytiradi, mushaklarni bo‘shashtiradi.", "Массаж лица и шеи снимает отёки и расслабляет мышцы.", "A face and neck massage that reduces puffiness and relaxes the muscles.")},
]

DOCTORS = [
    {"key": "saragul", "image": "img/photos/saragul.jpg", "image2": "img/photos/saragul2.jpg", "exp": 16,
     "name": ("Saragul Ahmedovna", "Сарагуль Ахмедовна", "Saragul Ahmedovna"),
     "spec": ("Tibbiy ma’lumotli kosmetolog", "Косметолог с медицинским образованием", "Cosmetologist with a medical education"),
     "bio": ("Kosmetolog va plastik jarroh assistenti, 16 yillik tajribaga ega. Kosmetologiyaning barcha xizmatlarini bajaradi.",
             "Косметолог и ассистент пластического хирурга со стажем 16 лет. Проводит все услуги косметологии.",
             "A cosmetologist and plastic surgeon’s assistant with 16 years of experience, offering all cosmetology services.")},
]

BANNERS = [
    ("img/photos/banner1.jpg", "", ("Mezoterapiya", "Мезотерапия", "Mesotherapy"),
     ("Har bir qabul bir soat, faqat siz uchun", "Каждый приём — час только для вас", "Each visit is one hour, just for you")),
    ("img/photos/banner2.jpg", "", ("Yuz chistkasi va parvarish", "Чистка и уход за лицом", "Facial cleansing and care"),
     ("Tiniq teri uchun professional yondashuv", "Профессиональный подход к чистой коже", "A professional approach to clear skin")),
    ("img/photos/banner3.jpg", "", ("Hijoma — steril va xavfsiz", "Хиджама — стерильно и безопасно", "Hijama, sterile and safe"),
     ("Bir martalik asboblar, tajribali mutaxassis", "Одноразовые инструменты, опытный специалист", "Single-use instruments, an experienced specialist")),
]


class Command(BaseCommand):
    help = "Boshlang'ich ma'lumotlarni yaratadi"

    def handle(self, *args, **options):
        User = get_user_model()
        if not User.objects.filter(username=ADMIN_USERNAME).exists():
            password = os.environ.get("ADMIN_PASSWORD") or secrets.token_urlsafe(9)
            User.objects.create_superuser(ADMIN_USERNAME, password=password)
            self.stdout.write(f"Bosh admin: {ADMIN_USERNAME} / {password}")

        site = SiteSettings.load()
        if not site.phone:
            for field, value in SITE.items():
                setattr(site, field, value)
            site.save()

        if not Doctor.objects.exists():
            self.create_catalog()
        self.stdout.write(self.style.SUCCESS("Tayyor"))

    def create_catalog(self):
        cats = {}
        for order, (key, uz, ru, en, photo) in enumerate(CATEGORIES):
            cats[key] = Category.objects.create(name_uz=uz, name_ru=ru, name_en=en, order=order,
                                                default_image=f"img/photos/{photo}.jpg")
        docs = {}
        for order, row in enumerate(DOCTORS):
            docs[row["key"]] = Doctor.objects.create(
                name_uz=row["name"][0], name_ru=row["name"][1], name_en=row["name"][2],
                specialty_uz=row["spec"][0], specialty_ru=row["spec"][1], specialty_en=row["spec"][2],
                bio_uz=row["bio"][0], bio_ru=row["bio"][1], bio_en=row["bio"][2],
                experience=row["exp"], order=order,
                default_image=row["image"], default_image2=row["image2"], phone=SITE["phone"],
                telegram=SITE["telegram"], instagram=SITE["instagram"],
            )
        for order, row in enumerate(SERVICES):
            service = Service.objects.create(
                category=cats[row["cat"]], price=row["price"], old_price=row["old"],
                is_popular=row["popular"], order=order, keywords=row["keywords"],
                default_image=f"img/photos/{row['key']}.jpg",
                name_uz=row["uz"][0], short_uz=row["uz"][1], name_ru=row["ru"][0], short_ru=row["ru"][1],
                name_en=row["en"][0], short_en=row["en"][1],
                description_uz=row["desc"][0], description_ru=row["desc"][1], description_en=row["desc"][2],
            )
            service.doctors.add(docs["saragul"])
        for order, (image, badge, titles, subs) in enumerate(BANNERS):
            Banner.objects.create(
                default_image=image, badge=badge, order=order, link="/navbat/",
                title_uz=titles[0], title_ru=titles[1], title_en=titles[2],
                subtitle_uz=subs[0], subtitle_ru=subs[1], subtitle_en=subs[2],
            )
