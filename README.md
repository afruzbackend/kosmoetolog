# Kosmetologiya markazi sayti

Onlayn navbat, 3 ta shifokor uchun alohida kalendar, kunlik hisobot va bitta login bilan boshqariladigan admin panel.

## Ishga tushirish

```bash
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py seed
.venv\Scripts\python.exe manage.py runserver
```

- Sayt: http://127.0.0.1:8000/
- Admin panel: http://127.0.0.1:8000/panel/

## Loginlar

- Bosh admin hammasini boshqaradi: navbatlar, mutaxassislar, xizmatlar, bannerlar, hisobot, sozlamalar.
- Doktor faqat o'z navbatlari, kalendari, mijozlari, hisoboti va profilini ko'radi.

Joriy loginlar `logins.txt` faylida. U gitga qo'shilmaydi. Yangi bazada `seed` buyrug'i bosh admin parolini ekranga chiqaradi (`ADMIN_PASSWORD` bilan o'zingiz berishingiz ham mumkin). Yangi mutaxassis uchun login panelda **Mutaxassislar** bo'limida yaratiladi.

## Namuna ma'lumotlar

Video yoki ko'rsatuv uchun namuna navbatlar va mijozlar. Qayta ishga tushirilsa, sanalar bugungi kunga yangilanadi. Haqiqiy navbatlarga tegmaydi.

```bash
.venv\Scripts\python.exe manage.py demo
```

Saytni ishga tushirishdan oldin o'chiring, aks holda namuna navbatlar bo'sh vaqtlarni band qilib turadi:

```bash
.venv\Scripts\python.exe manage.py demo --clear
```

## Fotosuratlar

`static/img/photos/` dagi fotolar [Pexels](https://www.pexels.com/license/) litsenziyasi bilan olingan: tijorat saytida bepul, muallifni ko'rsatish shart emas, tahrirlash mumkin. Fotodagi odamlar markazni tavsiya qilayotgandek ko'rsatilmasligi kerak.

| Fayl | Manba |
| --- | --- |
| meso | https://www.pexels.com/photo/hands-with-syringe-touching-patient-face-9157201/ |
| bio | https://www.pexels.com/photo/hands-holding-cosmetic-injection-vials-in-pink-gloves-34220315/ |
| plasma | https://www.pexels.com/photo/a-syringe-with-red-liquid-on-a-person-s-skin-6629368/ |
| clean | https://www.pexels.com/photo/woman-at-beautician-15866050/ |
| peel | https://www.pexels.com/photo/photo-of-woman-having-facial-care-4207234/ |
| oxy | https://www.pexels.com/photo/cosmetologist-applying-facial-mask-on-customer-face-in-spa-salon-5069494/ |
| mask | https://www.pexels.com/photo/beautician-removing-clay-cosmetic-mask-from-woman-face-12115041/ |
| hijama, banner3 | https://www.pexels.com/photo/close-up-shot-of-a-cupping-therapy-8312830/ |
| hijama2 | https://www.pexels.com/photo/a-person-applying-ventosa-on-a-man-s-back-6076127/ |
| massage | https://www.pexels.com/photo/woman-having-facial-care-3738349/ |
| banner1 | https://www.pexels.com/photo/woman-doing-a-treatment-at-beautician-19242406/ |
| banner2 | https://www.pexels.com/photo/woman-getting-a-facial-treatment-3985329/ |

## Testlar

```bash
.venv\Scripts\python.exe manage.py test clinic
```

## Serverga joylash

`DEBUG=0`, `SECRET_KEY`, `ALLOWED_HOSTS` va `CSRF_TRUSTED_ORIGINS` muhit o'zgaruvchilarini bering, `manage.py collectstatic` ni ishga tushiring, `static` va `media` papkalarini veb-server orqali bering.

## Tuzilishi

- `clinic/booking.py`: navbat mantig'i (har shifokorga soatiga bitta mijoz)
- `clinic/search.py`: uch tilli, xatoga chidamli qidiruv
- `clinic/i18n.py`: sayt matnlari (uz, ru, en)
- `clinic/panel_views.py`: admin panel
- `static/js/masks.js`: telefon, narx, vaqt va ism qoliplari
