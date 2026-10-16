import threading

from celery import shared_task
from django.conf import settings
from django.db import connection

from .processor import process_document as process_document_sync


@shared_task
def process_document_task(document_id):
    return process_document_sync(document_id)


def _process_in_thread(document_id):
    try:
        process_document_sync(document_id)
    finally:
        connection.close()  # each thread gets its own DB connection; release it


def start_document_processing(document_id):
    """Celery when a broker (Redis) is configured; otherwise a background thread,
    so hosting without a worker (e.g. Render free) still processes uploads."""
    if settings.CELERY_BROKER_URL:
        process_document_task.delay(document_id)
    else:
        # ponytail: an in-process thread dies if the server restarts mid-processing
        # (document stays 'processing'); add Redis + a Celery worker if that matters.
        threading.Thread(target=_process_in_thread, args=(document_id,), daemon=True).start()
