# chatgpt_integration.py
# OpenAI API integration for Buffett Analyzer
# Provides ChatGPT functionality with PDF export capabilities

from __future__ import annotations

import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

import streamlit as st
from dotenv import load_dotenv, find_dotenv

# PDF helpers (already in your codebase)
from chat_pdf_export import export_chat_to_pdf, export_enhanced_chat_pdf  # noqa: F401

# OpenAI SDK v1+
from openai import OpenAI
from openai._exceptions import (
    AuthenticationError,
    APIConnectionError,
    NotFoundError,
    RateLimitError,
    BadRequestError,
)

# -----------------------------
# ----- dotenv + helpers -------
# -----------------------------
# Load nearest .env (walks up from CWD). Non-destructive (won't override existing env vars).
_ENV_PATH = find_dotenv(usecwd=True)
load_dotenv(_ENV_PATH, override=False)

DEFAULT_MODEL = "gpt-4o-mini"


def _get_env_api_key() -> Optional[str]:
    """Priority: environment -> Streamlit secrets."""
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key.strip()
    try:
        key = st.secrets.get("OPENAI_API_KEY")
        if key:
            return str(key).strip()
    except Exception:
        pass
    return None


def _mask(s: Optional[str], keep: int = 4) -> str:
    if not s:
        return "None"
    s = str(s)
    return f"{'*' * max(0, len(s) - keep)}{s[-keep:]}"


# -----------------------------
# ---------- Models -----------
# -----------------------------
@dataclass
class ChatMessage:
    """Represents a single chat message."""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime


class ChatGPTIntegration:
    """Handles OpenAI API integration and chat management."""

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        # Prefer provided key; else from env/secrets
        self.api_key: Optional[str] = (api_key or _get_env_api_key())
        self.model: str = model
        self.client: Optional[OpenAI] = OpenAI(api_key=self.api_key) if self.api_key else None
        self.chat_history: List[ChatMessage] = []

    # ---- configuration ----
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def set_api_key(self, key: str):
        """Set/replace key at runtime and rebuild client."""
        self.api_key = key.strip() if key else None
        self.client = OpenAI(api_key=self.api_key) if self.api_key else None

    def health_check(self, model: Optional[str] = None) -> str:
        """Tiny test call to confirm auth + model access."""
        if not self.api_key:
            src = "env/secrets" if _get_env_api_key() else "none"
            return f"API key not set (loader saw source: {src})."

        if not self.client:
            return "Client not initialized. Try re-entering the key."

        model = model or self.model
        try:
            resp = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a health check."},
                    {"role": "user", "content": "Reply with the single word: pong."},
                ],
                max_tokens=3,
                temperature=0,
            )
            txt = (resp.choices[0].message.content or "").strip()
            if txt.lower() == "pong":
                env_status = "yes" if _ENV_PATH else "no"
                return f"OK (key={_mask(self.api_key)}, model={model}, .env found={env_status})"
            return f"Connected, unexpected reply: {txt!r}"
        except AuthenticationError:
            return f"Auth failed (key={_mask(self.api_key)}). Check OPENAI_API_KEY formatting/permissions."
        except NotFoundError:
            return f"Model '{model}' not found/authorized for this account."
        except RateLimitError:
            return "Rate limit reached; try again later."
        except APIConnectionError:
            return "Network error reaching OpenAI."
        except BadRequestError as e:
            return f"Bad request to OpenAI: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

    # ---- system context ----
    def add_system_context(self, ticker: str, company_data: Dict) -> str:
        """Create system context from current company analysis."""
        return (
            "You are an expert financial analyst assistant integrated into the Buffett Analyzer application.\n"
            f"The user is currently analyzing {ticker} with the following key metrics:\n\n"
            "Financial Data:\n"
            f"- Net Income: {company_data.get('net_income', 'N/A')}\n"
            f"- Sales: {company_data.get('sales', 'N/A')}\n"
            f"- Owner Earnings: {company_data.get('owner_earnings', 'N/A')}\n"
            f"- Look-Through Earnings: {company_data.get('look_through_earnings', 'N/A')}\n"
            f"- Altman Z-Score: {company_data.get('altman_z', 'N/A')}\n"
            f"- Capital Preservation Score: {company_data.get('capital_preservation', 'N/A')}\n"
            f"- Buffett Score: {company_data.get('buffett_score', 'N/A')}\n\n"
            "Provide insightful financial analysis and answer questions about this company using Warren Buffett's "
            "investment principles. Be specific and actionable; reference the provided metrics when relevant. "
            "Keep responses concise but informative."
        )

    # ---- core call ----
    def get_chatgpt_response(
        self,
        user_message: str,
        ticker: str,
        company_data: Dict,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> str:
        """Get response from ChatGPT with company context (synchronous)."""
        if not self.client or not self.api_key:
            return "OpenAI client not configured. Set OPENAI_API_KEY first."

        model = model or self.model
        try:
            messages = [{"role": "system", "content": self.add_system_context(ticker, company_data)}]

            # Include last up-to-6 messages for context
            recent = self.chat_history[-6:] if len(self.chat_history) > 6 else self.chat_history
            for msg in recent:
                messages.append({"role": msg.role, "content": msg.content})

            messages.append({"role": "user", "content": user_message})

            resp = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            assistant_message = (resp.choices[0].message.content or "").strip()

            # Store messages in history
            self.chat_history.append(ChatMessage("user", user_message, datetime.now()))
            self.chat_history.append(ChatMessage("assistant", assistant_message, datetime.now()))

            return assistant_message

        except AuthenticationError:
            return "Authentication failed. Verify OPENAI_API_KEY."
        except NotFoundError:
            return f"Model '{model}' not available to this account."
        except RateLimitError:
            return "Rate limit reached; please retry later."
        except APIConnectionError:
            return "Network error reaching OpenAI."
        except BadRequestError as e:
            return f"OpenAI request error: {e}"
        except Exception as e:
            return f"Unexpected error: {e}"

    # ---- utilities ----
    def get_chat_history_for_export(self) -> List[Dict]:
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            }
            for msg in self.chat_history
        ]

    def clear_chat_history(self):
        self.chat_history = []

    def export_chat_to_text(self) -> str:
        if not self.chat_history:
            return "No chat history to export."
        out = f"# ChatGPT Analysis Session\nExported: {datetime.now():%Y-%m-%d %H:%M:%S}\n\n"
        for msg in self.chat_history:
            who = "🤖 Assistant" if msg.role == "assistant" else "👤 User"
            out += f"## {who} ({msg.timestamp:%H:%M:%S})\n{msg.content}\n\n---\n\n"
        return out


# -----------------------------
# --------- UI Modal ----------
# -----------------------------
def render_chatgpt_modal(chat_integration: ChatGPTIntegration, ticker: str, company_data: Dict):
    """Render the ChatGPT integration modal UI."""
    if not st.session_state.get("show_chatgpt_modal", False):
        return

    # Basic CSS
    st.markdown(
        """
    <style>
    .chatgpt-modal { position: fixed; top: 5%; right: 2%; width: 480px; max-height: 86vh;
        background: white; border: 2px solid #1f77b4; border-radius: 15px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.2); z-index: 1000; overflow: hidden; }
    .chatgpt-header { background: linear-gradient(135deg, #1f77b4, #1565c0); color: white;
        padding: 14px 18px; margin: 0; font-weight: 600; font-size: 16px; }
    .chatgpt-content { padding: 14px 16px; max-height: 70vh; overflow-y: auto; }
    .chat-message { margin: 10px 0; padding: 10px 12px; border-radius: 10px; font-size: 14px; line-height: 1.4; }
    .user-message { background: #e3f2fd; border-left: 4px solid #2196f3; margin-left: 20px; }
    .assistant-message { background: #f1f8e9; border-left: 4px solid #4caf50; margin-right: 20px; }
    .stTextArea textarea { border-radius: 8px; border: 2px solid #e0e0e0; }
    .stTextArea textarea:focus { border-color: #1f77b4; box-shadow: 0 0 0 1px #1f77b4; }
    </style>
    """,
        unsafe_allow_html=True,
    )

    # Header row
    head_cols = st.columns([6, 1])
    with head_cols[0]:
        st.markdown('<div class="chatgpt-header">🤖 ChatGPT Financial Assistant</div>', unsafe_allow_html=True)
    with head_cols[1]:
        if st.button("✕", key="close_chatgpt_modal", help="Close ChatGPT Assistant"):
            st.session_state["show_chatgpt_modal"] = False
            st.rerun()

    # Config/status strip
    st.caption(
        f".env found: {'yes' if _ENV_PATH else 'no'} • "
        f"Env/Secrets key present: {'yes' if bool(_get_env_api_key()) else 'no'} • "
        f"Using key: {_mask(chat_integration.api_key)} • "
        f"Model: {chat_integration.model}"
    )

    # If not configured, let user paste a key
    if not chat_integration.is_configured():
        st.warning("⚠️ OpenAI API key not configured. Set `OPENAI_API_KEY` in your environment or paste it below.")
        key_in = st.text_input("Enter OpenAI API Key", type="password", key="temp_api_key")
        cols = st.columns([1, 1, 2])
        with cols[0]:
            if st.button("Save key", key="save_openai_key"):
                if key_in.strip():
                    chat_integration.set_api_key(key_in.strip())
                    st.success("Key saved in memory for this session.")
                    st.rerun()
        with cols[1]:
            if st.button("Health Check", key="health_check_no_key"):
                st.info(chat_integration.health_check())
        return

    # Health check + model choice (optional)
    hc_cols = st.columns([1, 1, 1])
    with hc_cols[0]:
        if st.button("Health Check", key="health_check_keyed"):
            st.info(chat_integration.health_check())
    with hc_cols[1]:
        # Allow on-the-fly model override
        new_model = st.text_input("Model (optional)", value=chat_integration.model, key="chat_model_name")
        if new_model and new_model != chat_integration.model:
            chat_integration.model = new_model.strip()

    st.markdown("#### Recent Conversation")
    if chat_integration.chat_history:
        for msg in chat_integration.chat_history[-8:]:
            css = "user-message" if msg.role == "user" else "assistant-message"
            role_icon = "👤" if msg.role == "user" else "🤖"
            ts = msg.timestamp.strftime("%H:%M")
            st.markdown(
                f"""
            <div class="chat-message {css}">
              <small><strong>{role_icon} {ts}</strong></small><br>{msg.content}
            </div>
            """,
                unsafe_allow_html=True,
            )
    else:
        st.info(f"💡 Ask questions about {ticker}'s financial analysis!")

    st.markdown("#### Ask a Question")
    user_input = st.text_area(
        "Your question:",
        placeholder=f"Ask about {ticker}'s financials, risks, or investment potential...",
        key="chatgpt_input",
        height=80,
    )

    btn_cols = st.columns(3)
    with btn_cols[0]:
        if st.button("Send 📤", key="send_chatgpt", type="primary"):
            if user_input.strip():
                with st.spinner("Getting AI analysis..."):
                    _ = chat_integration.get_chatgpt_response(user_input, ticker, company_data)
                st.session_state["chatgpt_input"] = ""  # clear box
                st.rerun()

    with btn_cols[1]:
        if st.button("Clear 🗑️", key="clear_chatgpt"):
            chat_integration.clear_chat_history()
            st.rerun()

    with btn_cols[2]:
        if st.button("Export 📄", key="export_chatgpt"):
            if chat_integration.chat_history:
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                pdf_filename = f"{ticker}_chatgpt_analysis_{ts}.pdf"
                try:
                    buffett_metrics = {"circle_of_competence": "Evaluated"}
                    pdf_path = export_enhanced_chat_pdf(
                        pdf_filename,
                        ticker,
                        chat_integration.get_chat_history_for_export(),
                        company_data,
                        buffett_metrics,
                    )
                    with open(pdf_path, "rb") as f:
                        st.download_button(
                            "📥 Download PDF Report",
                            f.read(),
                            file_name=pdf_filename,
                            mime="application/pdf",
                            key="download_chat_pdf",
                        )
                    st.success(f"✅ PDF report generated: {pdf_filename}")
                except Exception as e:
                    st.error(f"Error creating PDF: {e}")
                    # Fallback: text export
                    export_text = chat_integration.export_chat_to_text()
                    st.download_button(
                        "📥 Download Text (Fallback)",
                        export_text,
                        file_name=f"{ticker}_chatgpt_analysis_{ts}.txt",
                        mime="text/plain",
                        key="download_chat_text_fallback",
                    )
            else:
                st.warning("No conversation to export yet!")


def add_chatgpt_trigger_button():
    """Add the ChatGPT trigger button to the sidebar."""
    with st.sidebar:
        st.markdown("---")
        if st.button(
            "🤖 Ask ChatGPT",
            key="open_chatgpt_modal",
            help="Open ChatGPT assistant for financial analysis",
            type="primary",
        ):
            st.session_state["show_chatgpt_modal"] = True
            st.rerun()
