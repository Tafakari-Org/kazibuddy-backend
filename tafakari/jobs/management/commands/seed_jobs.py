"""
Seed command — creates test job data for local/staging development.

Usage:
    python manage.py seed_jobs            # create all seed data (skips existing)
    python manage.py seed_jobs --flush    # wipe seed data and recreate from scratch

Creates:
  - 5 job categories
  - 5 skills
  - 12 jobs in various states (active/approved, pending, draft, filled),
    posted by / applied to by seed users directly (no separate profile needed)

Requires seed users to exist first:
    python manage.py seed_data
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta

from accounts.models import CustomUser
from skills.models import Skill, SkillCategory
from jobs.models import Job, JobCategory

SEED_DOMAIN = "@tafakari.local"

# ── Categories ────────────────────────────────────────────────────────────────

CATEGORIES = [
    {
        "name": "Cleaning & Housekeeping",
        "description": "Home cleaning, office cleaning, laundry and related services",
    },
    {
        "name": "Construction & Labour",
        "description": "Building, renovation, plumbing, electrical and general labour",
    },
    {
        "name": "Delivery & Logistics",
        "description": "Courier, goods delivery, moving and transportation services",
    },
    {
        "name": "Catering & Events",
        "description": "Food preparation, event setup, waitstaff and bartending",
    },
    {
        "name": "IT & Tech Support",
        "description": "Computer repair, networking, software and digital services",
    },
]

# ── Skills ────────────────────────────────────────────────────────────────────

SKILL_CATEGORY_NAME = "General Skills"

SKILLS = [
    "House Cleaning",
    "Masonry",
    "Motorcycle Delivery",
    "Food Preparation",
    "Computer Repair",
]

# ── Jobs ──────────────────────────────────────────────────────────────────────
# employer_email references a seed user created by `seed_data` (must have posted
# jobs directly — no separate employer profile required).
# category_name references one of the CATEGORIES above.

TODAY = date.today()

JOBS = [
    # ── Active + admin approved (visible to workers) ───────────────────────
    {
        "employer_email": f"alice{SEED_DOMAIN}",
        "category_name": "Cleaning & Housekeeping",
        "title": "Live-in Housekeeper – Westlands Home",
        "description": (
            "We are looking for a reliable, full-time live-in housekeeper for our family home in Westlands. "
            "Duties include cleaning all rooms, laundry, ironing and light cooking. "
            "Accommodation provided. Monday–Saturday, 7am–5pm."
        ),
        "location_text": "Westlands, Nairobi",
        "job_type": "full_time",
        "urgency_level": "medium",
        "budget_min": "18000.00",
        "budget_max": "25000.00",
        "payment_type": "monthly",
        "start_date": TODAY + timedelta(days=7),
        "estimated_hours": 160,
        "max_applicants": 5,
        "status": "active",
        "admin_approved": True,
        "is_featured": True,
        "views_count": 42,
        "applications_count": 3,
    },
    {
        "employer_email": f"alice{SEED_DOMAIN}",
        "category_name": "Catering & Events",
        "title": "Waitstaff Needed for Weekend Wedding – Karen",
        "description": (
            "We need 4 experienced waitstaff for a wedding reception on Saturday 5th July. "
            "Event runs from 12pm to 10pm. Smart uniform required (we provide). "
            "Must have at least 1 year experience in events or restaurant service."
        ),
        "location_text": "Karen, Nairobi",
        "job_type": "temporary",
        "urgency_level": "high",
        "budget_min": "2500.00",
        "budget_max": "3500.00",
        "payment_type": "daily",
        "start_date": TODAY + timedelta(days=14),
        "end_date": TODAY + timedelta(days=14),
        "estimated_hours": 10,
        "max_applicants": 8,
        "status": "active",
        "admin_approved": True,
        "is_featured": False,
        "views_count": 18,
        "applications_count": 6,
    },
    {
        "employer_email": f"bob{SEED_DOMAIN}",
        "category_name": "Delivery & Logistics",
        "title": "Motorbike Courier – Nairobi CBD Routes",
        "description": (
            "Otieno Logistics is hiring motorbike riders for daily parcel delivery across Nairobi CBD, "
            "Westlands and Parklands. Must own a roadworthy motorbike and have a valid licence. "
            "Earn per delivery plus a daily retainer. Start immediately."
        ),
        "location_text": "CBD, Nairobi",
        "job_type": "part_time",
        "urgency_level": "urgent",
        "budget_min": "700.00",
        "budget_max": "1200.00",
        "payment_type": "daily",
        "start_date": TODAY + timedelta(days=2),
        "estimated_hours": 8,
        "max_applicants": 10,
        "status": "active",
        "admin_approved": True,
        "is_featured": True,
        "views_count": 95,
        "applications_count": 12,
    },
    {
        "employer_email": f"bob{SEED_DOMAIN}",
        "category_name": "Construction & Labour",
        "title": "Site Labourers – Warehouse Construction, Mlolongo",
        "description": (
            "Looking for 8 general labourers for a 3-month warehouse construction project in Mlolongo. "
            "Work involves loading, offloading, mixing concrete and general site duties. "
            "PPE provided on site. Monday–Saturday, 6am–4pm."
        ),
        "location_text": "Mlolongo, Machakos",
        "job_type": "contract",
        "urgency_level": "medium",
        "budget_min": "600.00",
        "budget_max": "800.00",
        "payment_type": "daily",
        "start_date": TODAY + timedelta(days=5),
        "end_date": TODAY + timedelta(days=95),
        "estimated_hours": 240,
        "max_applicants": 15,
        "status": "active",
        "admin_approved": True,
        "is_featured": False,
        "views_count": 31,
        "applications_count": 8,
    },
    {
        "employer_email": f"alice{SEED_DOMAIN}",
        "category_name": "IT & Tech Support",
        "title": "IT Support Technician – Office Network Setup",
        "description": (
            "We need an IT technician to set up a small office LAN, configure 10 workstations "
            "and install a basic CCTV system. One-off engagement, estimated 2–3 days. "
            "Must bring own tools. Experience with Windows networks required."
        ),
        "location_text": "Upper Hill, Nairobi",
        "job_type": "temporary",
        "urgency_level": "medium",
        "budget_min": "15000.00",
        "budget_max": "20000.00",
        "payment_type": "fixed",
        "start_date": TODAY + timedelta(days=10),
        "estimated_hours": 24,
        "max_applicants": 3,
        "status": "active",
        "admin_approved": True,
        "is_featured": False,
        "views_count": 14,
        "applications_count": 2,
    },
    # ── Pending admin approval ─────────────────────────────────────────────
    {
        "employer_email": f"bob{SEED_DOMAIN}",
        "category_name": "Delivery & Logistics",
        "title": "Van Driver – Weekend Furniture Deliveries",
        "description": (
            "Part-time van driver needed for weekend furniture deliveries around Nairobi. "
            "Must have a valid BCE licence and at least 2 years driving experience. "
            "Vehicle provided. Saturdays and Sundays, 7am–3pm."
        ),
        "location_text": "South C, Nairobi",
        "job_type": "part_time",
        "urgency_level": "low",
        "budget_min": "1500.00",
        "budget_max": "2000.00",
        "payment_type": "daily",
        "start_date": TODAY + timedelta(days=7),
        "estimated_hours": 16,
        "max_applicants": 2,
        "status": "active",
        "admin_approved": False,
        "is_featured": False,
        "views_count": 0,
        "applications_count": 0,
    },
    {
        "employer_email": f"alice{SEED_DOMAIN}",
        "category_name": "Catering & Events",
        "title": "Head Chef – Corporate Canteen, 3-Month Contract",
        "description": (
            "Seeking an experienced head chef to run a corporate canteen serving 80 staff daily. "
            "Menu planning, food ordering and supervision of 2 kitchen assistants required. "
            "Must hold a valid food handler's certificate."
        ),
        "location_text": "Gigiri, Nairobi",
        "job_type": "contract",
        "urgency_level": "high",
        "budget_min": "45000.00",
        "budget_max": "60000.00",
        "payment_type": "monthly",
        "start_date": TODAY + timedelta(days=21),
        "end_date": TODAY + timedelta(days=111),
        "estimated_hours": 480,
        "max_applicants": 5,
        "status": "active",
        "admin_approved": False,
        "is_featured": False,
        "views_count": 0,
        "applications_count": 0,
    },
    # ── Draft (not yet submitted for approval) ─────────────────────────────
    {
        "employer_email": f"bob{SEED_DOMAIN}",
        "category_name": "Construction & Labour",
        "title": "Plumber – Apartment Block, Kasarani [DRAFT]",
        "description": (
            "Need a qualified plumber for a 2-week assignment fixing leaking pipes and "
            "installing new fixtures across a 20-unit apartment block in Kasarani."
        ),
        "location_text": "Kasarani, Nairobi",
        "job_type": "temporary",
        "urgency_level": "medium",
        "budget_min": "2500.00",
        "budget_max": "3500.00",
        "payment_type": "daily",
        "start_date": TODAY + timedelta(days=30),
        "estimated_hours": 80,
        "max_applicants": 2,
        "status": "draft",
        "admin_approved": False,
        "is_featured": False,
        "views_count": 0,
        "applications_count": 0,
    },
    # ── Filled (already assigned) ──────────────────────────────────────────
    {
        "employer_email": f"alice{SEED_DOMAIN}",
        "category_name": "Cleaning & Housekeeping",
        "title": "Office Cleaner – Kilimani Block [FILLED]",
        "description": (
            "Part-time office cleaner for a 3-storey office block. Evenings only, "
            "Monday–Friday 6pm–9pm."
        ),
        "location_text": "Kilimani, Nairobi",
        "job_type": "part_time",
        "urgency_level": "low",
        "budget_min": "500.00",
        "budget_max": "700.00",
        "payment_type": "daily",
        "start_date": TODAY - timedelta(days=30),
        "estimated_hours": 60,
        "max_applicants": 3,
        "status": "filled",
        "admin_approved": True,
        "is_assigned": True,
        "is_featured": False,
        "views_count": 58,
        "applications_count": 9,
    },
    # ── Completed ──────────────────────────────────────────────────────────
    {
        "employer_email": f"bob{SEED_DOMAIN}",
        "category_name": "Delivery & Logistics",
        "title": "Event Setup Crew – KICC Conference [COMPLETED]",
        "description": (
            "Crew of 6 needed to set up chairs, tables and AV equipment for a 2-day "
            "international conference at KICC. Setup day 1 June, conference 2–3 June."
        ),
        "location_text": "KICC, CBD Nairobi",
        "job_type": "temporary",
        "urgency_level": "high",
        "budget_min": "1500.00",
        "budget_max": "2000.00",
        "payment_type": "daily",
        "start_date": TODAY - timedelta(days=25),
        "end_date": TODAY - timedelta(days=22),
        "estimated_hours": 24,
        "max_applicants": 6,
        "status": "completed",
        "admin_approved": True,
        "is_assigned": True,
        "is_featured": False,
        "views_count": 77,
        "applications_count": 11,
    },
    # ── Paused ─────────────────────────────────────────────────────────────
    {
        "employer_email": f"alice{SEED_DOMAIN}",
        "category_name": "IT & Tech Support",
        "title": "Social Media Manager – Part Time [PAUSED]",
        "description": (
            "Looking for a part-time social media manager to handle Instagram, Facebook and "
            "TikTok for our hospitality brand. 3 hours per day, fully remote."
        ),
        "location_text": "Remote",
        "job_type": "part_time",
        "urgency_level": "low",
        "budget_min": "8000.00",
        "budget_max": "12000.00",
        "payment_type": "monthly",
        "start_date": TODAY + timedelta(days=3),
        "estimated_hours": 60,
        "max_applicants": 5,
        "status": "paused",
        "admin_approved": True,
        "is_featured": False,
        "views_count": 23,
        "applications_count": 4,
    },
    # ── Cancelled ──────────────────────────────────────────────────────────
    {
        "employer_email": f"bob{SEED_DOMAIN}",
        "category_name": "Construction & Labour",
        "title": "Painter – Ngong Road Offices [CANCELLED]",
        "description": (
            "Painters needed to repaint 4 offices and 2 corridors. "
            "Paint and materials provided. Estimated 5 days."
        ),
        "location_text": "Ngong Road, Nairobi",
        "job_type": "temporary",
        "urgency_level": "low",
        "budget_min": "1200.00",
        "budget_max": "1500.00",
        "payment_type": "daily",
        "start_date": TODAY - timedelta(days=10),
        "estimated_hours": 40,
        "max_applicants": 4,
        "status": "cancelled",
        "admin_approved": False,
        "is_featured": False,
        "views_count": 5,
        "applications_count": 0,
    },
]


class Command(BaseCommand):
    help = "Seed the database with test job data (dev/staging only)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--flush",
            action="store_true",
            help="Delete all seed job data before recreating",
        )

    def handle(self, *args, **options):
        if options["flush"]:
            self._flush()

        with transaction.atomic():
            categories = self._seed_categories()
            self._seed_skill_category_and_skills()
            self._seed_jobs(categories)

        self._print_summary()

    # ── Flush ─────────────────────────────────────────────────────────────────

    def _flush(self):
        from jobs.models import Job, JobCategory

        job_titles = [j["title"] for j in JOBS]
        deleted_jobs, _ = Job.objects.filter(title__in=job_titles).delete()
        self.stdout.write(self.style.WARNING(f"  flushed {deleted_jobs} job(s)"))

        cat_names = [c["name"] for c in CATEGORIES]
        deleted_cats, _ = JobCategory.objects.filter(name__in=cat_names).delete()
        self.stdout.write(self.style.WARNING(f"  flushed {deleted_cats} category(ies)"))

        skill_names = SKILLS
        deleted_skills, _ = Skill.objects.filter(name__in=skill_names).delete()
        self.stdout.write(self.style.WARNING(f"  flushed {deleted_skills} skill(s)"))

        deleted_sc, _ = SkillCategory.objects.filter(name=SKILL_CATEGORY_NAME).delete()
        self.stdout.write(self.style.WARNING(f"  flushed {deleted_sc} skill category(ies)"))

    # ── Categories ────────────────────────────────────────────────────────────

    def _seed_categories(self):
        self.stdout.write("\n  Job categories:")
        result = {}
        for data in CATEGORIES:
            cat, created = JobCategory.objects.get_or_create(
                name=data["name"],
                defaults={"description": data["description"], "is_active": True},
            )
            result[cat.name] = cat
            status = "created" if created else "exists "
            self.stdout.write(self.style.SUCCESS(f"    {status}  {cat.name}"))
        return result

    # ── Skills ────────────────────────────────────────────────────────────────

    def _seed_skill_category_and_skills(self):
        self.stdout.write("\n  Skills:")
        sc, _ = SkillCategory.objects.get_or_create(name=SKILL_CATEGORY_NAME)
        for name in SKILLS:
            skill, created = Skill.objects.get_or_create(
                name=name,
                defaults={"category": sc, "is_active": True},
            )
            status = "created" if created else "exists "
            self.stdout.write(self.style.SUCCESS(f"    {status}  {skill.name}"))

    # ── Jobs ──────────────────────────────────────────────────────────────────

    def _seed_jobs(self, categories):
        self.stdout.write("\n  Jobs:")
        created_count = 0
        skipped_count = 0

        for data in JOBS:
            try:
                employer = CustomUser.objects.get(email=data["employer_email"])
            except CustomUser.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"    SKIP — employer {data['employer_email']} not found (run seed_data first)"
                    )
                )
                skipped_count += 1
                continue

            category = categories.get(data["category_name"])

            defaults = {
                k: v
                for k, v in data.items()
                if k not in ("employer_email", "category_name")
            }
            defaults["employer"] = employer
            defaults["category"] = category
            defaults.setdefault("visibility", "public")
            defaults.setdefault("is_assigned", False)

            job, created = Job.objects.get_or_create(
                title=data["title"],
                employer=employer,
                defaults=defaults,
            )

            if created:
                created_count += 1
                flag = ""
                if job.status == "active" and job.admin_approved:
                    flag = " [LIVE]"
                elif not job.admin_approved:
                    flag = " [PENDING APPROVAL]"
                elif job.status == "draft":
                    flag = " [DRAFT]"
                else:
                    flag = f" [{job.status.upper()}]"
                self.stdout.write(
                    self.style.SUCCESS(f"    created  {job.title}{flag}")
                )
            else:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(f"    exists   {job.title}")
                )

        return created_count, skipped_count

    # ── Summary ───────────────────────────────────────────────────────────────

    def _print_summary(self):
        from jobs.models import Job

        total = Job.objects.count()
        live = Job.objects.filter(status="active", admin_approved=True).count()
        pending = Job.objects.filter(admin_approved=False, status="active").count()
        draft = Job.objects.filter(status="draft").count()
        other = total - live - pending - draft

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"  Done."))
        self.stdout.write(f"  Total jobs in DB : {total}")
        self.stdout.write(f"  Live (approved)  : {live}")
        self.stdout.write(f"  Pending approval : {pending}")
        self.stdout.write(f"  Draft            : {draft}")
        self.stdout.write(f"  Other            : {other}")
        self.stdout.write("")
        self.stdout.write("  Employer accounts used:")
        self.stdout.write(f"    alice@tafakari.local  — Kamau Family Enterprises")
        self.stdout.write(f"    bob@tafakari.local    — Otieno Logistics Ltd")
        self.stdout.write("")
        self.stdout.write("  Worker accounts seeded:")
        self.stdout.write(f"    carol@tafakari.local  — available (approved)")
        self.stdout.write(f"    david@tafakari.local  — available (approved)")
        self.stdout.write(f"    eve@tafakari.local    — unavailable (pending)")
        self.stdout.write("")
