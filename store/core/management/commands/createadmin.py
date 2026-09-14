"""
Create or update the EKIOBA backend admin account from environment variables.

The admin API (`/api/admin/...`) authenticates with a JWT obtained from
`/api/admin/auth/token/`, and `AdminTokenObtainPairSerializer` rejects any user
that is not `is_staff`. This command guarantees an account that satisfies that.

It is idempotent — safe to run on every deploy:
  * account missing  -> created
  * account present  -> password and staff/superuser flags re-synced

Credentials are read from ADMIN_EMAIL / ADMIN_PASSWORD, falling back to the
DJANGO_SUPERUSER_* names for compatibility with the older startup script.
The password is never echoed.
"""
from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


def _env(*names: str, default: str = "") -> str:
    """First non-empty value among `names`."""
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default


class Command(BaseCommand):
    help = "Create or update the backend admin account from ADMIN_EMAIL / ADMIN_PASSWORD."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--username",
            help="Login username. Defaults to ADMIN_USERNAME, else the admin email.",
        )
        parser.add_argument(
            "--email",
            help="Admin email. Defaults to ADMIN_EMAIL.",
        )
        parser.add_argument(
            "--skip-password-update",
            action="store_true",
            help="If the account already exists, leave its current password alone.",
        )

    def handle(self, *args, **options) -> None:
        user_model = get_user_model()

        email = options.get("email") or _env("ADMIN_EMAIL", "DJANGO_SUPERUSER_EMAIL")
        password = _env("ADMIN_PASSWORD", "DJANGO_SUPERUSER_PASSWORD")
        # The default Django user model logs in by username, not email, so the
        # email doubles as the username unless one is given explicitly.
        username = (
            options.get("username")
            or _env("ADMIN_USERNAME", "DJANGO_SUPERUSER_USERNAME")
            or email
        )

        if not username:
            raise CommandError(
                "No admin identity configured. Set ADMIN_EMAIL (or ADMIN_USERNAME)."
            )
        if not password:
            raise CommandError(
                "No admin password configured. Set ADMIN_PASSWORD "
                "(or DJANGO_SUPERUSER_PASSWORD). Nothing was changed."
            )

        with transaction.atomic():
            user, created = user_model.objects.get_or_create(
                **{user_model.USERNAME_FIELD: username},
                defaults={"email": email},
            )

            if created:
                user.set_password(password)
            elif not options.get("skip_password_update"):
                user.set_password(password)

            if email:
                user.email = email
            # Both flags matter: is_staff gates the admin JWT and the Django
            # admin site; is_superuser gates the IsAdminUser-protected API.
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.save()

        action = "Created" if created else "Updated"
        password_note = (
            "password left unchanged"
            if (not created and options.get("skip_password_update"))
            else "password set"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"{action} admin account '{username}' "
                f"(email={user.email or 'unset'}, {password_note}, "
                f"is_staff=True, is_superuser=True)."
            )
        )
        self.stdout.write(
            "Obtain a token with: POST /api/admin/auth/token/ "
            '{"username": "%s", "password": "<ADMIN_PASSWORD>"}' % username
        )
