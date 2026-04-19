# ai_providers.py

import os
import json
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


def get_providers_status() -> dict:
    return {
        "mistral":   bool(os.getenv("MISTRAL_API_KEY")),
        "openai":    bool(os.getenv("OPENAI_API_KEY")),
        "anthropic": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


def _call_mistral(system_prompt: str, user_prompt: str, model: str = "mistral-small-latest") -> str:
    from mistralai import Mistral
    client = Mistral(api_key=os.getenv("MISTRAL_API_KEY"))
    r = client.chat.complete(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.1, max_tokens=2000,
    )
    return r.choices[0].message.content.strip()


def _call_openai_json(system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini") -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.1, max_tokens=2000,
        response_format={"type": "json_object"},
    )
    return r.choices[0].message.content.strip()


def _call_openai_text(system_prompt: str, user_prompt: str, model: str = "gpt-4o-mini") -> str:
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    r = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
        temperature=0.5, max_tokens=800,
    )
    return r.choices[0].message.content.strip()


def _call_anthropic(system_prompt: str, user_prompt: str, model: str = "claude-sonnet-4-6") -> str:
    import anthropic
    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    r = client.messages.create(
        model=model, max_tokens=2000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.1,
    )
    return r.content[0].text.strip()


def _clean_json_response(raw: str) -> str:
    """Nettoie la reponse IA pour extraire le JSON valide."""
    cleaned = raw.strip()
    # Retire les balises markdown
    if cleaned.startswith("```"):
        lines   = cleaned.split("\n")
        start   = 1 if lines[0].startswith("```") else 0
        end     = len(lines) - 1 if lines[-1].strip() == "```" else len(lines)
        cleaned = "\n".join(lines[start:end]).strip()
    # Trouve le premier { et le dernier } pour isoler le JSON
    start_idx = cleaned.find("{")
    end_idx   = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1:
        cleaned = cleaned[start_idx:end_idx + 1]
    return cleaned


def call_ai_json(system_prompt: str, user_prompt: str,
                 preferred_provider: str = "mistral", model: Optional[str] = None) -> tuple:
    status     = get_providers_status()
    order      = [preferred_provider] + [p for p in ["mistral", "openai", "anthropic"] if p != preferred_provider]
    last_error = None

    for provider in order:
        if not status.get(provider):
            continue
        try:
            if provider == "mistral":
                raw = _call_mistral(system_prompt, user_prompt, *([model] if model else []))
            elif provider == "openai":
                raw = _call_openai_json(system_prompt, user_prompt, *([model] if model else []))
            else:
                raw = _call_anthropic(system_prompt, user_prompt, *([model] if model else []))

            cleaned = _clean_json_response(raw)
            return json.loads(cleaned), provider

        except json.JSONDecodeError as e:
            last_error = ValueError(f"JSON invalide ({provider}): {e} — reponse: {raw[:200]}")
        except Exception as e:
            last_error = e

    raise RuntimeError(f"Tous les providers ont echoue : {last_error}")


def generate_contact_message(contact: dict, context: str, channel: str = "email") -> tuple:
    from config import MESSAGE_SYSTEM_PROMPT, MESSAGE_USER_TEMPLATE

    prenom   = contact.get("prenom") or "Madame/Monsieur"
    poste    = contact.get("poste") or "consultant"
    domaines = ", ".join(contact.get("domaines_fonctionnels", [])) or "non precise"

    user_prompt = MESSAGE_USER_TEMPLATE.format(
        channel=channel, prenom=prenom, poste=poste,
        domaines=domaines,
        context=context.strip() or "Mission de conseil a pourvoir.",
    )

    status = get_providers_status()

    if status.get("anthropic"):
        try:
            return _call_anthropic(MESSAGE_SYSTEM_PROMPT, user_prompt), "anthropic"
        except Exception:
            pass
    if status.get("mistral"):
        try:
            return _call_mistral(MESSAGE_SYSTEM_PROMPT, user_prompt), "mistral"
        except Exception:
            pass
    if status.get("openai"):
        try:
            return _call_openai_text(MESSAGE_SYSTEM_PROMPT, user_prompt), "openai"
        except Exception as e:
            raise RuntimeError(f"Generation impossible : {e}")

    raise RuntimeError("Aucun provider disponible.")
