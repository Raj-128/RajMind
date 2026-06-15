from celery import shared_task
from .processor import process_document as process_document_sync


@shared_task
def process_document_task(document_id):
    return process_document_sync(document_id)