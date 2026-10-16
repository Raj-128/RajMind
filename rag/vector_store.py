import numpy as np
from google import genai
from django.conf import settings

from documents.models import DocumentChunk

EMBEDDING_MODEL = "gemini-embedding-001"
EMBED_BATCH_SIZE = 100  # chunks per Gemini call

client_genai = genai.Client(api_key=settings.GEMINI_API_KEY)


def embed_texts(texts):
    vectors = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        result = client_genai.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts[start:start + EMBED_BATCH_SIZE],
        )
        vectors.extend(e.values for e in result.embeddings)
    return vectors


def get_embedding(text):
    return embed_texts([text])[0]


def store_chunks(workspace_id, document_id, chunks):
    """Embeds the document's chunks and saves the vectors on its DocumentChunk rows."""
    rows = list(DocumentChunk.objects.filter(document_id=document_id).order_by('chunk_index'))
    for row, vector in zip(rows, embed_texts([row.content for row in rows])):
        row.embedding = vector
    DocumentChunk.objects.bulk_update(rows, ['embedding'])
    return len(rows)


def search_similar_chunks(workspace_id, query, n_results=5):
    """Cosine-similarity search over a workspace's chunks.

    Returns the same shape Chroma did: {'documents': [[...]], 'metadatas': [[...]]}.
    """
    # ponytail: scans every chunk in the workspace per query (fine for thousands of
    # chunks); switch to pgvector if a workspace grows to hundreds of thousands.
    rows = list(
        DocumentChunk.objects.filter(
            document__workspace_id=workspace_id,
            document__status='completed',
            embedding__isnull=False,
        ).values('document_id', 'chunk_index', 'content', 'embedding')
    )
    if not rows:
        return {'documents': [[]], 'metadatas': [[]]}

    matrix = np.array([row['embedding'] for row in rows], dtype=np.float32)
    query_vector = np.array(get_embedding(query), dtype=np.float32)
    scores = matrix @ query_vector / (
        np.linalg.norm(matrix, axis=1) * np.linalg.norm(query_vector) + 1e-10
    )
    best = np.argsort(scores)[::-1][:n_results]

    return {
        'documents': [[rows[i]['content'] for i in best]],
        'metadatas': [[
            {'document_id': str(rows[i]['document_id']), 'chunk_index': rows[i]['chunk_index']}
            for i in best
        ]],
    }


def delete_document_chunks(workspace_id, document_id):
    # Vectors live on DocumentChunk rows, which are deleted with their document.
    DocumentChunk.objects.filter(document_id=document_id).delete()
