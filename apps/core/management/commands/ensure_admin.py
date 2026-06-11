"""
Idempotently create or update the bootstrap admin from environment variables.

Unlike ``createsuperuser --noinput`` (which only creates on a fresh database
and never updates), this upserts: it creates the account if missing and
refreshes the password / email / superuser flags if it already exists. That
makes "edit .env.prod, restart" actually take effect, and is safe to run on
every container start.

Reads DJANGO_SUPERUSER_USERNAME / _PASSWORD / _EMAIL. No-op (with a message)
if username or password is unset, so the entrypoint can call it
unconditionally.
"""

import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update the bootstrap superuser from DJANGO_SUPERUSER_* env vars."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=os.environ.get("DJANGO_SUPERUSER_USERNAME"))
        parser.add_argument("--password", default=os.environ.get("DJANGO_SUPERUSER_PASSWORD"))
        parser.add_argument("--email", default=os.environ.get("DJANGO_SUPERUSER_EMAIL", ""))

    def handle(self, *args, **options):
        from django.contrib.auth import get_user_model

        username = options["username"]
        password = options["password"]
        email = options["email"] or ""

        if not username or not password:
            self.stdout.write(
                "ensure_admin: DJANGO_SUPERUSER_USERNAME/PASSWORD not set — skipping."
            )
            return

        User = get_user_model()
        user, created = User.objects.get_or_create(username=username)
        user.email = email or user.email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(password)
        user.save()
        # The post_save signal grants all app roles to superusers.

        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(f"ensure_admin: {verb} superuser '{username}'.")
        )
