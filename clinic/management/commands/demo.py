"""Video uchun namuna navbatlar. `demo --clear` faqat shu namunalarni o'chiradi."""
import random
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from clinic.booking import now_local, work_hours
from clinic.models import Appointment, Client, Doctor, Service

DEMO_NOTE = "Namuna mijoz (video uchun)"
NAMES = ["Aziza Yusupova", "Dilnoza Qodirova", "Malika Ergasheva", "Shahlo Tursunova", "Gulnora Karimova",
         "Sevara Nazarova", "Nodira Xolmatova", "Feruza Aliyeva", "Kamola Rustamova", "Zilola Sobirova",
         "Barno Ismoilova", "Umida Abdullayeva", "Nargiza Toshpo‘latova", "Lola Mirzayeva"]
DAYS_BACK = 29
DAYS_AHEAD = 7


class Command(BaseCommand):
    help = "Video uchun namuna navbatlar va mijozlarni qo'shadi yoki o'chiradi"

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="namunalarni o'chirish")

    def handle(self, *args, **options):
        removed = self.clear()
        if options["clear"]:
            self.stdout.write(self.style.SUCCESS(f"O'chirildi: {removed} ta navbat"))
            return
        count = self.create()
        self.stdout.write(self.style.SUCCESS(f"Qo'shildi: {count} ta navbat, {len(NAMES)} ta mijoz"))

    def clear(self):
        demo = Client.objects.filter(note=DEMO_NOTE)
        removed = Appointment.objects.filter(client__in=demo).delete()[0]
        demo.delete()
        return removed

    def create(self):
        rng = random.Random(7)
        now = now_local()
        today = now.date()
        clients = []
        for index, name in enumerate(NAMES, 1):
            client = Client.objects.create(name=name, phone=f"99890000{index:04d}", note=DEMO_NOTE)
            joined = now - timedelta(days=rng.randint(0, DAYS_BACK))
            Client.objects.filter(pk=client.pk).update(created_at=joined)
            clients.append(client)

        count = 0
        doctors = list(Doctor.objects.filter(is_active=True))
        for offset in range(-DAYS_BACK, DAYS_AHEAD + 1):
            day = today + timedelta(days=offset)
            for doctor in doctors:
                if day.weekday() not in doctor.work_day_set:
                    continue
                services = list(Service.objects.filter(doctors=doctor, is_active=True))
                hours = work_hours(doctor)
                taken = set(Appointment.objects.filter(doctor=doctor, date=day)
                            .exclude(status=Appointment.Status.CANCELLED).values_list("time", flat=True))
                free = [h for h in hours if h not in taken]
                for hour in rng.sample(free, min(rng.randint(3, 6), len(free))):
                    service = rng.choice(services)
                    moment = timezone.make_aware(datetime.combine(day, hour))
                    if moment < now:
                        status = rng.choice(["done"] * 8 + ["cancelled", "noshow"])
                    else:
                        status = rng.choice(["new", "confirmed", "confirmed"])
                    Appointment.objects.create(
                        client=rng.choice(clients), doctor=doctor, service=service, date=day, time=hour,
                        status=status, price=service.price,
                        source=rng.choice([Appointment.Source.SITE, Appointment.Source.PANEL]),
                    )
                    count += 1
        return count
