#!/bin/sh
set -e

# The worker container sets RUN_MIGRATIONS=0 so only the web container
# migrates (compose ordering makes the worker wait for a healthy web).
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python manage.py migrate --noinput

    # Create/update the admin from DJANGO_SUPERUSER_* (idempotent upsert, so
    # editing those vars and restarting actually updates the account).
    python manage.py ensure_admin
fi

exec "$@"
