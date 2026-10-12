"""Django settings pour grocery_store.

Stack : Python 3.14, Django 5, PostgreSQL 16 UNIQUEMENT.
Aucun SQLite, aucun npm, aucun framework JS.
Style : Tailwind CDN. Serveur interactif : HTMX. État local : Alpine.js.
"""

from pathlib import Path

from decouple import Csv, config
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------------
# Sécurité / debug via .env (python-decouple)
# ------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY")
DEBUG = config("DEBUG", default=False, cast=bool)
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="127.0.0.1,localhost", cast=Csv())
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="http://127.0.0.1:8000,http://localhost:8000",
    cast=Csv(),
)

# ------------------------------------------------------------------
# Base de données : PostgreSQL 16 OBLIGATOIRE via DATABASE_URL
# Ex : postgres://grocery_user:grocery_pass_123@127.0.0.1:5432/grocery_db
# Jamais de fallback SQLite : on échoue vite si mal configuré.
# ------------------------------------------------------------------
DATABASE_URL = config("DATABASE_URL", default="")

if not DATABASE_URL:
    raise ImproperlyConfigured(
        "DATABASE_URL manquante dans .env. "
        "Exemple : postgres://grocery_user:grocery_pass_123@127.0.0.1:5432/grocery_db"
    )

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=600,
        conn_health_checks=True,
    )
}

engine = DATABASES["default"].get("ENGINE", "")
if engine not in ("django.db.backends.postgresql", "django.db.backends.postgresql_psycopg2"):
    raise ImproperlyConfigured(
        f"ENGINE Postgres exigé, reçu : {engine!r}. SQLite est interdit."
    )

# psycopg v3 : pas d'adaptateur psycopg2, Django 5 utilise psycopg natif.
# Rien à importer ici, la dépendance psycopg[binary] suffit.

# ------------------------------------------------------------------
# Applications
# ------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # SearchVector, Trigram, ArrayField, JSONField avancé
    # Tierces
    "crispy_forms",
    "crispy_tailwind",
    "django_htmx",
    # Locale
    "store",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "store.context_processors.cart_count",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# ------------------------------------------------------------------
# Auth / i18n
# ------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "store.validators.ComplexPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Africa/Casablanca"
USE_I18N = True
USE_TZ = True

LOGIN_URL = "store:login"
LOGIN_REDIRECT_URL = "store:product_list"
LOGOUT_REDIRECT_URL = "store:product_list"

# Auth : email d'abord, pseudo en repli (admin garde son login habituel)
AUTHENTICATION_BACKENDS = [
    "store.backends.EmailBackend",
    "django.contrib.auth.backends.ModelBackend",
]

# ------------------------------------------------------------------
# Statiques & médias (WhiteNoise, sans npm)
# ------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------
# Crispy + Tailwind (rendu formulaires)
# ------------------------------------------------------------------
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# ------------------------------------------------------------------
# HTMX : le CSRF est envoyé via en-tête X-CSRFToken.
# Voir templates/base.html : htmx:configRequest ajoute le token.
# django-htmx expose request.htmx pour brancher les fragments "_".
# ------------------------------------------------------------------
CSRF_COOKIE_HTTPONLY = False  # JS doit lire csrftoken pour HTMX
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # panier anonyme 7 jours
