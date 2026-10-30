import logging

from google.genai import errors as genai_errors
from django.conf import settings
from rag.vector_store import search_similar_chunks, gemini_call
from documents.models import Document

logger = logging.getLogger(__name__)

# Newest first; the next model is tried if one is unavailable to the key (e.g. not
# on its tier) or over its limit. gemini-2.5-* is closed to new API keys.
CHAT_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash"]
GROQ_MODEL = "openai/gpt-oss-120b"  # backup when Gemini fails (needs GROQ_API_KEY)
NO_ANSWER = "I couldn't generate an answer for that. Please try rephrasing your question."


def generate_answer(workspace_id, question, conversation_history=None):
    # Follow-ups like "tell me more" carry no topic of their own, so search with
    # the previous question too.
    previous = [m['content'] for m in (conversation_history or []) if m['role'] == 'user']
    search_query = f"{previous[-1]}\n{question}" if previous else question
    search_results = search_similar_chunks(workspace_id, search_query, n_results=5)

    if not search_results['documents'] or not search_results['documents'][0]:
        return {
            'answer': 'I could not find relevant information in the knowledge base to answer your question.',
            'sources': []
        }

    chunks = search_results['documents'][0]
    metadatas = search_results['metadatas'][0]

    # One source per document (in relevance order), with the passages used from it.
    docs = Document.objects.in_bulk({int(m['document_id']) for m in metadatas})
    sources_by_id = {}
    context = ""
    for chunk, meta in zip(chunks, metadatas):
        doc = docs.get(int(meta['document_id']))
        if not doc:
            continue
        context += f"\n[Source: {doc.title}]\n{chunk}\n"
        source = sources_by_id.setdefault(doc.id, {
            'document_id': doc.id,
            'title': doc.title,
            'file_type': doc.file_type,
            'excerpts': [],
        })
        source['excerpts'].append(chunk[:600])
    sources = list(sources_by_id.values())

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
- Be concise and helpful; use short paragraphs or bullet points
- Mention which sources (by document title) you used

Answer:"""

    return {
        'answer': _complete(prompt),
        'sources': sources
    }


def _complete(prompt):
    """Tries each Gemini model with every Gemini key (switching when one is over its
    limit), then every Groq key if GROQ_API_KEY is set. Re-raises the last error if
    nothing could answer."""
    for model in CHAT_MODELS:
        try:
            # retries=0: the user is waiting, so switch keys but never sleep for the quota.
            # .text is None when Gemini returns no text (e.g. blocked by safety filters).
            return gemini_call('generate_content', retries=0, model=model, contents=prompt).text or NO_ANSWER
        except genai_errors.APIError:
            if model == CHAT_MODELS[-1] and not settings.GROQ_API_KEYS:
                raise
            logger.warning("Gemini model %s failed, trying the next option", model, exc_info=True)
    from groq import Groq
    for i, key in enumerate(settings.GROQ_API_KEYS):
        try:
            completion = Groq(api_key=key).chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return completion.choices[0].message.content or NO_ANSWER
        except Exception:
            if i == len(settings.GROQ_API_KEYS) - 1:
                raise
            logger.warning("Groq key #%d failed, switching to the next key", i + 1, exc_info=True)
