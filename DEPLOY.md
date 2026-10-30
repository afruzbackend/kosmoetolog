# Saytni internetga joylash

Netlify Python serverni ishga tushirmaydi va fayllarni doimiy saqlamaydi. Shuning uchun:

- **PythonAnywhere**: sayt, navbatlar bazasi va yuklangan rasmlar shu yerda turadi.
- **Netlify**: chiroyli manzil beradi va hamma so'rovni PythonAnywhere'ga uzatadi.

Avval 1-qismni, keyin 2-qismni bajaring. `USERNAME` o'rniga PythonAnywhere foydalanuvchi nomingizni, `SAYT-NOMI` o'rniga Netlify'dagi sayt nomini yozing.

## 1-qism. PythonAnywhere

1. https://www.pythonanywhere.com saytida ro'yxatdan o'ting.
2. **Files** bo'limiga `dist/saragul-sayt.zip` faylini yuklang.
3. **Consoles** → **Bash** ochib, quyidagilarni birma-bir bajaring:

```bash
mkdir -p ~/sayt && cd ~/sayt && unzip -o ~/saragul-sayt.zip
python3.11 -m venv ~/.venvs/sayt
~/.venvs/sayt/bin/pip install -r requirements.txt
cp .env.example .env
~/.venvs/sayt/bin/python -c "import secrets; print(secrets.token_urlsafe(50))"
```

4. Oxirgi buyruq chiqargan kalitni nusxalang. **Files** orqali `~/sayt/.env` faylini ochib, `SECRET_KEY`, `USERNAME` va `SAYT-NOMI` qiymatlarini yozing.
5. Yana konsolda:

```bash
cd ~/sayt
~/.venvs/sayt/bin/python manage.py migrate
~/.venvs/sayt/bin/python manage.py collectstatic --noinput
~/.venvs/sayt/bin/python manage.py demo --clear
```

6. **Web** → **Add a new web app** → **Manual configuration** → **Python 3.11**.
7. **Virtualenv** maydoniga yozing: `/home/USERNAME/.venvs/sayt`
8. **WSGI configuration file** havolasini ochib, ichidagini shu bilan almashtiring:

```python
import os
import sys

sys.path.insert(0, "/home/USERNAME/sayt")
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

9. **Reload** tugmasini bosing va `https://USERNAME.pythonanywhere.com` manzilini oching. Sayt shu yerda ishlashi kerak.

### Arxiv o'rniga GitHub'dan olsangiz

Repozitoriyda baza, `logins.txt` va `.env` yo'q. Shuning uchun 2-3 qadam o'rniga kodni `git clone` bilan oling, 5-qadamda esa `collectstatic` dan keyin `manage.py seed` bajaring. U bosh admin (`glavniy`) parolini ekranga chiqaradi, `demo --clear` shart emas. Doktor loginini panelda **Mutaxassislar** bo'limida yarating.

## 2-qism. Netlify

1. `netlify/_redirects` faylida `USERNAME` so'zini almashtiring.
2. https://app.netlify.com saytiga kiring: **Add new project** → **Deploy manually**.
3. `netlify` papkasini sahifaga sudrab tashlang.
4. **Site configuration** → **Change site name** orqali `SAYT-NOMI` ni belgilang.
5. Agar nom o'zgargan bo'lsa, PythonAnywhere'dagi `.env` faylida ham yangilab, **Reload** bosing.
6. `https://SAYT-NOMI.netlify.app` manzilini oching va tekshiring.

## Ishga tushgach tekshiring

- Bosh sahifa va rasmlar ochiladi.
- `/panel/` orqali login bilan kirish ishlaydi.
- Sinov navbati olinadi va panelda ko'rinadi, keyin uni bekor qiling.
- Panelda bitta rasm almashtirib ko'ring.

## Muhim

- Haqiqiy mijozlar uchun PythonAnywhere'ning pullik tarifi tavsiya etiladi: bepul tarifda web app har oyda uzaytirilishi, CPU va disk cheklangan.
- Telegram xabari bepul tarifda ishlamasligi mumkin, chunki tashqi saytlarga chiqish cheklangan.
- `logins.txt` va `.env` faylini hech kimga bermang.
- Parollarni ishga tushirishdan oldin panelda almashtiring.
- Kod o'zgarsa: faylni yangilang, `collectstatic` bajaring va **Reload** bosing.
