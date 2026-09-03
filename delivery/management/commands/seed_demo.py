from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from delivery.models import UserProfile


class Command(BaseCommand):
    help = "Creates demo accounts (and an admin superuser) so the panel can log in immediately, without needing shell access."

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

        # Shell access isn't available on Render's free tier, so we create the
        # admin superuser here too instead of via `createsuperuser` interactively.
        admin, created = User.objects.get_or_create(username="admin")
        if created:
            admin.set_password("reflexAdmin2026")
            admin.is_staff = True
            admin.is_superuser = True
            admin.save()
            self.stdout.write(self.style.SUCCESS("admin (superuser) - created"))
        else:
            self.stdout.write(self.style.SUCCESS("admin (superuser) - already existed"))

        self.stdout.write(self.style.SUCCESS(
            "\nDemo login — password for all demo users: reflex2026"
            "\nAdmin login — username: admin, password: reflexAdmin2026"
        ))