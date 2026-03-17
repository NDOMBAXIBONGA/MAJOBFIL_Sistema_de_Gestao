"""
Django settings for majobfil project - Configurado para Railway
"""
import os
from pathlib import Path
import dj_database_url
from decouple import config  # Para ler .env facilmente

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================
# SEGURANÇA (usando variáveis de ambiente)
# ============================================
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production')
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,.up.railway.app').split(',')

CSRF_TRUSTED_ORIGINS = [
    'https://*.up.railway.app',
]

if not DEBUG:
    CSRF_TRUSTED_ORIGINS.append('https://' + config('RAILWAY_STATIC_URL', ''))
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ============================================
# APLICAÇÕES INSTALADAS
# ============================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Seus apps
    'balanco',
    'conta',
    'lojas',
    'produtos',
    'relatorio',
]

# ============================================
# MIDDLEWARE (ordem correta é importante!)
# ============================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # ESSENCIAL: para arquivos estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'majobfil.middleware.force_custom_errors.ForceCustomErrorsMiddleware',
]

# ============================================
# URLs E TEMPLATES
# ============================================
ROOT_URLCONF = 'majobfil.urls'

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
                'conta.context_processors.estatisticas_relatorios',
                'conta.context_processors.atividades_recentes_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'majobfil.wsgi.application'

# ============================================
# BANCO DE DADOS (Configuração Inteligente)
# ============================================
# No Railway: usa PostgreSQL automaticamente via DATABASE_URL
# Localmente: usa SQLite (sem precisar instalar PostgreSQL)
DATABASES = {
    'default': dj_database_url.config(
        default='sqlite:///' + str(BASE_DIR / 'db.sqlite3'),
        conn_max_age=600,
        conn_health_checks=True,
    )
}

# ============================================
# VALIDAÇÃO DE SENHAS
# ============================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ============================================
# INTERNACIONALIZAÇÃO
# ============================================
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'Africa/Luanda'
USE_I18N = True
USE_L10N = True
USE_TZ = True

# ============================================
# ARQUIVOS ESTÁTICOS (ESSENCIAL PARA O RAILWAY)
# ============================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Arquivos de mídia (uploads)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ============================================
# AUTENTICAÇÃO
# ============================================
AUTH_USER_MODEL = 'conta.Conta'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# ============================================
# ADMIN INTERFACE (se for usar)
# ============================================
X_FRAME_OPTIONS = 'SAMEORIGIN'
SILENCED_SYSTEM_CHECKS = ['security.W019']

# ============================================
# CONFIGURAÇÕES ADICIONAIS DE SEGURANÇA (PRODUÇÃO)
# ============================================
if not DEBUG:
    # Sessões seguras (só se tiver HTTPS)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# ============================================
# DEFAULT PRIMARY KEY
# ============================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'