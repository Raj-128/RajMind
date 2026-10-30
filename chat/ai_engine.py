import logging

from google.genai import errors as genai_errors, types as genai_types
from django.conf import settings
from rag.vector_store import search_similar_chunks, gemini_call
from documents.models import Document

logger = logging.getLogger(__name__)

# Newest first; the next model is tried if one is unavailable to the key (e.g. not
# on its tier) or over its limit. gemini-2.5-* is closed to new API keys.
CHAT_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash"]
_unavailable_models = set()  # filled at runtime; reset on each deploy/restart
GROQ_MODEL = "openai/gpt-oss-120b"  # answers first when GROQ_API_KEY is set (fastest)
# Gemini 3.x "thinks" before answering (medium by default), which adds seconds per
# answer. Retrieval already supplies the facts, so low thinking is enough.
FAST_ANSWERS = genai_types.GenerateContentConfig(
    thinking_config=genai_types.ThinkingConfig(thinking_level='low'),
)
NO_ANSWER = "I couldn't generate an answer for that. Please try rephrasing your question."


def generate_answer(workspace_id, question, conversation_history=None):
    # Follow-ups like "tell me more" carry no topic of their own, so search with
    # the previous question too.
    previous = [m['content'] for m in (conversation_history or []) if m['role'] == 'user']
    search_query = f"{previous[-1]}\n{question}" if previous else question
    search_results = search_similar_chunks(workspace_id, search_query, n_results=5)

    if not search_results['documents'] or not search_results['documents'][0]:
        return {
            # Search only comes back empty when nothing in the workspace is indexed yet.
            'answer': 'This workspace has no indexed documents yet. Upload a document in the '
                      'Documents tab and wait until it shows "completed", then ask again.',
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
    """Groq first (typically ~1s, vs several seconds for Gemini), trying every Groq
    key; then each Gemini model with every Gemini key. Re-raises the last error if
    nothing could answer."""
    from groq import Groq
    for i, key in enumerate(settings.GROQ_API_KEYS):
        try:
            # max_retries=0: on a rate limit, move to the next key/provider instead of
            # waiting and retrying while the user waits.
            completion = Groq(api_key=key, max_retries=0, timeout=30).chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return completion.choices[0].message.content or NO_ANSWER
        except Exception:
            logger.warning("Groq key #%d failed, trying the next option", i + 1, exc_info=True)

    available = [m for m in CHAT_MODELS if m not in _unavailable_models] or CHAT_MODELS
    for model in available:
        try:
            # retries=0: the user is waiting, so switch keys but never sleep for the quota.
            # .text is None when Gemini returns no text (e.g. blocked by safety filters).
            return gemini_call('generate_content', retries=0, model=model, contents=prompt, config=FAST_ANSWERS).text or NO_ANSWER
        except genai_errors.APIError as e:
            if e.code in (400, 404):
                # Model not offered to these keys: stop trying it first on every question.
                _unavailable_models.add(model)
            if model == available[-1]:
                raise
            logger.warning("Gemini model %s failed, trying the next option", model, exc_info=True)
