"""
Configurações do Django para projeto majobfil - Otimizado para Railway
"""
import os
from pathlib import Path
import dj_database_url
from decouple import config
from django.core.management.utils import get_random_secret_key

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================
# SEGURANÇA (usando variáveis de ambiente)
# ============================================
# Gera uma chave secreta automaticamente se não existir (útil para deploy)
SECRET_KEY = config('SECRET_KEY', default=get_random_secret_key())

# DEBUG deve ser False em produção
DEBUG = config('DEBUG', default=False, cast=bool)

# Configuração de hosts permitidos
ALLOWED_HOSTS = config('ALLOWED_HOSTS', 
                      default='localhost,127.0.0.1,.up.railway.app,railway.app', 
                      cast=lambda v: [s.strip() for s in v.split(',')])

# Adiciona o host do Railway automaticamente se disponível
railway_host = config('RAILWAY_STATIC_URL', default='')
if railway_host and railway_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(railway_host)

# CSRF confiável para Railway
CSRF_TRUSTED_ORIGINS = [
    'https://*.up.railway.app',
    'https://*.railway.app',
]

if railway_host:
    CSRF_TRUSTED_ORIGINS.append(f'https://{railway_host}')

# Configurações de proxy (importante para Railway)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

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
    
    # Apps de terceiros
    'whitenoise.runserver_nostatic',  # Melhora performance em desenvolvimento
    
    # Seus apps
    'balanco',
    'conta',
    'lojas',
    'produtos',
    'relatorio',
]

# ============================================
# MIDDLEWARE (CORRIGIDO)
# ============================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Deve ser logo após SecurityMiddleware
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# CORREÇÃO: Verificar se o middleware customizado existe antes de adicionar
custom_middleware_path = 'majobfil.middleware.force_custom_errors.ForceCustomErrorsMiddleware'
try:
    # Tenta importar o middleware para verificar se existe
    import importlib
    module_path, class_name = custom_middleware_path.rsplit('.', 1)
    importlib.import_module(module_path)
    MIDDLEWARE.append(custom_middleware_path)
except (ImportError, ValueError):
    # Se não existir, ignora silenciosamente
    pass

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
# BANCO DE DADOS (CORRIGIDO)
# ============================================
# Configuração melhorada para Railway
DATABASE_URL = os.environ.get('DATABASE_URL')

if DATABASE_URL:
    # Estamos no Railway ou tem DATABASE_URL configurado
    DATABASES = {
        'default': dj_database_url.config(
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=True  # Railway requer SSL
        )
    }
else:
    # Desenvolvimento local com SQLite
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
            'OPTIONS': {
                'timeout': 20,  # Timeout maior para evitar locks
            }
        }
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
USE_TZ = True

# ============================================
# ARQUIVOS ESTÁTICOS (CORRIGIDO E OTIMIZADO)
# ============================================
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',  # Se você tiver uma pasta static na raiz
]

# Configuração do WhiteNoise para arquivos estáticos
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
# ADMIN INTERFACE
# ============================================
X_FRAME_OPTIONS = 'SAMEORIGIN'
SILENCED_SYSTEM_CHECKS = ['security.W019']

# ============================================
# SEGURANÇA EM PRODUÇÃO (CORRIGIDO)
# ============================================
if not DEBUG:
    # Configurações de segurança para produção
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    
    # HSTS - apenas se tiver certeza que tudo é HTTPS
    SECURE_HSTS_SECONDS = 31536000  # 1 ano
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    
    # Outras configurações de segurança
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    SESSION_COOKIE_HTTPONLY = True
    CSRF_COOKIE_HTTPONLY = True
else:
    # Em desenvolvimento, não forçar HTTPS
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False

# ============================================
# CONFIGURAÇÕES DE LOG (ÚTIL PARA DEBUG NO RAILWAY)
# ============================================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': config('DJANGO_LOG_LEVEL', default='INFO'),
            'propagate': False,
        },
    },
}

# ============================================
# DEFAULT PRIMARY KEY
# ============================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ============================================
# CONFIGURAÇÕES ESPECÍFICAS DO RAILWAY
# ============================================
# Porta para o Railway (importante!)
PORT = config('PORT', default=8000, cast=int)

# Se estiver no Railway, configurações adicionais
if 'RAILWAY_ENVIRONMENT' in os.environ:
    # Ajustes específicos para o ambiente Railway
    CSRF_TRUSTED_ORIGINS.append(f'https://{os.environ.get("RAILWAY_STATIC_URL")}')
    
    # Configuração adicional de banco de dados para Railway
    if DATABASE_URL and 'sslrootcert' not in DATABASE_URL:
        # Forçar SSL para conexão com PostgreSQL no Railway
        DATABASES['default']['OPTIONS'] = {
            'sslmode': 'require'
        }