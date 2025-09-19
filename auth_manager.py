# Working corrected auth_manager.py — saved 2025-09-19 14:57:37Z
# Google OAuth for Streamlit with robust state handling (HMAC-signed, time-bound) and PKCE support.
# Fixes common "OAuth state mismatch" by avoiding reliance on ephemeral Streamlit session state.
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time as _time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import streamlit as st
from urllib.parse import urlencode, urlparse, urlunparse

# dotenv is optional; tolerate absence without crashing at import time
try:
    from dotenv import load_dotenv, find_dotenv
except Exception:
    def load_dotenv(*args, **kwargs):
        return False
    def find_dotenv(*args, **kwargs):
        return ""

# -----------------------------------------------------------------------------
# Load env
# -----------------------------------------------------------------------------
_ENV_PATH = find_dotenv(usecwd=True)
load_dotenv(_ENV_PATH, override=False)

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"

DEFAULT_SCOPES = ["openid", "email", "profile"]
STATE_TTL_SECONDS = 10 * 60  # 10 minutes default

# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _rq():
    """Lazy import of 'requests' to avoid import-time failure if not installed."""
    import importlib
    try:
        return importlib.import_module("requests")
    except Exception as e:
        st.error(f"The 'requests' package is required for Google OAuth: {e}")
        raise

def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    v = os.getenv(name)
    if v:
        return v.strip()
    try:
        sv = st.secrets.get(name)  # type: ignore[attr-defined]
        if sv:
            return str(sv).strip()
    except Exception:
        pass
    return default

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)

def _sign_state(payload: Dict[str, str], secret: str) -> str:
    """
    Create a compact, signed state token: base64url(header).base64url(payload).base64url(sig)
    header={"alg":"HS256","typ":"STATE"}
    """
    header = {"alg": "HS256", "typ": "STATE"}
    j_header = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    j_payload = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    to_sign = b".".join([_b64url(j_header).encode(), _b64url(j_payload).encode()])
    sig = hmac.new(secret.encode("utf-8"), to_sign, hashlib.sha256).digest()
    return ".".join([_b64url(j_header), _b64url(j_payload), _b64url(sig)])

def _verify_state(state_token: str, secret: str, ttl_seconds: int = STATE_TTL_SECONDS) -> Tuple[bool, Optional[Dict]]:
    try:
        parts = state_token.split(".")
        if len(parts) != 3:
            return False, None
        header_b64, payload_b64, sig_b64 = parts
        to_sign = (header_b64 + "." + payload_b64).encode("utf-8")
        expected_sig = hmac.new(secret.encode("utf-8"), to_sign, hashlib.sha256).digest()
        if not hmac.compare_digest(expected_sig, _b64url_decode(sig_b64)):
            return False, None
        payload = json.loads(_b64url_decode(payload_b64))
        ts = int(payload.get("ts", 0))
        if int(_time.time()) - ts > ttl_seconds:
            return False, None
        return True, payload
    except Exception:
        return False, None

def _build_redirect_uri() -> str:
    """
    Decide redirect URI:
    - Require GOOGLE_REDIRECT_URI (exact URL registered in Google Console).
    We do NOT guess here; incorrect guessing is a major source of OAuth failures.
    """
    redir = _get_env("GOOGLE_REDIRECT_URI")
    if not redir:
        raise RuntimeError(
            "GOOGLE_REDIRECT_URI is not set. Please set it to the exact redirect URL "
            "you registered in Google Cloud Console (including scheme and path)."
        )
    parsed = urlparse(redir)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))

def _pkce_pair() -> Tuple[str, str]:
    """Generate (code_verifier, code_challenge) pair for PKCE S256."""
    verifier = _b64url(secrets.token_bytes(32))
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = _b64url(digest)
    return verifier, challenge

# --- Streamlit URL param compatibility helpers ---
def _get_query_params():
    # Prefer new API
    try:
        return dict(st.query_params)
    except Exception:
        pass
    # Fallback to experimental API (older Streamlit)
    try:
        return dict(st.experimental_get_query_params())
    except Exception:
        return {}

def _clear_oauth_params():
    # Try new API mutation
    try:
        for k in ("code", "state", "scope", "authuser", "prompt"):
            if hasattr(st, "query_params") and k in st.query_params:
                del st.query_params[k]
        return
    except Exception:
        pass
    # Fallback to experimental API rewrite
    try:
        qp = dict(st.experimental_get_query_params())
        for k in ("code", "state", "scope", "authuser", "prompt"):
            qp.pop(k, None)
        st.experimental_set_query_params(**qp)
    except Exception:
        pass

@dataclass
class GoogleTokens:
    access_token: str
    refresh_token: Optional[str]
    id_token: Optional[str]
    expires_in: int
    token_type: str

# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------
def is_authenticated() -> bool:
    return bool(st.session_state.get("google_user"))

def current_user() -> Optional[Dict]:
    return st.session_state.get("google_user")

def logout():
    st.session_state.pop("google_tokens", None)
    st.session_state.pop("google_user", None)
    _clear_oauth_params()
    st.success("You have been signed out.")
    st.rerun()

def _exchange_code_for_tokens(code: str, redirect_uri: str, code_verifier: Optional[str]) -> GoogleTokens:
    rq = _rq()
    cid = _get_env("GOOGLE_CLIENT_ID", "")
    csec = _get_env("GOOGLE_CLIENT_SECRET", "")
    data = {
        "code": code,
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    # Use PKCE if available AND authenticate as a confidential client
    if code_verifier:
        data["code_verifier"] = code_verifier
    if csec:
        data["client_secret"] = csec

    resp = rq.post(GOOGLE_TOKEN_ENDPOINT, data=data, timeout=10)
    resp.raise_for_status()
    js = resp.json()
    return GoogleTokens(
        access_token=js.get("access_token", ""),
        refresh_token=js.get("refresh_token"),
        id_token=js.get("id_token"),
        expires_in=int(js.get("expires_in", 0)),
        token_type=js.get("token_type", "Bearer"),
    )

def _fetch_userinfo(access_token: str) -> Dict:
    rq = _rq()
    r = rq.get(
        GOOGLE_USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()

# --- Begin render_auth_ui ---
def render_auth_ui(button_label: str = "Sign in with Google"):
    """
    Sidebar UI:
      - If callback params present (code/state) -> complete OAuth, store user, clear URL.
      - If signed in -> show name/email + 'Sign out' button.
      - Else -> show ONE 'Sign in with Google' button that is a direct link to Google OAuth.
    """
    cid = _get_env("GOOGLE_CLIENT_ID")
    csec = _get_env("GOOGLE_CLIENT_SECRET")
    if not cid:
        st.error("GOOGLE_CLIENT_ID is not set.")
        return
    if not csec:
        st.info("Tip: set GOOGLE_CLIENT_SECRET for stronger state signing (still recommended with PKCE).")

    # Require a valid redirect URI
    try:
        redirect_uri = _build_redirect_uri()
    except RuntimeError as e:
        st.error(str(e))
        return

    # 1) Handle OAuth callback if Google sent us ?code=…&state=…
    qp = {}
    try:
        qp = _get_query_params()
    except Exception:
        pass

    code = qp.get("code")
    state = qp.get("state")

    if code and state:
        valid, payload = _verify_state(state, csec or cid)
        if not valid:
            st.error("OAuth state mismatch. Please try again.")
        else:
            code_verifier = payload.get("pkce")
            try:
                tokens = _exchange_code_for_tokens(code, redirect_uri, code_verifier)
                st.session_state["google_tokens"] = tokens.__dict__
                userinfo = _fetch_userinfo(tokens.access_token)
                st.session_state["google_user"] = {
                    "email": userinfo.get("email"),
                    "name": userinfo.get("name"),
                    "picture": userinfo.get("picture"),
                    "sub": userinfo.get("sub"),
                }
                _clear_oauth_params()
                st.success(f"Signed in as {userinfo.get('email')}")
                st.rerun()
            except Exception as e:
                body = getattr(getattr(e, "response", None), "text", None)
                st.error(f"Token exchange failed: {body or e}")

    # 2) If already authenticated: show user + Sign out
    if is_authenticated():
        u = current_user() or {}
        cols = st.columns([1, 3, 2])
        with cols[0]:
            if u.get("picture"):
                st.image(u["picture"], width=40)
        with cols[1]:
            st.write(f"**{u.get('name') or u.get('email')}**")
            st.caption(u.get("email", ""))
        with cols[2]:
            if st.button("Sign out", key="btn_signout_auth"):
                logout()
        return

    # 3) Not authenticated: show a direct link to Google OAuth (with PKCE + signed state)
    verifier, challenge = _pkce_pair()
    payload = {
        "ts": int(_time.time()),
        "nonce": _b64url(secrets.token_bytes(12)),
        "app": "buffett-analyzer",
        "pkce": verifier,
    }
    signed_state = _sign_state(payload, csec or cid)

    auth_params = {
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": redirect_uri,
        "scope": " ".join(DEFAULT_SCOPES),
        "state": signed_state,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(auth_params)}"
    # --- Google Logon Button ---
    # create three columns; middle one is the widest
    cols = st.columns([1, 2, 1])

    with cols[1]:               # everything in this block is centered
        st.link_button(button_label, auth_url)
        st.link_button(
            "🏠 Back to Buffett-Analyzer Home",
            "https://buffett-analyzer.investments",
        )
    # --- End --- Google Logon Button ---

# --- Begin require_auth ---
def require_auth():
    if not is_authenticated():
        render_auth_ui()   # render only when not authenticated
        st.stop()
# --- End of require_auth ---
