from .settings import *  # noqa: F401,F403

# Use local in-memory sqlite for deterministic tests.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
