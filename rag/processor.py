import logging

from documents.models import Document, DocumentChunk
from .text_extractor import extract_text_from_file
from .chunker import chunk_text
from .vector_store import store_chunks

logger = logging.getLogger(__name__)


def _fail(document_id, message):
    Document.objects.filter(id=document_id).update(status='failed', error_message=message[:500])
    return False


def process_document(document_id):
    try:
        document = Document.objects.get(id=document_id)
        document.status = 'processing'
        document.error_message = ''
        document.save()

        # Extract text
        file_path = document.file.path
        text = extract_text_from_file(file_path, document.file_type)

        if not text:
            return _fail(document_id, 'No readable text found. Scanned/image-only PDFs are not supported.')

        # Chunk text
        chunks = chunk_text(text)

        # Store chunk rows in PostgreSQL, then their embeddings
        DocumentChunk.objects.filter(document=document).delete()

        DocumentChunk.objects.bulk_create([
            DocumentChunk(
                document=document,
                chunk_index=i,
                content=chunk_content,
                embedding_id=f"doc_{document_id}_chunk_{i}"
            )
            for i, chunk_content in enumerate(chunks)
        ])

        store_chunks(document.workspace.id, document_id, chunks)

        document.status = 'completed'
        document.save()
        return True

    except Exception as e:
        logger.exception("Error processing document %s", document_id)
        if isinstance(e, FileNotFoundError):
            reason = 'The uploaded file is no longer on the server. Please upload it again.'
        elif '429' in str(e):
            reason = 'AI usage limit reached while indexing. Click Retry in a minute.'
        else:
            reason = 'Processing failed. Click Retry, or upload the file again.'
        return _fail(document_id, reason)
