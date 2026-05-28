"""B2 — seed_test_users command tests.

Idempotent seed of the 7 dummy users defined in auth_dummy_email.md.
"""
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase


EXPECTED_EMAILS = {
    "user.public@triplechat.test",
    "user.internal@triplechat.test",
    "manager.sales@triplechat.test",
    "manager.eng@triplechat.test",
    "admin@triplechat.test",
    "moderation.admin@triplechat.test",
    "inactive@triplechat.test",
}


class SeedTestUsersCommandTest(TestCase):
    def test_seeds_seven_users(self):
        User = get_user_model()
        call_command("seed_test_users", "--force", verbosity=0)
        self.assertEqual(User.objects.count(), 7)
        self.assertEqual(set(User.objects.values_list("email", flat=True)), EXPECTED_EMAILS)

    def test_password_is_set(self):
        User = get_user_model()
        call_command("seed_test_users", "--force", verbosity=0)
        u = User.objects.get(email="user.internal@triplechat.test")
        self.assertTrue(u.check_password("Triple!23"))

    def test_role_access_level_mapping(self):
        User = get_user_model()
        call_command("seed_test_users", "--force", verbosity=0)
        cases = [
            ("user.public@triplechat.test", "USER", "public"),
            ("user.internal@triplechat.test", "USER", "internal"),
            ("manager.sales@triplechat.test", "MANAGER", "confidential"),
            ("manager.eng@triplechat.test", "MANAGER", "confidential"),
            ("admin@triplechat.test", "ADMIN", "restricted"),
            ("moderation.admin@triplechat.test", "ADMIN", "restricted"),
            ("inactive@triplechat.test", "USER", "internal"),
        ]
        for email, role, level in cases:
            u = User.objects.get(email=email)
            self.assertEqual(u.role, role, email)
            self.assertEqual(u.access_level, level, email)

    def test_inactive_user_flag(self):
        User = get_user_model()
        call_command("seed_test_users", "--force", verbosity=0)
        u = User.objects.get(email="inactive@triplechat.test")
        self.assertFalse(u.is_active)

    def test_idempotent(self):
        User = get_user_model()
        call_command("seed_test_users", "--force", verbosity=0)
        call_command("seed_test_users", "--force", verbosity=0)
        self.assertEqual(User.objects.count(), 7)
