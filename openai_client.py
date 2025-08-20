# openai_client.py
from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv

# Optional: if you use Streamlit secrets as a fallback
try:
    import streamlit as st
except Exception:
    st = None  # not running inside Streamlit

# Official SDK v1+
from openai import OpenAI
from openai._exceptions import AuthenticationError, APIConnectionError, NotFoundError, RateLimitError, BadRequestError

# Load .env once (safe to call multiple times)
load_dotenv(override=False)


def _get_api_key() -> Optional[str]:
    # Priority: explicit env var, then streamlit secrets (if present)
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key

    if st is not None:
        try:
            key = st.secrets.get("OPENAI_API_KEY")
            if key:
                return key
        except Exception:
            pass
    return None


def _mask(s: str, keep: int = 4) -> str:
    if not s:
        return ""
    return f"{'*' * max(0, len(s) - keep)}{s[-keep:]}"


def get_openai_client() -> OpenAI:
    api_key = _get_api_key()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file or Streamlit secrets."
        )

    # If you use org/project scoping, you can also pass organization=... or project=...
    # Example: client = OpenAI(api_key=api_key, organization=os.getenv("OPENAI_ORG_ID"))
    client = OpenAI(api_key=api_key)
    return client


def quick_ping(model: str = "gpt-4o-mini") -> str:
    """
    Small request to verify the key is valid and the model is reachable.
    Returns the assistant's one-line reply or raises a helpful exception.
    """
    client = get_openai_client()

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a health check."},
                {"role": "user", "content": "Reply with the single word: pong."},
            ],
            max_tokens=3,
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text
    except AuthenticationError as e:
        raise RuntimeError(
            "OpenAI auth failed (check OPENAI_API_KEY)."
        ) from e
    except NotFoundError as e:
        raise RuntimeError(
            f"Model '{model}' not found for your account. Try another model."
        ) from e
    except RateLimitError as e:
        raise RuntimeError(
            "Rate limit reached. Try again later or check your plan/usage."
        ) from e
    except APIConnectionError as e:
        raise RuntimeError(
            "Network error reaching OpenAI API. Check connectivity / proxy."
        ) from e
    except BadRequestError as e:
        raise RuntimeError(
            f"Bad request to OpenAI: {e}"
        ) from e
