#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! python -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.connect(('db', 5432))
    s.close()
except Exception:
    exit(1)
" 2>/dev/null; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 1
done
echo "PostgreSQL is up!"

echo "Running migrations..."
python manage.py makemigrations loans
python manage.py migrate

echo "Triggering data ingestion..."
python manage.py shell -c "
from celery import chain
from loans.tasks import ingest_customer_data, ingest_loan_data
chain(ingest_customer_data.si(), ingest_loan_data.si()).delay()
print('Data ingestion chain queued.')
"

echo "Starting server..."
exec python manage.py runserver 0.0.0.0:8000
