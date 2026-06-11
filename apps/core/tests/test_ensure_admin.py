import pytest
from django.core.management import call_command

from apps.core.models import Role, User


@pytest.mark.django_db
class TestEnsureAdmin:
    def test_creates_superuser_with_all_roles(self):
        call_command("ensure_admin", username="admin", password="pw12345", email="a@example.com")
        user = User.objects.get(username="admin")
        assert user.is_superuser and user.is_staff
        assert user.check_password("pw12345")
        # post_save signal grants every app role to superusers
        assert set(user.role_values) == {r.value for r in Role}

    def test_updates_existing_password(self):
        call_command("ensure_admin", username="admin", password="old-pw-123")
        call_command("ensure_admin", username="admin", password="new-pw-456")
        user = User.objects.get(username="admin")
        assert user.check_password("new-pw-456")
        assert User.objects.filter(username="admin").count() == 1

    def test_noop_without_credentials(self):
        call_command("ensure_admin", username="", password="")
        assert User.objects.count() == 0

    def test_idempotent_repeated_runs(self):
        for _ in range(3):
            call_command("ensure_admin", username="admin", password="pw12345")
        assert User.objects.filter(username="admin").count() == 1
