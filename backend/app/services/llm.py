"""LLM service for summarization and query answering (Groq or Gemini)."""
from typing import Optional
from app.config import Config


def get_llm_client():
    """Return LLM client (Groq preferred for speed)."""
    if Config.GROQ_API_KEY:
        import groq
        return "groq", groq.Groq(api_key=Config.GROQ_API_KEY)
    if Config.GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        return "gemini", genai
    return None, None


_llm_type = None
_llm_client = None


def summarize_with_llm(
    prompt: str,
    system: Optional[str] = None,
    model_override: Optional[str] = None,
) -> str:
    """Generate summary or answer using configured LLM."""
    global _llm_type, _llm_client
    if _llm_client is None:
        _llm_type, _llm_client = get_llm_client()
    if _llm_client is None:
        return (
            "[No LLM configured. Set GROQ_API_KEY or GEMINI_API_KEY for summarization.]"
        )
    if _llm_type == "groq":
        model = model_override or Config.GROQ_MODEL
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        chat = _llm_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1024,
        )
        return chat.choices[0].message.content or ""
    if _llm_type == "gemini":
        model = _llm_client.GenerativeModel(
            model_override or Config.GEMINI_LLM_MODEL
        )
        full = (system or "") + "\n\n" + prompt if system else prompt
        response = model.generate_content(full)
        return response.text if response.text else ""
    return "[LLM not available]"
