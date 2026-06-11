"""
Local development settings.
"""
from .base import *  # noqa: F401, F403

DEBUG = True
DJANGO_VITE["default"]["dev_mode"] = True  # noqa: F405

INSTALLED_APPS += [  # noqa: F405
    "debug_toolbar",
    "django_browser_reload",
]

MIDDLEWARE += [  # noqa: F405
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

INTERNAL_IPS = ["127.0.0.1"]

# Use simpler static files storage for development
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
