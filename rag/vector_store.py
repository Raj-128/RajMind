import time

import chromadb
from google import genai
from google.genai import types
from django.conf import settings

client_genai = genai.Client(api_key=settings.GEMINI_API_KEY)
client = chromadb.PersistentClient(path="./chromadb_store")


def get_or_create_collection(workspace_id):
    collection_name = f"workspace_{workspace_id}"
    return client.get_or_create_collection(name=collection_name)


def get_embedding(text):
    result = client_genai.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
    )
    return result.embeddings[0].values


def store_chunks(workspace_id, document_id, chunks):
    collection = get_or_create_collection(workspace_id)

    ids = []
    embeddings = []
    documents = []
    metadatas = []

    for i, chunk in enumerate(chunks):
        chunk_id = f"doc_{document_id}_chunk_{i}"
        embedding = get_embedding(chunk)
        time.sleep(1)

        ids.append(chunk_id)
        embeddings.append(embedding)
        documents.append(chunk)
        metadatas.append({
            "document_id": str(document_id),
            "chunk_index": i
        })

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas
    )

    return len(chunks)


def search_similar_chunks(workspace_id, query, n_results=5):
    collection = get_or_create_collection(workspace_id)

    query_embedding = client_genai.models.embed_content(
        model="gemini-embedding-001",
        contents=query,
    ).embeddings[0].values

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )

    return results


def delete_document_chunks(workspace_id, document_id):
    collection = get_or_create_collection(workspace_id)
    results = collection.get(where={"document_id": str(document_id)})
    if results['ids']:
        collection.delete(ids=results['ids'])