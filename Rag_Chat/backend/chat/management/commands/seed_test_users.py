"""Seed 7 dummy users for auth/RBAC/ACL testing.

Source of truth = `auth_dummy_email.md` (repo root). Idempotent — re-running
upserts role/access_level and resets the password but leaves user_id intact.

Dev/test only. Refuse to run when DEBUG=False unless --force passed, to
prevent accidentally seeding the matrix into a prod database.
"""
from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


# (email, role, access_level, department_name_or_None, is_active)
SEED_USERS: list[tuple[str, str, str, str | None, bool]] = [
    ("user.public@triplechat.test",        "USER",    "public",       None,           True),
    ("user.internal@triplechat.test",      "USER",    "internal",     "Sales",        True),
    ("manager.sales@triplechat.test",      "MANAGER", "confidential", "Sales",        True),
    ("manager.eng@triplechat.test",        "MANAGER", "confidential", "Engineering",  True),
    ("admin@triplechat.test",              "ADMIN",   "restricted",   None,           True),
    ("moderation.admin@triplechat.test",   "ADMIN",   "restricted",   None,           True),
    ("inactive@triplechat.test",           "USER",    "internal",     "Sales",        False),
]

PASSWORD = "Triple!23"


class Command(BaseCommand):
    help = "Seed dummy test users defined in auth_dummy_email.md (dev only)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run even when DEBUG=False (be sure you're not on prod).",
        )

    def handle(self, *args, **opts):
        if not settings.DEBUG and not opts.get("force"):
            raise CommandError(
                "seed_test_users refuses to run with DEBUG=False. Pass --force to override."
            )

        User = get_user_model()
        from knowledge.models import Department

        # Pre-create departments referenced by the matrix.
        dept_cache: dict[str, Department] = {}
        for _, _, _, dept_name, _ in SEED_USERS:
            if dept_name and dept_name not in dept_cache:
                dept_cache[dept_name], _ = Department.objects.get_or_create(name=dept_name)

        created = 0
        updated = 0
        for email, role, access_level, dept_name, is_active in SEED_USERS:
            defaults = {
                "role": role,
                "access_level": access_level,
                "department": dept_cache.get(dept_name) if dept_name else None,
                "is_active": is_active,
            }
            user, was_created = User.objects.get_or_create(email=email, defaults=defaults)
            if was_created:
                created += 1
            else:
                for k, v in defaults.items():
                    setattr(user, k, v)
                updated += 1
            user.set_password(PASSWORD)
            user.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"seed_test_users: {created} created, {updated} updated "
                f"(total={User.objects.count()})"
            )
        )
