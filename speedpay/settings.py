import sys
from os import getenv
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(".env")

ENVIRONMENT = getenv(
    "ENVIRONMENT", "test" if any("pytest" in a for a in sys.argv) else "development"
)

SECRET_KEY = getenv("SECRET_KEY")
DEBUG = getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "ninja",
    "api",
]

MIDDLEWARE = [
    "api.middleware.SecurityHeadersMiddleware",
    "api.middleware.RateLimitMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "speedpay.urls"

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

WSGI_APPLICATION = "speedpay.wsgi.application"

DATABASE_URL = getenv("DATABASE_URL")
if DATABASE_URL:
    DATABASES = {"default": dj_database_url.parse(DATABASE_URL)}
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": getenv("DB_NAME"),
            "USER": getenv("DB_USER"),
            "PASSWORD": getenv("DB_PASSWORD"),
            "HOST": getenv("DB_HOST", "localhost"),
            "PORT": getenv("DB_PORT", "5432"),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Africa/Lagos"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

AUTH_USER_MODEL = "api.User"

DATA_UPLOAD_MAX_MEMORY_SIZE = 1_048_576

PAYSTACK_SECRET_KEY = getenv("PAYSTACK_SECRET_KEY")
PAYSTACK_PUBLIC_KEY = getenv("PAYSTACK_PUBLIC_KEY")
CALLBACK_URL = getenv(
    "CALLBACK_URL",
    "http://localhost:8000/docs",
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        }
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "api": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

if ENVIRONMENT == "test":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "test_speedpay.sqlite3",
        }
    }
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    SECRET_KEY = "test-secret-key-for-speedpay-tests"
    PAYSTACK_SECRET_KEY = "sk_test_placeholder"
    PAYSTACK_PUBLIC_KEY = "pk_test_placeholder"
