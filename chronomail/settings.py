import logging
import os
from pathlib import Path
from dotenv import load_dotenv
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Создание необходимых директорий при запуске
def create_directories():
    """Создание необходимых директорий для приложения"""
    directories = [
        BASE_DIR / 'logs',
        BASE_DIR / 'static',
        BASE_DIR / 'media/attachments',
        BASE_DIR / 'media/uploads',
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"Проверка/создание директории: {directory}")

create_directories()

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', 'django-insecure-your-secret-key-here-change-in-production')

# Определяем, находимся ли мы на Railway
IS_RAILWAY = 'RAILWAY_ENVIRONMENT' in os.environ or 'RAILWAY_STATIC_URL' in os.environ
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true' and not IS_RAILWAY

# ALLOWED_HOSTS для Railway и локальной разработки
if IS_RAILWAY:
    ALLOWED_HOSTS = ['*']  # На Railway разрешаем все хосты
    CSRF_TRUSTED_ORIGINS = [
        'https://chronomailproject-production.up.railway.app',
        'https://*.railway.app',
        'https://*.up.railway.app',
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ]
else:
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
        'https://localhost',
    ]

# Настройки безопасности для продакшена
if not DEBUG or IS_RAILWAY:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# Trusted origins (дополняем)
CSRF_TRUSTED_ORIGINS.extend([
    'https://*.railway.app',
    'https://*.onrender.com',
])

# Приложения
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'whitenoise.runserver_nostatic',  # Для разработки с whitenoise
    
    # Третьи стороны
    'django_otp',
    'django_otp.plugins.otp_totp',
    'django_otp.plugins.otp_static',
    'two_factor',
    'ckeditor',
    'ckeditor_uploader',
    'rest_framework',
    'rest_framework.authtoken',
    'corsheaders',
    'django_cleanup.apps.CleanupConfig',
    
    # Локальные приложения
    'core',
]

# Middleware - УПРОЩЕННАЯ ВЕРСИЯ для отладки
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Временно отключаем OTP и IP фильтр для отладки
    # 'django_otp.middleware.OTPMiddleware',
    # 'two_factor.middleware.threadlocals.ThreadLocals',
    # 'core.middleware.IPFilterMiddleware',
]

ROOT_URLCONF = 'chronomail.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# Database - Railway предоставляет DATABASE_URL
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL:
    DATABASES = {
        'default': dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Для favicon - добавляем статический файл
# Создайте файл в static/favicon.ico или добавьте в STATICFILES_DIRS

# Настройки WhiteNoise для Railway
if IS_RAILWAY:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'
else:
    STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Настройки пользователя
AUTH_USER_MODEL = 'core.CustomUser'

# 2FA настройки - ОТКЛЮЧАЕМ для админки
TWO_FACTOR_PATCH_ADMIN = False  # Отключаем 2FA в админке
TWO_FACTOR_LOGIN_TIMEOUT = 300
TWO_FACTOR_REMEMBER_COOKIE_AGE = 60*60*24*30
TWO_FACTOR_QR_FACTORY = 'qrcode.image.pil.PilImage'

# CORS настройки
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://chronomailproject-production.up.railway.app",
]

CORS_ALLOW_CREDENTIALS = True

# REST Framework настройки
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/day',
        'user': '1000/day',
    },
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
}

# Encryption key
FERNET_KEY = os.getenv('FERNET_KEY', 'your-fernet-key-here-change-in-production')

# НАСТРОЙКИ БЕЗОПАСНОСТИ - ИСПРАВЛЕННЫЕ
# Временно отключаем IP фильтрацию для отладки
ALLOWED_IPS = []
BLOCKED_IPS = []

RATE_LIMIT = {
    'requests': 1000,  # Увеличиваем лимит для отладки
    'period': 60,
}

# Email settings
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', 587))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() == 'true'
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'webmaster@localhost')

# CKEditor настройки
CKEDITOR_UPLOAD_PATH = "uploads/"
CKEDITOR_IMAGE_BACKEND = "pillow"
CKEDITOR_CONFIGS = {
    'default': {
        'toolbar': 'Custom',
        'toolbar_Custom': [
            ['Bold', 'Italic', 'Underline'],
            ['NumberedList', 'BulletedList'],
            ['Link', 'Unlink'],
            ['Image', 'Table'],
            ['RemoveFormat', 'Source']
        ],
        'height': 300,
        'width': '100%',
        'extraPlugins': ','.join([
            'uploadimage',
            'div',
            'autolink',
            'autoembed',
            'embedsemantic',
            'autogrow',
            'widget',
            'lineutils',
            'clipboard',
            'dialog',
            'dialogui',
            'elementspath'
        ]),
    },
}

# Sentry конфигурация
SENTRY_DSN = os.getenv('SENTRY_DSN')
if SENTRY_DSN and (not DEBUG or IS_RAILWAY):
    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[
            DjangoIntegration(
                transaction_style='url',
                middleware_spans=True,
                signals_spans=False,
                cache_spans=False,
            ),
            LoggingIntegration(
                level=logging.INFO,
                event_level=logging.ERROR
            ),
        ],
        traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', 0.1)),
        profiles_sample_rate=float(os.getenv('SENTRY_PROFILES_SAMPLE_RATE', 0.1)),
        send_default_pii=True,
        environment='railway' if IS_RAILWAY else os.getenv('ENVIRONMENT', 'development'),
        release=f"chronomail@{os.getenv('VERSION', '1.0.0')}",
        ignore_errors=[
            'django.http.response.Http404',
            'django.core.exceptions.PermissionDenied',
        ]
    )

# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    
    'handlers': {
        'console': {
            'level': 'DEBUG',  # Изменено на DEBUG для отладки
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'DEBUG',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/chronomail.log',
            'maxBytes': 1024*1024*10,  # 10 MB
            'backupCount': 10,
            'formatter': 'verbose',
        },
        'error_file': {
            'level': 'ERROR',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs/errors.log',
            'maxBytes': 1024*1024*10,
            'backupCount': 10,
            'formatter': 'verbose',
        },
    },
    
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console', 'error_file'],
            'level': 'DEBUG',  # Изменено на DEBUG
            'propagate': False,
        },
        'django.db.backends': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'core': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

# Cache configuration
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Для Railway - дополнительные настройки
if IS_RAILWAY:
    # Автоматически определяем домен Railway
    RAILWAY_STATIC_URL = os.getenv('RAILWAY_STATIC_URL', '')
    if RAILWAY_STATIC_URL:
        STATIC_URL = RAILWAY_STATIC_URL + '/static/'
    
    # Увеличиваем максимальный размер файла для загрузки
    DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
    
    # Отключаем DEBUG на Railway
    DEBUG = False
    
    # Настройки WhiteNoise для продакшена
    WHITENOISE_MAX_AGE = 31536000  # 1 year
