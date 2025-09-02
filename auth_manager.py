# auth_manager.py  (v2)
# Minimal Streamlit-based auth with a tiny JSON "DB" for stats
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict
from pathlib import Path
from datetime import datetime, timezone
import json
import re
import os
import streamlit as st

_VALID_TIERS = ("free", "premium", "professional")
_STORE_ENV = "AUTH_STORE_PATH"
_STORE_DEFAULT = ".data/paywall_store.json"


@dataclass
class UserInfo:
    email: str
    name: str
    subscription_tier: str = "free"
    is_authenticated: bool = False

    def to_dict(self) -> Dict[str, str]:
        return {
            "email": self.email,
            "name": self.name,
            "subscription_tier": self.subscription_tier,
            "is_authenticated": self.is_authenticated,
        }


def _valid_email(addr: str) -> bool:
    return bool(addr and isinstance(addr, str) and re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr))


def _get_query_params() -> Dict[str, str]:
    try:
        return dict(st.query_params)  # streamlit >= 1.30
    except Exception:
        try:
            qp = st.experimental_get_query_params()
            return {k: (v[0] if isinstance(v, list) and len(v) == 1 else v) for k, v in qp.items()}
        except Exception:
            return {}


class AuthManager:
    STATE_KEY = "auth.user"

    def __init__(self, allowed_domains: Optional[list[str]] = None):
        self.allowed_domains = set([d.lower() for d in allowed_domains]) if allowed_domains else None
        self._ensure_state()
        self._ensure_store()

    # ----------------- Public API -----------------

    def handle_login(self) -> bool:
        # Dev/bootstrap via query params
        qp = _get_query_params()
        if not self._state["is_authenticated"]:
            qp_email = qp.get("login_as")
            qp_tier = qp.get("tier")
            if qp_email and _valid_email(qp_email) and self._email_allowed(qp_email):
                tier = (qp_tier or "free").lower()
                if tier not in _VALID_TIERS:
                    tier = "free"
                self._state.update({
                    "email": qp_email.strip(),
                    "name": qp_email.split("@")[0].replace(".", " ").title(),
                    "subscription_tier": tier,
                    "is_authenticated": True,
                })
                st.session_state[self.STATE_KEY] = self._state
                self._record_login(qp_email, tier, self._state["name"])
                return True

        if self._state["is_authenticated"]:
            return True

        # Render simple login UI (no rerun loop)
        st.markdown("### Sign in")
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email", key="auth_email_input", placeholder="you@company.com")
            name = st.text_input("Display name (optional)", key="auth_name_input", placeholder="Your name")
            submitted = st.form_submit_button("Sign in")

        if submitted:
            if not _valid_email(email):
                st.error("Please enter a valid email address.")
                return False
            if not self._email_allowed(email):
                st.error("This email domain is not allowed.")
                return False

            display = (name or email.split("@")[0]).strip().replace(".", " ").title()
            tier = self._coerce_tier(self._state.get("subscription_tier"))
            self._state.update({
                "email": email.strip(),
                "name": display,
                "subscription_tier": tier,
                "is_authenticated": True,
            })
            st.session_state[self.STATE_KEY] = self._state
            self._record_login(email, tier, display)
            st.success("Signed in.")
            return True

        st.info("Sign in to continue.")
        return False

    def get_user_info(self, email: Optional[str] = None) -> Optional[Dict[str, str]]:
        self._ensure_state()
        if not self._state["is_authenticated"]:
            return None
        if email and email != self._state["email"]:
            return None
        return UserInfo(
            email=self._state["email"],
            name=self._state.get("name") or self._state["email"].split("@")[0],
            subscription_tier=self._coerce_tier(self._state.get("subscription_tier")),
            is_authenticated=True,
        ).to_dict()

    def get_current_user_email(self) -> Optional[str]:
        self._ensure_state()
        return self._state["email"] if self._state["is_authenticated"] else None

    def is_premium_user(self, email: Optional[str]) -> bool:
        info = self.get_user_info(email)
        return bool(info and info.get("subscription_tier") in ("premium", "professional"))

    def is_professional_user(self, email: Optional[str]) -> bool:
        info = self.get_user_info(email)
        return bool(info and info.get("subscription_tier") == "professional")

    def set_subscription_tier(self, tier: str) -> None:
        self._ensure_state()
        if not self._state["is_authenticated"]:
            return
        t = self._coerce_tier(tier)
        self._state["subscription_tier"] = t
        st.session_state[self.STATE_KEY] = self._state
        # persist in store
        email = self._state["email"]
        store = self._load_store()
        u = store.setdefault("users", {}).setdefault(email, {})
        u["tier"] = t
        u.setdefault("name", self._state.get("name") or email)
        self._save_store(store)

    def get_user_stats(self) -> Dict[str, int | str | bool]:
        """
        Compatibility method for your tests.
        Returns aggregate stats + current user context.
        """
        store = self._load_store()
        users = store.get("users", {})
        total_users = len(users)
        premium = sum(1 for u in users.values() if u.get("tier") == "premium")
        professional = sum(1 for u in users.values() if u.get("tier") == "professional")
        logins_total = sum(int(u.get("logins", 0)) for u in users.values())
        last_login_global = max((u.get("last_login_at", "") for u in users.values()), default="")
        return {
            "total_users": total_users,
            "premium_users": premium,
            "professional_users": professional,
            "logins_total": logins_total,
            "last_login_global": last_login_global,
            "current_user_email": self._state.get("email"),
            "is_authenticated": bool(self._state.get("is_authenticated")),
        }

    def logout(self) -> None:
        self._ensure_state()
        self._state.update({
            "email": None,
            "name": None,
            "subscription_tier": "free",
            "is_authenticated": False,
        })
        st.session_state[self.STATE_KEY] = self._state

    # ----------------- Internals -----------------

    def _ensure_state(self) -> None:
        if self.STATE_KEY not in st.session_state:
            st.session_state[self.STATE_KEY] = {
                "email": None,
                "name": None,
                "subscription_tier": "free",
                "is_authenticated": False,
            }
        self._state = st.session_state[self.STATE_KEY]

    def _email_allowed(self, email: str) -> bool:
        if not self.allowed_domains:
            return True
        try:
            domain = email.split("@", 1)[1].lower()
        except Exception:
            return False
        return domain in self.allowed_domains

    @staticmethod
    def _coerce_tier(tier: Optional[str]) -> str:
        t = (tier or "free").lower()
        return t if t in _VALID_TIERS else "free"

    # ----- tiny JSON store for testable stats -----

    def _store_path(self) -> Path:
        p = Path(os.getenv(_STORE_ENV, _STORE_DEFAULT))
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def _ensure_store(self) -> None:
        p = self._store_path()
        if not p.exists():
            p.write_text(json.dumps({"users": {}}, indent=2))

    def _load_store(self) -> dict:
        try:
            return json.loads(self._store_path().read_text() or "{}")
        except Exception:
            return {"users": {}}

    def _save_store(self, data: dict) -> None:
        tmp = self._store_path().with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2))
        tmp.replace(self._store_path())

    def _record_login(self, email: str, tier: str, name: str) -> None:
        store = self._load_store()
        user = store.setdefault("users", {}).setdefault(email, {})
        user["tier"] = self._coerce_tier(tier)
        user["name"] = name or email
        user["logins"] = int(user.get("logins", 0)) + 1
        user["last_login_at"] = datetime.now(timezone.utc).isoformat()
        self._save_store(store)