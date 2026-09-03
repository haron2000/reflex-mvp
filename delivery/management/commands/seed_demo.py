from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from delivery.models import UserProfile


class Command(BaseCommand):
    help = "Creates demo accounts for retailer/dispatcher/rider so the panel can log in immediately."

    def handle(self, *args, **options):
        demo_users = [
            ("retailer1", "RETAILER", {"shop_name": "Njoroge Auto Spares"}),
            ("dispatcher1", "DISPATCHER", {}),
            ("rider1", "RIDER", {"phone_number": "0712000001"}),
            ("rider2", "RIDER", {"phone_number": "0712000002"}),
        ]
        for username, role, extra in demo_users:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password("reflex2026")
                user.save()
            UserProfile.objects.update_or_create(user=user, defaults={"role": role, **extra})
            status = "created" if created else "already existed"
            self.stdout.write(self.style.SUCCESS(f"{username} ({role}) - {status}"))

        self.stdout.write(self.style.SUCCESS("\nDemo login — password for all: reflex2026"))
