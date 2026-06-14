from documents.models import Document, DocumentChunk
from .text_extractor import extract_text_from_file
from .chunker import chunk_text
from .vector_store import store_chunks
import os


def process_document(document_id):
    try:
        document = Document.objects.get(id=document_id)
        document.status = 'processing'
        document.save()

        # Extract text
        file_path = document.file.path
        text = extract_text_from_file(file_path, document.file_type)

        if not text:
            document.status = 'failed'
            document.save()
            return False

        # Chunk text
        chunks = chunk_text(text)

        # Store in ChromaDB and PostgreSQL
        DocumentChunk.objects.filter(document=document).delete()

        for i, chunk_content in enumerate(chunks):
            DocumentChunk.objects.create(
                document=document,
                chunk_index=i,
                content=chunk_content,
                embedding_id=f"doc_{document_id}_chunk_{i}"
            )

        # Store embeddings in ChromaDB
        store_chunks(document.workspace.id, document_id, chunks)

        document.status = 'completed'
        document.save()
        return True

    except Exception as e:
        print(f"Error processing document {document_id}: {e}")
        try:
            document = Document.objects.get(id=document_id)
            document.status = 'failed'
            document.save()
        except:
            pass
        return False