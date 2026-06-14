from google import genai
from django.conf import settings
from rag.vector_store import search_similar_chunks
from documents.models import Document

client_genai = genai.Client(api_key=settings.GEMINI_API_KEY)


def generate_answer(workspace_id, question, conversation_history=None):
    # Search relevant chunks
    search_results = search_similar_chunks(workspace_id, question, n_results=5)

    if not search_results['documents'] or not search_results['documents'][0]:
        return {
            'answer': 'I could not find relevant information in the knowledge base to answer your question.',
            'sources': []
        }

    # Build context from chunks
    chunks = search_results['documents'][0]
    metadatas = search_results['metadatas'][0]

    context = ""
    source_doc_ids = set()

    for i, chunk in enumerate(chunks):
        context += f"\n[Source {i+1}]:\n{chunk}\n"
        source_doc_ids.add(int(metadatas[i]['document_id']))

    # Get source document titles
    sources = []
    for doc_id in source_doc_ids:
        try:
            doc = Document.objects.get(id=doc_id)
            sources.append({
                'document_id': doc_id,
                'title': doc.title,
                'file_type': doc.file_type
            })
        except Document.DoesNotExist:
            pass

    # Build conversation history string
    history_text = ""
    if conversation_history:
        for msg in conversation_history[-6:]:  # Last 6 messages for context
            role = "User" if msg['role'] == 'user' else "Assistant"
            history_text += f"{role}: {msg['content']}\n"

    # Build prompt
    prompt = f"""You are an intelligent knowledge assistant. Answer the user's question based ONLY on the provided context.

Context from knowledge base:
{context}

Previous conversation:
{history_text}

User question: {question}

Instructions:
- Answer based only on the context provided
- If the answer is not in the context, say so clearly
- Be concise and helpful
- Mention which sources you used

Answer:"""

    response = client_genai.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    return {
        'answer': response.text,
        'sources': sources
    }