"""
Seed command — creates test users for local/staging development.


Usage:
    python manage.py seed_data            # create all seed users
    python manage.py seed_data --flush    # delete seed users fir
    st, then recreate

All seed accounts use the password:  Admin@1234
Seed users are identified by emails ending in @tafakari.local — never use
this domain in production.

"""


from django.core.management.base import BaseCommand
from django.db import transaction
from accounts.models import CustomUser

PASSWORD = "Admin@1234"

SEED_DOMAIN = "@tafakari.local"


SEED_USERS = [
    # ── super admins ──────────────────────────────────────────────────────────
    {
        "email": "superadmin@tafakari.local",
        "full_name": "Super Admin",
        "username": "superadmin",
        "phone_number": "0700000001",
        "user_type": "super_admin",
        "is_staff": True,
        "is_superuser": True,
        "is_active": True,
        "is_verified": True,
        "email_verified": True,
    },
    # ── admins ────────────────────────────────────────────────────────────────
    {
        "email": "admin@tafakari.local",
        "full_name": "Admin User",
        "username": "admin",
        "phone_number": "0700000002",
        "user_type": "admin",
        "is_staff": True,
        "is_superuser": False,
        "is_active": True,
        "is_verified": True,
        "email_verified": True,
    },
    {
        "email": "admin2@tafakari.local",
        "full_name": "Second Admin",
        "username": "admin2",
        "phone_number": "0700000003",
        "user_type": "admin",
        "is_staff": True,
        "is_superuser": False,
        "is_active": True,
        "is_verified": True,
        "email_verified": True,
    },
    # ── regular users ─────────────────────────────────────────────────────────
    {
        "email": "alice@tafakari.local",
        "full_name": "Alice Kamau",
        "username": "alice_kamau",
        "phone_number": "0712000001",
        "user_type": "user",
        "is_staff": False,
        "is_superuser": False,
        "is_active": True,
        "is_verified": True,
        "email_verified": True,
    },

    {
        "email": "bob@tafakari.local",
        "full_name": "Bob Otieno",
        "username": "bob_otieno",
        "phone_number": "0712000002",
        "user_type": "user",
        "is_staff": False,
        "is_superuser": False,
        "is_active": True,
        "is_verified": True,
        "email_verified": True,
    },
    {
        "email": "carol@tafakari.local",
        "full_name": "Carol Mwangi",
        "username": "carol_mwangi",
        "phone_number": "0712000003",
        "user_type": "user",
        "is_staff": False,
        "is_superuser": False,
        "is_active": True,
        "is_verified": True,
        "email_verified": True,
    },
    {
        "email": "david@tafakari.local",
        "full_name": "David Njoroge",
        "username": "david_njoroge",
        "phone_number": "0712000004",
        "user_type": "user",
        "is_staff": False,
        "is_superuser": False,
        "is_active": True,
        "is_verified": True,
        "email_verified": True,
    },
    {
        "email": "eve@tafakari.local",
        "full_name": "Eve Achieng",
        "username": "eve_achieng",
        "phone_number": "0712000005",
        "user_type": "user",
        "is_staff": False,
        "is_superuser": False,
        "is_active": False,  # intentionally inactive — tests deactivation flow
        "is_verified": True,
        "email_verified": True,
    },
    {
        "email": "frank@tafakari.local",
        "full_name": "Frank Kimani",
        "username": "frank_kimani",
        "phone_number": "0712000006",
        "user_type": "user",
        "is_staff": False,
        "is_superuser": False,
        "is_active": True,
        "is_verified": False,  # intentionally unverified — tests pending-user flow
        "email_verified": False,
    },
]


class Command(BaseCommand):
    help = "Seed the database with test users (dev/staging only)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete existing seed users before recreating them",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            deleted, _ = CustomUser.objects.filter(
                email__endswith=SEED_DOMAIN
            ).delete()
            self.stdout.write(self.style.WARNING(f"Flushed {deleted} seed user(s)."))

        created_count = 0
        skipped_count = 0

        with transaction.atomic():
            for data in SEED_USERS:
                email = data["email"]
                extra = {k: v for k, v in data.items() if k != "email"}
                user, created = CustomUser.objects.get_or_create(
                    email=email,
                    defaults=extra,
                )
                if created:
                    user.set_password(PASSWORD)
                    user.save()
                    created_count += 1
                    label = f"[{data['user_type'].upper()}]"
                    self.stdout.write(
                        self.style.SUCCESS(f"  created  {label:<14} {email}")
                    )
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(f"  skipped  (exists)      {email}")
                    )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done — {created_count} created, {skipped_count} skipped."
            )
        )
        self.stdout.write("")
        self.stdout.write("  Password for all seed accounts:  Admin@1234")
        self.stdout.write("")
        self.stdout.write("  Seed accounts:")
        self.stdout.write("    superadmin@tafakari.local  — super_admin")
        self.stdout.write("    admin@tafakari.local       — admin")
        self.stdout.write("    admin2@tafakari.local      — admin")
        self.stdout.write("    alice@tafakari.local       — user (active, verified)")
        self.stdout.write("    bob@tafakari.local         — user (active, verified)")
        self.stdout.write("    carol@tafakari.local       — user (active, verified)")
        self.stdout.write("    david@tafakari.local       — user (active, verified)")
        self.stdout.write("    eve@tafakari.local         — user (inactive)")
        self.stdout.write("    frank@tafakari.local       — user (unverified/pending)")
