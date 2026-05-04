import os
from pathlib import Path
from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", get_random_secret_key())
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
DJANGO_DB_ENGINE = os.getenv("DJANGO_DB_ENGINE", "sqlite")
DEBUG = os.getenv("DEBUG", "False") == "True"

# In production set ALLOWED_HOSTS to your actual domain(s), e.g. "ekioba.com,*.run.app"
_raw_hosts = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1" if not DEBUG else "*")
ALLOWED_HOSTS = [h.strip() for h in _raw_hosts.split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "core",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "store_service.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "store_service.wsgi.application"
ASGI_APPLICATION = "store_service.asgi.application"


def _database_config_from_env() -> dict[str, object]:
    db_engine = DJANGO_DB_ENGINE

    # SQLite — tests and local dev only
    if db_engine == "sqlite":
        sqlite_name = DATABASE_URL.replace("sqlite:///", "", 1)
        if not os.path.isabs(sqlite_name):
            sqlite_name = str(BASE_DIR / sqlite_name)
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": os.getenv("SQLITE_DB_PATH", sqlite_name),
        }

    # Azure SQL Managed Instance / Azure SQL Database
    if db_engine == "mssql":
        return {
            "ENGINE": "mssql",
            "NAME": os.getenv("AZURE_SQL_STORE_DB", "ekioba_store"),
            "USER": os.getenv("AZURE_SQL_USER", ""),
            "PASSWORD": os.getenv("AZURE_SQL_PASSWORD", ""),
            "HOST": os.getenv("AZURE_SQL_HOST", ""),
            "PORT": os.getenv("AZURE_SQL_PORT", "1433"),
            "OPTIONS": {
                "driver": "ODBC Driver 18 for SQL Server",
                "extra_params": "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30",
            },
        }

    # PostgreSQL — legacy / non-Azure fallback
    database_url = DATABASE_URL
    if not database_url:
        return {
            "ENGINE": db_engine,
            "NAME": "ekioba_store",
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": "",
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": int(os.getenv("DB_PORT", "5432")),
            "OPTIONS": {"sslmode": os.getenv("DB_SSLMODE", "disable")},
        }

    parsed = urlparse(database_url)
    query = parse_qs(parsed.query)
    sslmode = query.get("sslmode", ["require"])[0]
    return {
        "ENGINE": db_engine,
        "NAME": parsed.path.lstrip("/") or "ekioba_store",
        "USER": parsed.username or "postgres",
        "PASSWORD": parsed.password or "",
        "HOST": parsed.hostname or "localhost",
        "PORT": parsed.port or 5432,
        "OPTIONS": {"sslmode": sslmode},
    }


DATABASES = {"default": _database_config_from_env()}


REDIS_URL = os.getenv("REDIS_URL", "")
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
            },
            "TIMEOUT": 300,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "store-local-cache",
            "TIMEOUT": 300,
        }
    }

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "None"
CSRF_COOKIE_SAMESITE = "None"

# Security & Proxy Configuration
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True
CSRF_TRUSTED_ORIGINS = ["https://*.run.app", "https://ekioba.com"]

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# JWT Configuration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=1),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "SIGNING_KEY": SECRET_KEY,
}

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.run\.app$",
]
