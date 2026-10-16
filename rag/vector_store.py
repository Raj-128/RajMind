import re
import time

import numpy as np
from google import genai
from google.genai import errors as genai_errors
from django.conf import settings

from documents.models import DocumentChunk

EMBEDDING_MODEL = "gemini-embedding-001"
# Free-tier keys reject ~100 chunks per request (429 RESOURCE_EXHAUSTED); 20 fits.
EMBED_BATCH_SIZE = 20
MAX_RATE_LIMIT_RETRIES = 6

client_genai = genai.Client(api_key=settings.GEMINI_API_KEY)


def call_with_rate_limit_retry(fn, *args, retries=MAX_RATE_LIMIT_RETRIES, **kwargs):
    """Calls a Gemini API function, waiting and retrying when the per-minute quota
    is hit (HTTP 429), so large documents slow down instead of failing."""
    for attempt in range(retries + 1):
        try:
            return fn(*args, **kwargs)
        except genai_errors.ClientError as e:
            if e.code != 429 or attempt == retries:
                raise
            # Gemini says how long to wait, e.g. "retryDelay': '23s'"; default 20s.
            match = re.search(r"retryDelay'?:\s*'(\d+)", str(e))
            time.sleep(int(match.group(1)) + 1 if match else 20)


def embed_texts(texts, retries=MAX_RATE_LIMIT_RETRIES):
    vectors = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        result = call_with_rate_limit_retry(
            client_genai.models.embed_content,
            model=EMBEDDING_MODEL,
            contents=texts[start:start + EMBED_BATCH_SIZE],
            retries=retries,
        )
        vectors.extend(e.values for e in result.embeddings)
    return vectors


def get_embedding(text):
    # Used while a user waits for an answer: one retry at most, not minutes of waiting.
    return embed_texts([text], retries=1)[0]


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
