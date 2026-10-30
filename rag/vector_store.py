import logging
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

# GEMINI_API_KEY may hold several comma-separated keys (e.g. from different Google
# accounts). When one hits its quota or stops working, calls switch to the next.
gemini_clients = [genai.Client(api_key=key) for key in settings.GEMINI_API_KEYS]
_active_key = 0  # index of the key that last worked; later calls start there

logger = logging.getLogger(__name__)


def _should_switch_key(e):
    # 429 = quota/limit exceeded; 401/403 or API_KEY_INVALID = key revoked or wrong.
    return e.code in (401, 403, 429) or 'API_KEY_INVALID' in str(e)


def gemini_call(method, retries=MAX_RATE_LIMIT_RETRIES, **kwargs):
    """Calls client.models.<method> (e.g. 'embed_content'), trying each Gemini key in
    turn. Only when every key is over its limit does it wait for the per-minute quota
    to reset and try again, so large documents slow down instead of failing."""
    global _active_key
    for attempt in range(retries + 1):
        for _ in range(len(gemini_clients)):
            try:
                return getattr(gemini_clients[_active_key].models, method)(**kwargs)
            except genai_errors.ClientError as e:
                if not _should_switch_key(e):
                    raise
                last_error = e
                if len(gemini_clients) > 1:
                    logger.warning("Gemini key #%d failed (%s), switching to the next key", _active_key + 1, e.code)
                _active_key = (_active_key + 1) % len(gemini_clients)
        if last_error.code != 429 or attempt == retries:
            raise last_error
        # Gemini says how long to wait, e.g. "retryDelay': '23s'"; default 20s.
        match = re.search(r"retryDelay'?:\s*'(\d+)", str(last_error))
        time.sleep(int(match.group(1)) + 1 if match else 20)


def embed_texts(texts, retries=MAX_RATE_LIMIT_RETRIES):
    vectors = []
    for start in range(0, len(texts), EMBED_BATCH_SIZE):
        result = gemini_call(
            'embed_content',
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
