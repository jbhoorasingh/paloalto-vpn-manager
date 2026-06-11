#!/bin/sh
set -e

# The worker container sets RUN_MIGRATIONS=0 so only the web container
# migrates (compose ordering makes the worker wait for a healthy web).
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python manage.py migrate --noinput

    # Optional first-boot admin: set DJANGO_SUPERUSER_USERNAME/EMAIL/PASSWORD
    if [ -n "${DJANGO_SUPERUSER_USERNAME}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD}" ]; then
        python manage.py createsuperuser --noinput 2>/dev/null || true
    fi
fi

exec "$@"
